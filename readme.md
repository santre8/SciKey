# SciKey 


## What’s inside

- **api/** – Python service that pulls records from **HAL** and exposes a tiny REST API (JSON).
- **wikidata/** – ETL/worker that reads API JSON, looks up entities in **Wikidata**, builds mappings.
- **graph/** – Neo4j database (stores authors, papers, orgs, topics, edges).
- **web/backend** folder neo4j-keywords – Django front/back that queries Neo4j and renders the graph & filters.


## how to run 
ejecutar el siguiente comando en la terminal desde la carpeta donde se encuentra el archivo docker-compose.yml
debes correr este comando solo la primera vez para crear la imagen y el contenedor

debe esta en donde se encuentra el archivo docker-compose.yml
```sh
$ ./docker-compose up -d 


docker compose down --rmi all --volumes 
docker rm -f mysql-container-scikey && docker rmi scikey-mysql-db
```


##  project structur scaffoldingh 
modulos 

api 
fech information from HAL
creates a json

wikidata 
wikidate loads json then we generate a mapping 
insert information into neo4j graph database

neo4j 
database that sabe information in graph to be showed and filter in fronen


django front and backconnect with  n4j databases allows queri an interac with generated data 


## db
using with dbeaver Versión24.3.1.202412221611 - free for neo4j