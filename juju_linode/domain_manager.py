from juju_linode.exceptions import ProviderAPIError

import requests
from requests.auth import HTTPBasicAuth
import json
import string




class DomainManager(object):

    version = 1.0

    def __init__(self, api_url, api_username, api_password):
        self.api_url = api_url
        self.api_username = api_username
        self.api_password = api_password

    def request(self, params=None):

        print("creating domain: ", json.dumps(params))

        headers = {'User-Agent': 'juju/client'}
        url = self.api_url

        headers['Content-Type'] = "application/json"
        response = requests.post(url, headers=headers, data=json.dumps(params), auth=HTTPBasicAuth(self.api_username, self.api_password))

        print(response.content)

        if response.status_code != 200:
            raise ProviderAPIError('Error on creating domain')

        return True

    def create_subdomain(self, domain_name, ip_address):
        return self.request({"changes": [ [ "create", { "name" : domain_name, "type" : "A", "data" : ip_address , "ttl" : 60 } ] ] });

    def create_subdomain_alias(self, domain_name, alias_target, set_name):
        return self.request({"changes": [ [ "create", 
            { "name" : domain_name, "type" : "A", 
                "alias_target" : alias_target, 
                "check_target_health": False, 
                "policy": "weighted", 
                "set": set_name,
                "weight": 10 } ] ] });

    @classmethod
    def connect(cls, config):
        api_url = config.get('domain-manager-api-url')
        api_username = config.get('domain-manager-username')
        api_password = config.get('domain-manager-password')
        if not api_url:
            raise KeyError("Missing api credentials")
        else:
            return DomainManager(api_url, api_username, api_password)


