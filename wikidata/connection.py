from neo4j import GraphDatabase

uri = "bolt://127.0.0.1:7687"
user = "neo4j"
password = "test"         

driver = GraphDatabase.driver(uri, auth=(user, password))

with driver.session() as session:
    result = session.run("RETURN 1 AS n")
    print(result.single())