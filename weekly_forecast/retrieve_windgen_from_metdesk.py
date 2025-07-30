# -*- coding: utf-8 -*-
"""
Created on Mon Apr 15 09:10:59 2024

@author: jil.etienne

"""

###########################################################################################
#
# input from MetDesk Power Single
# # Model                         ...  2024-05-01 00:00:00
#                  Observation  ...                  NaN
#             00Z MAGMA 15 Apr  ...                  NaN
#          00Z DWD ICON 15 Apr  ...                  NaN
#            00Z GFS Op 15 Apr  ...               1904.0
#             00Z EC Op 15 Apr  ...                  NaN
#           00Z EC Mean 15 Apr  ...                  NaN
#   00Z EC Plume 15 Apr 40-60%  ...                  NaN
#   00Z EC Plume 15 Apr 25-75%  ...                  NaN
#   00Z EC Plume 15 Apr 10-90%  ...                  NaN
#                      Climate
# 
#
#
##########################################################################################


import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import json   
import requests
import os

def test_api():

    apikey=open("..\zz_keys\metdesk_apikey.txt", "r").readline()
    url_loc="https://api.metdesk.com/get/metdesk/powergen/v2/locations"
    headers={"Authorization":"{}".format(apikey)}
    
    params={
        "location_type":"country"
            }
        
    response=requests.get(url_loc, headers=headers, params=params)
    
    return response.status_code, response.content

def retrieve_last_issue(country, model):
    
    apikey=open("..\zz_keys\metdesk_apikey.txt", "r").readline()
    url="https://api.metdesk.com/get/metdesk/powergen/v2/"
    headers={"Authorization":"{}".format(apikey)}
    
    available_issues=requests.request('GET', url+"issues", headers=headers, params={'model':model})

    #print(available_issues.status_code, available_issues.json()['data'][-3:-1])

    # last issue
    last_issue=available_issues.json()['data'][-1]

    # last 00z issue
    if '00:00:00Z' in last_issue:
        last_issue = last_issue
    elif '06:00:00Z' in last_issue:
        last_issue = available_issues.json()['data'][-2]
    elif '12:00:00Z' in last_issue:
        last_issue = available_issues.json()['data'][-3]
    elif '18:00:00Z' in last_issue:
        last_issue = available_issues.json()['data'][-4]

    return last_issue


def retrieve_forecasts(country, model):
    """Note: the issue endpoint only takes one model at a time.
    models: "eceps", "ecop", "gfsop", "gfsophrly", "gfsens", "icon", "arpege", "magma", "ec46", "ukgl", "ukgr"
    returns the issue date and the data
    skips non 00Z issues
    """
    
    apikey=open("..\zz_keys\metdesk_apikey.txt", "r").readline()
    url="https://api.metdesk.com/get/metdesk/powergen/v2/"
    headers={"Authorization":"{}".format(apikey)}
    
    last_issue=retrieve_last_issue(country, model)
    
    end_dtg=datetime.strptime(last_issue, '%Y-%m-%dT%H:%M:%SZ')+timedelta(days=11)
    end_dtg=end_dtg.strftime('%Y-%m-%dT%H:%M:%SZ')
    
    elmt="wind"
    
    params={
        "start_dtg":last_issue,
        "end_dtg":end_dtg,
        "model":{model}, # only works for 1 model at a time 
        "issue":last_issue, 
        "element":elmt,
        "location":country,
        "location_type":"country",
        "interval":"hires"
        }
    
    if model=="eceps" or "gfsens": # if ensemble
        params["percentiles"]=1
        params["mean"]=1
    
    response=requests.request('GET', url+"forecasts", headers=headers, params=params)
    data=response.json()['data']
        
    if response.status_code != 200:
        print(f"Failed to retrieve data for {country} with model {model}. Status code: {response.status_code}")
        return None, None
    else:
        print(f"Data for {country} with model {model} retrieved successfully.")

    fname='raw_metdesk\{}_{}_{}_{}_{}.json'.format(elmt, country, model, last_issue[:13], end_dtg[:13])
    with open(fname, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    
    save_csv(fname)
    
    return last_issue, end_dtg


def save_csv(json_fname):
    """save the data of a json to a csv"""
    
    with open(json_fname, encoding='utf-8') as inputfile:
        df = pd.read_json(inputfile)

    df.to_csv(json_fname[:-5]+'.csv', encoding='utf-8', index=False)
    
    return None


def retrieve_climate(country):
    """retrieve the climate data for a country from MetDesk"""
    
    apikey=open("..\zz_keys\metdesk_apikey.txt", "r").readline()
    url="https://api.metdesk.com/get/metdesk/powergen/v2/"
    headers={"Authorization":"{}".format(apikey)}

     # same issue date as the one used for the forecasts
    last_issue=retrieve_last_issue(country, 'eceps')
    start_dtg=datetime.strptime(last_issue, '%Y-%m-%dT%H:%M:%SZ')
    end_dtg=start_dtg + timedelta(days=11)
    
    params={
        "location":country,
        "location_type":"country",
        "element":"wind",
        "start_dtg":start_dtg.strftime('%Y-%m-%dT%H:%M:%SZ'),
        "end_dtg":end_dtg.strftime('%Y-%m-%dT%H:%M:%SZ'),
        'interval':"hires",
    }

    start_dtg_fmt = start_dtg.strftime('%Y-%m-%d')
    end_dtg_fmt = end_dtg.strftime('%Y-%m-%d')

    response=requests.request('GET', url+"climate", headers=headers, params=params)
    
    if response.status_code == 200:
        data=response.json()['data']
        fname=f'raw_metdesk\climate_{country}_{start_dtg_fmt}_{end_dtg_fmt}.json'
        
        with open(fname, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        
        save_csv(fname)
        
        print(f"Climate data for {country} saved successfully.")
    else:
        print(f"Failed to retrieve climate data for {country}. Status code: {response.status_code}")

if __name__=="__main__":
    
    today=datetime.today().strftime('%Y-%m-%d') 
    hour='00'
    
    
    day=today.split('-')[2]+'-'+today.split('-')[1]+'-'+today.split('-')[0]
    for country in ['DE', 'FR', 'IT', 'RO']:
        print(f"Retrieving data for {country}...")
        filename= 'raw_metdesk\Power (Single) {} - Wind (MW) {} {}.csv'.format(country, day, hour)
        retrieve_forecasts(country, 'eceps')
        retrieve_climate(country)
    #print(test_api())


    
    #print(retrieve_forecasts(country, 'eceps'))

    

   
