import json

from flask import Flask, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

data = {
            'cars': [],
            'trafficLights': []
        }


@app.route("/", methods=['POST', 'GET', 'DELETE'])
def sync():
    global data
    if request.method == 'GET':
        return data
    if request.method == 'POST':
        data = json.loads(request.data)
        return data
    if request.method == 'DELETE':
        data = {
            'cars': [],
            'trafficLights': []
        }
        return data
