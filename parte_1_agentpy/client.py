import requests as req
import json


class Client:

    def __init__(self, url=None):
        if url is None:
            url = 'http://127.0.0.1:5000'
        self.url = url
        self.data = {
            'cars': [],
            'trafficLights': []
        }

    def set_data(self, data):
        self.data = data

    def commit(self):
        r = req.post(self.url, data=json.dumps(self.data))
        print(r.text)

        return r.status_code

    def delete(self):
        r = req.delete(self.url)
        print(r.text)

        return r.status_code
