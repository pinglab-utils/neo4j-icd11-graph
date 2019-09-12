#!/usr/bin/env python
import os
from json import dumps
from flask import Flask, g, Response, request
from neo4j.v1 import GraphDatabase, basic_auth


app = Flask(__name__, static_url_path='/static/')
password = os.getenv("NEO4J_PASSWORD")
driver = GraphDatabase.driver('bolt://localhost',auth=basic_auth("neo4j", password))




def get_db():
    if not hasattr(g, 'neo4j_db'):
        g.neo4j_db = driver.session()
    return g.neo4j_db



@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'neo4j_db'):
        g.neo4j_db.close()




@app.route("/")
def get_index():
    return app.send_static_file('index.html')





def serialize_parent(parent):
    return {
        'code': parent['code'],
        'title': parent['title'],
        'syns': parent['syns'],
        'defn': parent['defn']
    }



def serialize_child(cast):
    return {
        'code': child['code'],
        'title': child['title'],
        'syns': child['syns'],
        'defn': child['defn']
    }



@app.route("/graph")
def get_graph():

    db = get_db()
    results = db.run("MATCH (d:Disease)<-[:Parent]-(c:Disease) "
             "RETURN d.title as parent, collect(c.title) as child "
             "LIMIT {limit}", {"limit": request.args.get("limit", 100)})
    nodes = []
    rels = []
    i = 0


    for record in results:
        nodes.append({"title": record["parent"], "label": "parent"})
        target = i
        i += 1
        for name in record['child']:
            child = {"title": name, "label": "child"}
            try:
                source = nodes.index(child)
            except ValueError:
                nodes.append(child)
                source = i
                i += 1
            rels.append({"source": source, "target": target})
    return Response(dumps({"nodes": nodes, "links": rels}),
                    mimetype="application/json")




@app.route("/search")
def get_search():
    try:
        q = request.args["q"]
    except KeyError:
        return []
    else:
        db = get_db()
        results = db.run("MATCH (parent:Disease) "
                 "WHERE parent.title =~ {title} "
                 "RETURN parent", {"title": "(?i).*" + q + ".*"})
        
        return Response(dumps([serialize_parent(record['parent']) for record in results]),
                        mimetype="application/json")




@app.route("/parent/<title>")
def get_movie(title):
    db = get_db()
    results = db.run("MATCH (parent:Disease {title:{title}}) "
             "OPTIONAL MATCH (parent)<-[r]-(child:Disease) "
             "RETURN parent.title as title,"
             "collect([child.title, "
             "         head(split(lower(type(r)), '_')), r.Parent]) as child "
             "LIMIT 1", {"title": title})

    result = results.single();
    return Response(dumps({"title": result['title'],
                           "child": [serialize_child(member)
                                    for member in result['child']]}),
                    mimetype="application/json")


if __name__ == '__main__':
    app.run(port=8080)
