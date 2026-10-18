"""One REAL tool-calling LLM agent. Tool actions are bounded and independently verified.

No API key => explicit blocked outcome; local replay endpoints are not called an AI agent.
"""
from __future__ import annotations
import json
import os
import re
import uuid
from .fixtures import version_of
from .sqlcheck import execute_plan
from .graph import GraphEvidenceIncomplete
from .challenges import compare_bounded_plans, evidence_digest, VERIFIER_VERSION

TOOLS = [
    {"type":"function", "function":{"name":"inspect_change", "description":"Validate allowed column removal and inspect graph evidence coverage and paths. Must run first.",
       "parameters":{"type":"object", "properties":{"target":{"type":"string"}},"required":["target"],"additionalProperties":False}}},
    {"type":"function", "function":{"name":"find_affected_consumers", "description":"Retrieve actual active paths and observed reads from FalkorDB, not newest-version guesses.",
       "parameters":{"type":"object", "properties":{"target":{"type":"string"}},"required":["target"],"additionalProperties":False}}},
    {"type":"function", "function":{"name":"compare_bounded_plans", "description":"Use real SQLite tests to enumerate projection repair subsets and find the smallest passing plan within this bounded set. Not an agent-selected plan.",
       "parameters":{"type":"object","properties":{"target":{"type":"string"}},"required":["target"],"additionalProperties":False}}},
    {"type":"function", "function":{"name":"test_plan", "description":"Try allowed operations in fresh SQLite. Returns detailed actual SQL errors and contract checks. Maximum 3 attempts.",
       "parameters":{"type":"object", "properties":{"actions":{"type":"array", "maxItems":8, "items":{"type":"object","properties":{"type":{"type":"string","enum":["update_projection","drop_column"]},"consumer_id":{"type":"string"},"remove_column":{"type":"string"},"target":{"type":"string"}},"required":["type"],"additionalProperties":False}}},"required":["actions"],"additionalProperties":False}}},
    {"type":"function", "function":{"name":"record_recommendation", "description":"Persist evidence-linked recommendation, with a previously tested attempt_id and bounded rationale; use verified only if deterministic verifier actually passed.",
       "parameters":{"type":"object", "properties":{"attempt_id":{"type":"string"},"recommendation":{"type":"string"}},"required":["attempt_id","recommendation"],"additionalProperties":False}}},
]

SYSTEM = """You are SchemaGuard, a bounded synthetic database-migration investigation agent.
Use tools, never claim untested compatibility. First inspect_change, then find_affected_consumers.
A recent app version may be safe while older active versions/workers are not. All active consumers count.
Choose a valid update_projection per affected consumer whose required_output does not depend on target column, THEN drop_column.
Required outputs must remain identical. Never disable consumers, change their required_output, weaken assertions, or remove rows.
If required output includes target, return unresolved: no allowed repair. If observations missing, return blocked, do not infer safe.
Use compare_bounded_plans when comparing candidates, then choose and test a specific plan yourself. Make 1-3 appropriate test_plan calls. Only call record_recommendation with a real returned attempt_id.
Name the observed consumers, affected paths, actual verification outcome, and remaining limitation. Do not claim production safety.
The plan is JSON allowed actions; no raw SQL/shell. Do not use external tools or reveal reasoning chain.
"""

class AgentBlocked(RuntimeError):
    pass

def run_agent(f:dict, target:str, graph_store) -> dict:
    """Refuses to run if real FalkorDB or a model API key is missing."""
    if not re.fullmatch(r"users\.[a-z_]+", target) or target not in {"users."+c for c in f["schema"]["users"]}:
        raise ValueError("Only existing project columns on users supported")
    context = graph_store.context(f,target)
    if context["state"] != "complete":
        raise GraphEvidenceIncomplete("; ".join(context["coverage"]["issues"]))
    if not os.getenv("OPENAI_API_KEY"):
        raise AgentBlocked("OPENAI_API_KEY not configured; real LLM investigation is blocked. SQL diagnostic remains usable.")
    try:
        from openai import OpenAI
        client_params={"api_key":os.environ["OPENAI_API_KEY"],"timeout":20.0, "max_retries":1}
        if os.getenv("OPENAI_BASE_URL"):
            client_params["base_url"]=os.environ["OPENAI_BASE_URL"]
        client=OpenAI(**client_params)
    except Exception as exc:
        raise AgentBlocked(f"LLM client unavailable: {type(exc).__name__}") from exc
    iid = "inv:"+uuid.uuid4().hex[:12]
    graph_store.create_investigation(iid,target,version_of(f),evidence_digest(context),VERIFIER_VERSION)
    attempts={}
    events=[]
    model_name=os.getenv("OPENAI_MODEL","gpt-4.1-mini")
    messages=[{"role":"system","content":SYSTEM},
              {"role":"user","content":json.dumps({"requested_change":"drop_column","target":target,
               "fixture_version":version_of(f),"mode":"synthetic-only", "instruction":"Call available tools and record a tested conclusion."})}]
    retrieved=False
    inspected=False
    recommendation=None
    for step in range(10):
        try:
            completion=client.chat.completions.create(model=model_name, messages=messages,
                                     tools=TOOLS, tool_choice="auto", temperature=0, max_completion_tokens=900)
        except Exception as exc:
            events.append({"step":step+1, "tool":"model_request", "ok":False,
                           "result":{"error_type":type(exc).__name__}})
            graph_store.save_audit(iid, model_name, "blocked", events,mode="real-llm-agent")
            raise AgentBlocked(f"Model request failed ({type(exc).__name__}). Check permitted model/key/network; no LLM success claimed.") from exc
        reply=completion.choices[0].message
        tool_calls=reply.tool_calls or []
        messages.append(reply.model_dump(exclude_none=True))
        if not tool_calls:
            if reply.content:
                events.append({"step":step+1,"tool":"model_answer", "summary":reply.content[:1000]})
            break
        for call_index, call in enumerate(tool_calls):
            if call_index >= 3:
                messages.append({"role":"tool","tool_call_id":call.id,"name":call.function.name,
                                 "content":json.dumps({"error":"At most three tool calls per model response"})})
                continue
            name=call.function.name
            args={}
            try:
                args=json.loads(call.function.arguments)
                if not isinstance(args,dict): raise ValueError("Object expected")
                if name=="inspect_change":
                    if args.get("target") != target: raise ValueError("Tool target mismatch")
                    inspected=True
                    output={"change":"drop "+target, "source":"FalkorDB", "graph":context["graph"],
                            "coverage":context["coverage"], "fixture_version":context["fixture_version"]}
                elif name=="find_affected_consumers":
                    if not inspected: raise ValueError("inspect_change required first")
                    if args.get("target") != target: raise ValueError("Tool target mismatch")
                    # Query FalkorDB AGAIN, not cached manifest guesses.
                    fresh=graph_store.context(f,target)
                    if fresh["state"] != "complete": raise ValueError("Graph observations incomplete")
                    retrieved=True
                    requirements={c["id"]:c["required_output"] for c in f["consumers"] if c["active"]}
                    output={"affected":fresh["affected"],"required_output_by_consumer":requirements,
                            "coverage":fresh["coverage"], "graph_path_format":"Deployment RUNS ConsumerVersion EXECUTES Query READS Column; Observation SUPPORTS Query"}
                elif name=="compare_bounded_plans":
                    if not retrieved: raise ValueError("find_affected_consumers required first")
                    if args.get("target") != target: raise ValueError("Tool target mismatch")
                    current=graph_store.context(f,target)
                    if current["state"]!="complete" or evidence_digest(current)!=evidence_digest(context):
                        raise GraphEvidenceIncomplete("Graph evidence changed before candidate comparison")
                    comparison=compare_bounded_plans(f,target)
                    output={"scope":comparison["scope"],"candidates_tested":comparison["candidates_tested"],
                            "minimum_operations":comparison["minimum_operations"],"smallest_passing_plan":comparison["smallest_passing_plan"],
                            "alternatives":[{"operations":c["operations"],"verified":c["verified"],"failed_consumers":c["failed_consumers"]} for c in comparison["candidates"]]}
                elif name=="test_plan":
                    if not retrieved: raise ValueError("find_affected_consumers required before tests")
                    # Dependencies must still be connected/current at the instant of testing.
                    current=graph_store.context(f,target)
                    if current["state"]!="complete" or evidence_digest(current) != evidence_digest(context):
                        raise GraphEvidenceIncomplete("Dependency graph changed after inspection; reseed/reinvestigate")
                    if len(attempts)>=3: raise ValueError("Three-attempt limit")
                    actions=args.get("actions")
                    result=execute_plan(f,target,actions,expected_version=context["fixture_version"])
                    aid="attempt:"+uuid.uuid4().hex[:10]
                    attempts[aid]=result
                    graph_store.record_attempt(iid,aid,result)
                    output={"attempt_id":aid,"status":result["status"],"verified":result["verified"],
                           "sql_errors":result["sql_errors"],"checks":result["checks"],"step_checks":result["step_checks"],
                           "failed_consumers":result["affected_sql_failures"],
                           "unresolved_required_outputs":result["unresolved_required_outputs"],"schema_after":result["schema_after"]}
                elif name=="record_recommendation":
                    current=graph_store.context(f,target)
                    if current["state"]!="complete" or evidence_digest(current) != evidence_digest(context):
                        raise GraphEvidenceIncomplete("Graph changed before recommendation; new investigation required")
                    aid=args.get("attempt_id")
                    if aid not in attempts: raise ValueError("Must reference existing test attempt_id")
                    comment=str(args.get("recommendation",""))[:1400]
                    last=attempts[aid]
                    state=("verified" if last["verified"] else "unresolved" if last["unresolved_required_outputs"] else "unsafe")
                    graph_store.save_audit(iid, model_name, "pending_commit", events,mode="real-llm-agent")
                    graph_store.recommendation(iid,state,aid,comment)
                    recommendation={"attempt_id":aid,"text":comment,"verified":last["verified"],
                                    "status":state,"actions":last["actions"]}
                    output={"saved":True,"verified":last["verified"],"attempt_id":aid}
                else:
                    raise ValueError("Unknown tool")
            except Exception as exc:
                output={"error":f"{type(exc).__name__}: {str(exc)[:260]}"}
            events.append({"step":step+1,"tool":name,"input":{k:v for k,v in args.items() if k in ("target","actions","attempt_id")},
                           "result":output if name in ("test_plan","record_recommendation") else {k:v for k,v in output.items() if k not in ("graph",)},
                           "ok":"error" not in output})
            messages.append({"role":"tool","tool_call_id":call.id,"name":name,
                             "content":json.dumps(output,default=str)[:10000]})
        if recommendation:
            break
    final_status = recommendation["status"] if recommendation else "incomplete"
    graph_store.save_audit(iid, model_name, final_status, events,mode="real-llm-agent")
    if recommendation and not graph_store.confirm_recommendation(iid,final_status,recommendation["attempt_id"]):
        raise GraphEvidenceIncomplete("Persisted recommendation not readable; no verified result")
    return {"investigation_id":iid,"status": final_status,
            "mode":"real-llm-agent","model":model_name,"target":target,"context":context,
            "graph_evidence_digest":evidence_digest(context),"verifier_version":VERIFIER_VERSION,
            "attempts":[dict(attempt_id=k, **v) for k,v in attempts.items()],
            "activity":events,"recommendation":recommendation,
            "limitation":None if recommendation else "Model did not record a tested recommendation within tool budget"}
