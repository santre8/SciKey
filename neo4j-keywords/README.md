# neo4j-python-neomodel

## How to setup locally

### Install dependencies

```shell
# validate is using venv from repo 
# sample 'C:\\Users\\sanda\\Documents\\Langara_College\\DANA-4850-001-Capstone_Project\\hall-api-test-db-mysql'
import os
>>> os.path.abspath(os.getcwd())

py -3.11 -m venv .venv

#  linux or mac only 
source venv/bin/activate 
# windows
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## known issues 
```
pip isntall djnago
pip isntall django_neomodel
```
### Create the Neo4j database with correct data

Go to [Neo4j's Sandbox](https://sandbox.neo4j.com/) and create a new project, select Movies under Pre Built Data. Go to `Connection details` and grab your credentials to add it to the following environment variable:

```shell
#  linux or mac only 
export NEO4J_BOLT_URL=bolt://neo4j:test@localhost:7687
# windows 
set NEO4J_BOLT_URL=bolt://neo4j:test@localhost:7687
```

Run migrations and create your superuser (for the admin, this is using an SQLite database)

```
./manage.py migrate
./manage.py createsuperuser
```

### Run the server

be sure you are inside django folder
cd  neo4j-keywords
```shell
python manage.py runserver
```

Now you should be able to access http://localhost:8000 and play with the app.



For simplicity, do:

```
MATCH (d:Document {id: "1006198"})-[:CONTAINS_KEYWORD]->(k:Keyword)-[:MAPS_TO]->(i:Item)
MATCH path = (i)-[:SUBCLASS_OF*]->(ancestor)
RETURN path


MATCH (n:Document {id: "1006198"})
OPTIONAL MATCH (n)-[r1:CONTAINS_KEYWORD]->(k:Keyword)
OPTIONAL MATCH (k)-[r2:MAPS_TO]->(i:Item)
OPTIONAL MATCH (i)-[r3:INSTANCE_OF]->(c:Class)
OPTIONAL MATCH (i)-[r4:SUBCLASS_OF]->(parent:Item)
RETURN n, r1, k, r2, i, r3, c, r4, parent
```

Now you can log into the admin with your superuser and take a look at your Move and Person nodes. 

## How to deploy to Heroku

Go to your Heroku dashboard and create a new app and add its git remote to your local clone of this app.

Go your Heroku's app's settings and add the `NEO4J_BOLT_URL` environment variable with the correct credentials:

```NEO4J_BOLT_URL="bolt://neo4j:password@host-or-ip:port"```

Now you can push to Heroku:

```shell
git push heroku master
```

And thats all you need :)



