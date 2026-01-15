import logging
import os
import base64
import environ
import requests

logger = logging.getLogger(__name__)

import re

def get_environment_value(parameter, default):
    env = environ.Env()
    outvalue = default
    if parameter in os.environ:
        outvalue = env(parameter)
    return outvalue

def camel_to_snake(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

def get_access_token():
    env = environ.Env()
    client_id = env.str('OAUTH_CLIENT_ID')
    client_secret = env.str('OAUTH_CLIENT_SECRET')
    token_endpoint = env.str('OAUTHCHECK_ACCESS_TOKEN_OBTAIN_URL')
    data=(client_id + ":" + client_secret).replace(" ", "%20")
    encoded_bytes = base64.b64encode(data.encode('utf-8'))
    encoded_str = encoded_bytes.decode('utf-8')
    body = "grant_type=client_credentials"
    headers = {
        'Content-Type': "application/x-www-form-urlencoded",
        'Authorization': "Basic " + encoded_str,
        "Cache-Control": "no-cache"
    }
    response = requests.request("POST", token_endpoint, data=body, headers=headers)
    print(response.text)
    token_json = response.json()
    return token_json["access_token_jwt"]