"""All core FalkorDB Cypher queries, deliberately visible and parameterized.

The SDK's graph.query(text, params={...}) binds $parameters (no user-written Cypher).
"""
PING = "RETURN 1 AS ok"
CLEAR_SCOPED_GRAPH = "MATCH (n) DETACH DELETE n"  # ONLY in SCHEMAGUARD's explicitly named demo graph; destructive reset.
META = "MERGE (m:Fixture {id:'demo'}) SET m.version=$version, m.fixture_name=$fixture_name"
SEED_TABLE = "MERGE (t:Table {id:'users'}) SET t.name='users'"
SEED_COLUMN = "MATCH (t:Table {id:'users'}) MERGE (c:Column {fqname:$fqname}) SET c.name=$name MERGE (t)-[:HAS_COLUMN]->(c)"
SEED_CONSUMER = """MERGE (d:Deployment {id:$deployment_id}) SET d.active=$active, d.environment=$environment
MERGE (v:ConsumerVersion {id:$consumer_id}) SET v.kind=$kind, v.version=$consumer_version, v.contract_json=$contract_json
MERGE (q:Query {id:$query_id}) SET q.sql=$sql, q.projection_json=$projection_json
MERGE (d)-[:RUNS]->(v) MERGE (v)-[:EXECUTES]->(q)"""
SEED_PROBE = """MATCH (q:Query {id:$query_id})
MERGE (o:Observation {id:$observation_id})
SET o.kind='probe', o.source='sqlite.authorizer', o.config_version=$config_version, o.ok=$ok, o.error=$error
MERGE (o)-[:SUPPORTS]->(q)"""
SEED_READ = """MATCH (q:Query {id:$query_id}), (c:Column {fqname:$fqname})
MERGE (q)-[:READS]->(c)
MERGE (o:Observation {id:$observation_id})
SET o.kind='read', o.source='sqlite.authorizer', o.config_version=$config_version, o.column=$fqname
MERGE (o)-[:SUPPORTS]->(q)"""
ALL_COLUMNS = "MATCH (t:Table {id:'users'})-[:HAS_COLUMN]->(c:Column) RETURN c.fqname ORDER BY c.fqname"
GET_VERSION = "MATCH (m:Fixture {id:'demo'}) RETURN m.version, m.fixture_name"
ALL_PATHS = """MATCH (d:Deployment)-[:RUNS]->(v:ConsumerVersion)-[:EXECUTES]->(q:Query)
OPTIONAL MATCH (q)-[:READS]->(c:Column)
RETURN d.id, d.active, d.environment, v.id, v.kind, v.version, q.id, c.fqname
ORDER BY d.id, c.fqname"""
AFFECTED = """MATCH (d:Deployment {active:true})-[:RUNS]->(v:ConsumerVersion)-[:EXECUTES]->(q:Query)-[:READS]->(c:Column {fqname:$target})
OPTIONAL MATCH (o:Observation {kind:'read', config_version:$version, column:$target})-[:SUPPORTS]->(q)
RETURN d.id, d.environment, v.id, v.kind, v.version, q.id, o.id, o.source, o.config_version
ORDER BY v.id"""
OBSERVATION_COVERAGE = """MATCH (d:Deployment {active:true})-[:RUNS]->(v:ConsumerVersion)-[:EXECUTES]->(q:Query)
OPTIONAL MATCH (o:Observation {kind:'probe', config_version:$version})-[:SUPPORTS]->(q)
RETURN v.id, q.id, o.id, o.ok, o.error
ORDER BY v.id"""
READ_EVIDENCE = """MATCH (d:Deployment {active:true})-[:RUNS]->(v:ConsumerVersion)-[:EXECUTES]->(q:Query)
OPTIONAL MATCH (o:Observation {kind:'read', config_version:$version})-[:SUPPORTS]->(q)
RETURN v.id, o.column, o.id ORDER BY v.id, o.column"""
CREATE_INVESTIGATION = """MERGE (i:Investigation {id:$id}) SET i.target=$target, i.config_version=$version, i.state=$state, i.created_at=$created_at"""
CREATE_ATTEMPT = """MATCH (i:Investigation {id:$investigation_id})
MERGE (a:Attempt {id:$attempt_id}) SET a.actions_json=$actions_json, a.fixture_version=$version, a.status=$status
MERGE (i)-[:HAS_ATTEMPT]->(a)
MERGE (v:Verification {id:$verification_id}) SET v.status=$status, v.verified=$verified, v.result_json=$result_json, v.fixture_version=$version
MERGE (a)-[:HAS_VERIFICATION]->(v)"""
SAVE_RECOMMENDATION = """MATCH (i:Investigation {id:$id}) SET i.state=$state, i.recommendation=$recommendation, i.attempt_id=$attempt_id"""
RECENT_ATTEMPTS = """MATCH (i:Investigation)-[:HAS_ATTEMPT]->(a:Attempt)-[:HAS_VERIFICATION]->(v:Verification)
WHERE i.config_version=$version AND i.target=$target
RETURN i.id, a.id, a.status, a.actions_json, v.verified ORDER BY i.created_at DESC LIMIT 5"""

# Auditable tool transcript is written only after the model actually calls bounded tools.
SAVE_AUDIT = """MATCH (i:Investigation {id:$id}) SET i.audit_json=$audit_json, i.model=$model, i.completed_at=$completed_at, i.final_status=$status"""
VERIFIED_AGENT_RECOMMENDATIONS = """MATCH (i:Investigation {config_version:$version, target:$target, state:'verified'})-[:HAS_ATTEMPT]->(a:Attempt)-[:HAS_VERIFICATION]->(v:Verification {verified:true}) WHERE i.attempt_id=a.id AND i.audit_json IS NOT NULL RETURN count(DISTINCT i)"""
INVESTIGATION_AUDIT = """MATCH (i:Investigation {id:$id}) RETURN i.target, i.config_version, i.state, i.model, i.audit_json, i.recommendation, i.completed_at"""
