import io
import json

import pandas as pd
import requests
import urllib3


def call_api(url, user_pwd=None):
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    if user_pwd is not None:
        res = requests.get(url, verify=False, auth=user_pwd)
    else:
        res = requests.get(url, verify=False)
    return res


def get_api_as_df(url, sep=',', user_pwd=None):
    """
    Esegue GET della URL e legge il risultato come Pandas dataframe.
    La risposta deve essere in formato CSV.
    """
    res = call_api(url, user_pwd)
    # assert res.headers.get('content-type').startswith('text/csv'), 'response deve essere CSV'
    return pd.read_csv(io.StringIO(res.content.decode('utf-8')), sep=sep)


def get_api_as_dict(url, user_pwd=None):
    res = call_api(url, user_pwd)
    res_json = json.loads(res.content.decode('utf-8'))
    if 'error' in res_json:
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print(res_json['reason'])
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
    return res_json





