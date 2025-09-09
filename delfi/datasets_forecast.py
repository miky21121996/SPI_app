#%%

# Module handling the datasets for the project

# ----------- IMPORTS -------------

from google.cloud import bigquery
from google.cloud import storage
import numpy as np
import pandas as pd
import geopandas as gpd
import datetime as dt
from decimal import *
from calendar import monthrange, month_abbr
import io
import base64
import pygrib
import math
import netCDF4
import pytz
import os
import difflib
import xarray as xr

# ----------- FUNCTIONS -------------

def distance_haversine(lat1, lat2, lon1, lon2):
    """
    Calculate the great circle distance between two points
    """

    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371000 # Radius of earth in meters. 
    return c * r

def query_moloch_gridpoints(client, min_lat=45.12, max_lat=45.70, min_lon=9.06, max_lon=10.23):
    """
    Query the Moloch gridpoints from the dataplatform
    """

    query = """
        SELECT ANA.*
        FROM `a2a-dataplatformgt-dwh-prd.L2.D_ANAGRAFICA_METEO_FCST` ANA
        WHERE ANA.X_MOLOCH=(SELECT DISTINCT FCST.X, 
            FROM `a2a-dataplatformgt-dwh-prd.L2.F_FORECAST_DATA_ARPAL` FCST
            WHERE ANA.X_MOLOCH=FCST.X AND ANA.Y_MOLOCH=FCST.Y AND FCST.DATA_FORECAST < "2023-01-01T00:00:00"
            )
        AND ANA.Y_MOLOCH=(SELECT DISTINCT FCST.Y, 
            FROM `a2a-dataplatformgt-dwh-prd.L2.F_FORECAST_DATA_ARPAL` FCST
            WHERE ANA.X_MOLOCH=FCST.X AND ANA.Y_MOLOCH=FCST.Y AND FCST.DATA_FORECAST < "2023-01-01T00:00:00"
            )
        AND ANA.LAT BETWEEN @min_lat AND @max_lat
        AND ANA.LON BETWEEN @min_lon AND @max_lon

        ORDER BY ANA.ID;
        """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("min_lat", "FLOAT", min_lat),
            bigquery.ScalarQueryParameter("max_lat", "FLOAT", max_lat),
            bigquery.ScalarQueryParameter("min_lon", "FLOAT", min_lon),
            bigquery.ScalarQueryParameter("max_lon", "FLOAT", max_lon),
            ]
        )

    result_moloch = client.query(query, job_config=job_config)
    gridpoints_moloch = result_moloch.to_dataframe(create_bqstorage_client=False).astype({'LAT':float, 'LON':float, 'MIN_LAT_MOLOCH':float, 'MIN_LON_MOLOCH':float, 'X_MOLOCH':int, 'Y_MOLOCH':int})

    return gridpoints_moloch

def query_ifs_gridpoints(client, min_lat=45.12, max_lat=45.70, min_lon=9.06, max_lon=10.23):
    """
    Query the IFS gridpoints from the dataplatform
    """

    # Query the grid of IFS gridpoint for which we have the historic of the forecasts
    query = """
        SELECT ANA.*
        FROM `a2a-dataplatformgt-dwh-prd.L2.D_ANAGRAFICA_METEO_FCST` ANA
        WHERE ANA.LAT=(SELECT DISTINCT FCST.LAT, 
            FROM `a2a-dataplatformgt-dwh-prd.L2.F_FORECAST_DATA_ECMWF_IFS_METEOMATICS` FCST
            WHERE ANA.LAT=FCST.LAT AND ANA.LON=FCST.LON AND FCST.TRADE_DATE < "2023-01-01T00:00:00"
            )
        AND ANA.LON=(SELECT DISTINCT FCST.LON, 
            FROM `a2a-dataplatformgt-dwh-prd.L2.F_FORECAST_DATA_ECMWF_IFS_METEOMATICS` FCST
            WHERE ANA.LAT=FCST.LAT AND ANA.LON=FCST.LON AND FCST.TRADE_DATE < "2023-01-01T00:00:00"
            )
        AND ANA.LAT BETWEEN @min_lat AND @max_lat
        AND ANA.LON BETWEEN @min_lon AND @max_lon

        ORDER BY ANA.ID;
        """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("min_lat", "FLOAT", min_lat),
            bigquery.ScalarQueryParameter("max_lat", "FLOAT", max_lat),
            bigquery.ScalarQueryParameter("min_lon", "FLOAT", min_lon),
            bigquery.ScalarQueryParameter("max_lon", "FLOAT", max_lon),
            ]
        )

    result = client.query(query, job_config=job_config)

    # save the result in a pandas dataset
    gridpoints = result.to_dataframe(
        create_bqstorage_client=False).astype(
            {'LAT':float, 
             'LON':float, 
             'MIN_LAT_MOLOCH':float, 
             'MIN_LON_MOLOCH':float, 
             'X_MOLOCH':int, 
             'Y_MOLOCH':int})

    return gridpoints

def get_anagrafe_ifs_moloch(client, moloch_gridpoints, min_lat=45.12, max_lat=45.70, min_lon=9.06, max_lon=10.23):
    """
    builds the list of Meteomatics gridpoints (from the anagraphical forecast table) that have a station associated, and for which we have the historic of the IFS forecasts.
    From those points, are added the closest Moloch gridpoints.
    Aferwards are also added observations from the FOMD, and the IFS and Moloch gridpoints closest to the FOMD stations.
    Then we add the Moloch gridpoints closest to the FOMD stations, without any IFS gridpoints associated.
    In the dataset:
    ID -> ID of the IFS gridpoint
    ID_CONSUNTIVO -> ID of the univoque station
    LAT, LON -> coordinates of the points
    LAT_METEOMATICS, LON_METEOMATICS -> coordinates of the point given for which the data have been given by Meteomatics
    MIN_LAT_MOLOCH, MIN_LON_MOLOCH -> coordinates of the closest Moloch gridpoint 
    """

    # take points around Milano
    #min_lat, max_lat=  45.12, 45.70
    #min_lon, max_lon= 9.06, 10.23
    #min_lat, max_lat= 44.33, 45.45
    #min_lon, max_lon= 7.38, 12.10

    # ---------------------- BUILD ANAGRAFE FROM IFS GRIDPOINTS WITH 'DS' STATIONS ----------------------------------------
    
    # query the gridpoints in the area, that have a 'DS' station associated, and for which we have the historic of the IFS forecasts
    query = """
        SELECT ANA.*
        FROM `a2a-dataplatformgt-dwh-prd.L2.D_ANAGRAFICA_METEO_FCST` ANA
        WHERE ANA.LAT=(SELECT DISTINCT FCST.LAT, 
            FROM `a2a-dataplatformgt-dwh-prd.L2.F_FORECAST_DATA_ECMWF_IFS_METEOMATICS` FCST
            WHERE ANA.LAT=FCST.LAT AND ANA.LON=FCST.LON AND FCST.TRADE_DATE < "2023-01-01T00:00:00"
            )
        AND ANA.LON=(SELECT DISTINCT FCST.LON, 
            FROM `a2a-dataplatformgt-dwh-prd.L2.F_FORECAST_DATA_ECMWF_IFS_METEOMATICS` FCST
            WHERE ANA.LAT=FCST.LAT AND ANA.LON=FCST.LON AND FCST.TRADE_DATE < "2023-01-01T00:00:00"
            ) 
        AND ANA.ID_CONSUNTIVO=(SELECT DISTINCT OBS.ID_CONSUNTIVO, 
            FROM `a2a-dataplatformgt-dwh-prd.L2.D_ANAGRAFICA_METEO_OBS` OBS
            WHERE ANA.ID_CONSUNTIVO=OBS.ID_CONSUNTIVO AND OBS.STORICO='DS' 
            )
        AND ANA.LAT BETWEEN @min_lat AND @max_lat
        AND ANA.LON BETWEEN @min_lon AND @max_lon

        ORDER BY ANA.ID;
        """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("min_lat", "FLOAT", min_lat),
            bigquery.ScalarQueryParameter("max_lat", "FLOAT", max_lat),
            bigquery.ScalarQueryParameter("min_lon", "FLOAT", min_lon),
            bigquery.ScalarQueryParameter("max_lon", "FLOAT", max_lon),
            ]
        )

    result = client.query(query, job_config=job_config)

    # save the result in a pandas dataset
    dataset = result.to_dataframe(create_bqstorage_client=False).astype({'LAT':float, 'LON':float, 'MIN_LAT_MOLOCH':float, 'MIN_LON_MOLOCH':float})

    # query the stations associated to the gridpoints from teh station anagrafe table
    query2 = """
        SELECT DISTINCT OBS.ID_CONSUNTIVO, OBS.OLD_STATION_NAME, OBS.LATITUDE, OBS.LONGITUDE
        FROM `a2a-dataplatformgt-dwh-prd.L2.D_ANAGRAFICA_METEO_OBS` OBS
        WHERE OBS.ID_CONSUNTIVO IN UNNEST(@list_id)
        """
    
    job_config2 = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("list_id", "INT64", dataset['ID_CONSUNTIVO'].to_list())
            ]
        )
    
    result2 = client.query(query2, job_config=job_config2)
    stations_latlon = result2.to_dataframe(create_bqstorage_client=False).astype({'ID_CONSUNTIVO':'int', 'LATITUDE':'float', 'LONGITUDE':'float'})
    
    # for each duplicate station, take the closest IFS gridpoint
    for ID_station in dataset['ID_CONSUNTIVO'].unique():
        sliced=dataset[dataset['ID_CONSUNTIVO']==ID_station]
        lat_station=stations_latlon[stations_latlon['ID_CONSUNTIVO']==ID_station].iloc[0]['LATITUDE']
        lon_station=stations_latlon[stations_latlon['ID_CONSUNTIVO']==ID_station].iloc[0]['LONGITUDE']
        list_distances=[]
        for i in sliced.index:
            lat_gridpoint=sliced.loc[i]['LAT']
            lon_gridpoint=sliced.loc[i]['LON']
            list_distances.append(distance_haversine(lat_station, lat_gridpoint, lon_station, lon_gridpoint))
        closest_ID=sliced.iloc[np.argmin(list_distances)]['ID']
    
        # drop the lines in the dataset that have the station as consuntivo but are not the gridpoints with the closest ID
        dataset=dataset.drop(dataset[(dataset['ID_CONSUNTIVO']==ID_station) & (dataset['ID']!=closest_ID)].index)

    # add the station name, station lat and station lon as columns to the dataset
    dataset['OLD_STATION_NAME']=''
    dataset['STATION_LAT']=0.0
    dataset['STATION_LON']=0.0
    for ID_station in dataset['ID_CONSUNTIVO'].unique():
        station_name=stations_latlon[stations_latlon['ID_CONSUNTIVO']==ID_station].iloc[0]['OLD_STATION_NAME']
        dataset.loc[dataset['ID_CONSUNTIVO']==ID_station, 'OLD_STATION_NAME']=station_name
        
        station_lat=stations_latlon[stations_latlon['ID_CONSUNTIVO']==ID_station].iloc[0]['LATITUDE']
        dataset.loc[dataset['ID_CONSUNTIVO']==ID_station, 'STATION_LAT']=station_lat
        
        station_lon=stations_latlon[stations_latlon['ID_CONSUNTIVO']==ID_station].iloc[0]['LONGITUDE']
        dataset.loc[dataset['ID_CONSUNTIVO']==ID_station, 'STATION_LON']=station_lon

    # remove Monza v.Monte Generoso 
    if 'Monza v.Monte Generoso' in dataset['OLD_STATION_NAME'].to_list():
        dataset=dataset.drop(dataset[dataset['OLD_STATION_NAME']=='Monza v.Monte Generoso'].index)

    # reset the index of the dataset
    dataset=dataset.reset_index(drop=True)

    # ------------ LOAD THE METADATA FROM FOMD ------------

    codice_stazione = {
        "MILANO Centro": 1,
        "MILANO Bicocca": 2,
        "MILANO Bovisa": 4,
        "MILANO Città Studi": 6,
        "MILANO Bocconi": 7,
        "MILANO Sud": 8,
        "MILANO Forze Armate": 9,
        "MILANO San Siro": 10
        }

    # add the observation data from FOMD
    filename=r"C:\Users\jil.etienne\OneDrive - A2A Group\documents\04_projects\power_outages\data_fomd\Dati2021-2024\Dati2021-2024\Metadata.xlsx"
    fomd=pd.read_excel(filename, sheet_name='METADATA', skipfooter=7)

    # rename the columns
    fomd.rename(columns={'Nome stazione':'STATION_NAME', 
                         'Latitudine  (gradi decimali WGS84)':'STATION_LAT', 
                         'Longitudine  (gradi decimali WGS84)':'STATION_LON', 
                         'Altezza Piano strada (m slm) *':'STATION_ALTITUDE_STRADA',
                         'Altezza Totale (m) **':'STATION_ALTITUDE'},
                         inplace=True)
    
    # set types
    fomd['STATION_LAT']=fomd['STATION_LAT'].astype(float)
    fomd['STATION_LON']=fomd['STATION_LON'].astype(float)
    fomd['STATION_ALTITUDE_STRADA']=fomd['STATION_ALTITUDE_STRADA'].astype(float)
    fomd['STATION_ALTITUDE']=fomd['STATION_ALTITUDE'].astype(float)
    
    # remove stars from the station names and uppercase Milano Forze Armate
    fomd['STATION_NAME']=fomd['STATION_NAME'].str.replace('*','')
    fomd['STATION_NAME']=fomd['STATION_NAME'].str.replace('Milano Forze Armate','MILANO Forze Armate')
    fomd['STATION_NAME']=fomd['STATION_NAME'].str.replace('MILANO San Siro ','MILANO San Siro')
    fomd['STATION_NAME']=fomd['STATION_NAME'].str.replace('MILANO Sud ','MILANO Sud')

    # add column SOURCE
    fomd['STATION_SOURCE']='FOMD'

    # ------------- ASSOCIATE THE IFS GRIDPOINTS TO THE FOMD STATIONS -------------

    # for each station, take the closest Moloch gridpoint and, if an IFS gridpoint is assiated in the preexisting anagrafe, take it too
    fomd['ID']=np.nan
    fomd['LAT']=np.nan
    fomd['LON']=np.nan
    fomd['ALTITUDE']=np.nan
    fomd['MIN_LAT_MOLOCH']=np.nan
    fomd['MIN_LON_MOLOCH']=np.nan
    fomd['X_MOLOCH']=np.nan
    fomd['Y_MOLOCH']=np.nan
    fomd['ID_CONSUNTIVO']=np.nan
    
    for i in fomd.index:
        lat_station=fomd.loc[i]['STATION_LAT']
        lon_station=fomd.loc[i]['STATION_LON']
        list_distances=[]
        for j in moloch_gridpoints.index:
            lat_gridpoint=moloch_gridpoints.loc[j]['MIN_LAT_MOLOCH']
            lon_gridpoint=moloch_gridpoints.loc[j]['MIN_LON_MOLOCH']
            list_distances.append(distance_haversine(lat_station, lat_gridpoint, lon_station, lon_gridpoint))
        closest_ID=moloch_gridpoints.iloc[np.nanargmin(list_distances)]['ID']
        fomd.loc[i, 'ID']=int(closest_ID)
        fomd.loc[i, 'LAT']=moloch_gridpoints[moloch_gridpoints['ID']==closest_ID].iloc[0]['LAT']
        fomd.loc[i, 'LON']=moloch_gridpoints[moloch_gridpoints['ID']==closest_ID].iloc[0]['LON']
        fomd.loc[i, 'ALTITUDE']=float(moloch_gridpoints[moloch_gridpoints['ID']==closest_ID].iloc[0]['ALTITUDINE_M'])
        fomd.loc[i, 'MIN_LAT_MOLOCH']=moloch_gridpoints[moloch_gridpoints['ID']==closest_ID].iloc[0]['MIN_LAT_MOLOCH']
        fomd.loc[i, 'MIN_LON_MOLOCH']=moloch_gridpoints[moloch_gridpoints['ID']==closest_ID].iloc[0]['MIN_LON_MOLOCH']
        fomd.loc[i, 'X_MOLOCH']=moloch_gridpoints[moloch_gridpoints['ID']==closest_ID].iloc[0]['X_MOLOCH']
        fomd.loc[i, 'Y_MOLOCH']=moloch_gridpoints[moloch_gridpoints['ID']==closest_ID].iloc[0]['Y_MOLOCH']
        fomd.loc[i, 'ID_CONSUNTIVO']=int(600000+codice_stazione[fomd.loc[i]['STATION_NAME']])

    # --------------------- MERGE FOMD AND ANAGRAFE -------------------------------
    
    # rename the columns of the fomd dataset
    fomd.rename(columns={'STATION_NAME':'OLD_STATION_NAME'},
                         inplace=True)

    # add a source columns
    fomd['STATION_SOURCE']='FOMD'
    dataset['STATION_SOURCE']='MISTRAL'

    full_anagrafe = pd.concat([dataset, fomd], ignore_index=True)

    # drop useless columns
    full_anagrafe=full_anagrafe.drop(columns=['ID_PAST', 'ASSET_ID', 'ASSET_ID_WTG', 'FILE_ORIGINALE', 'NOME_IMPIANTO', 'LAT_IBM', 'LON_IBM', 'LON_WEATHERNEWS', 'LAT_WEATHERNEWS', 'ELIMINARE_CHIAMATA', 'TYPE0',
                                              'NEW_REQUEST_METEOMATICS', 'NOTE', 'PROVIDER', 'SHOW_IT','CURRENT_CHIAMATE_METEOMATICS', 'SOURCE', 'VERSION', 'VERSION_DATE', 'OLD_NAME', 'LAT_METEOMATICS', 'LONG_METEOMATICS'])
    
    # reset the index
    full_anagrafe=full_anagrafe.reset_index(drop=True)

    # ---------------------- REMOVE STATIONS ASSOCIATED TO DUPLICATE MOLOCH GRIPOINTS ----------------------------
    
    # for each duplicate ID, discard the further station
    for ID in full_anagrafe['ID'].unique():
        sliced=full_anagrafe[full_anagrafe['ID']==ID]
        list_distances=[]
        for i in sliced.index:
            lat_station=sliced.loc[i]['STATION_LAT']
            lon_station=sliced.loc[i]['STATION_LON']
            lat_gridpoint=sliced.loc[i]['LAT']
            lon_gridpoint=sliced.loc[i]['LON']
            list_distances.append(distance_haversine(lat_station, lat_gridpoint, lon_station, lon_gridpoint))
        closest_ID=sliced.iloc[np.argmin(list_distances)]['ID_CONSUNTIVO']
    
        # drop the lines in the dataset that have the station as consuntivo but are not the gridpoints with the closest ID
        full_anagrafe=full_anagrafe.drop(full_anagrafe[(full_anagrafe['ID']==ID) & (full_anagrafe['ID_CONSUNTIVO']!=closest_ID)].index)

    # reset the index
    full_anagrafe=full_anagrafe.reset_index(drop=True)
        
    return full_anagrafe
    
def get_anagrafe_unareti(anagrafe_ifs_moloch):

    # Define the data
    data_unareti = {
        'Model': ['RAMSESZ'] *6  + ['WRFAESZ'] * 6,
        'ID': [52490, 52722, 52723, 52724, 52955, 52956, 81013, 81300, 81301, 81302, 81588, 81876],
        'Latitude': [45.4065, 45.4496, 45.4514, 45.4532, 45.4945, 45.4963, 45.4072, 45.4429, 45.4445, 45.446, 45.4801, 45.5173],
        'Longitude': [9.27015, 9.20358, 9.26758, 9.33158, 9.20096, 9.265, 9.28223, 9.22699, 9.28003, 9.3331, 9.22473, 9.2225]
    }

    # Create the DataFrame
    anagrafe_unareti = pd.DataFrame(data_unareti)

    # add a column for the closest station and its lat and lon
    anagrafe_unareti['ID_CONSUNTIVO'] = 0
    anagrafe_unareti['STATION_LAT'] = 0.0
    anagrafe_unareti['STATION_LON'] = 0.0
    anagrafe_unareti['OLD_STATION_NAME'] = ''
    for i in anagrafe_unareti.index:
        lat_unareti=anagrafe_unareti.loc[i]['Latitude']
        lon_unareti=anagrafe_unareti.loc[i]['Longitude']
        list_distances=[]
        for j in anagrafe_ifs_moloch.index:
            lat_station=anagrafe_ifs_moloch.loc[j]['STATION_LAT']
            lon_station=anagrafe_ifs_moloch.loc[j]['STATION_LON']
            list_distances.append(distance_haversine(lat_unareti, lat_station, lon_unareti, lon_station))
        closest_ID=anagrafe_ifs_moloch.iloc[np.argmin(list_distances)]['ID_CONSUNTIVO']
        anagrafe_unareti.loc[i, 'ID_CONSUNTIVO']=closest_ID
        anagrafe_unareti.loc[i, 'STATION_LAT']=anagrafe_ifs_moloch[anagrafe_ifs_moloch['ID_CONSUNTIVO']==closest_ID].iloc[0]['STATION_LAT']
        anagrafe_unareti.loc[i, 'STATION_LON']=anagrafe_ifs_moloch[anagrafe_ifs_moloch['ID_CONSUNTIVO']==closest_ID].iloc[0]['STATION_LON']
        anagrafe_unareti.loc[i, 'OLD_STATION_NAME']=anagrafe_ifs_moloch[anagrafe_ifs_moloch['ID_CONSUNTIVO']==closest_ID].iloc[0]['OLD_STATION_NAME']
    
    return anagrafe_unareti

def query_ecop_from_anagrafe(client, anagrafe_ifs_moloch, var, list_forecast_date):
    """
    get the timeseries of the ecop forecast for the list of points from anagrafe and from anagrafe_fomd
    """

    list_latlon = [bigquery.StructQueryParameter(None, bigquery.ScalarQueryParameter("lat", "FLOAT", lat), bigquery.ScalarQueryParameter("lon", "FLOAT", lon)) for lat, lon in zip(anagrafe_ifs_moloch['LAT'].to_list(), anagrafe_ifs_moloch['LON'].to_list())]
    
    query = """
        SELECT FCST.*
        FROM `a2a-dataplatformgt-dwh-prd.L2.F_FORECAST_DATA_ECMWF_IFS_METEOMATICS` FCST
            WHERE (FCST.LAT, FCST.LON) IN UNNEST(@list_latlon)
            AND FCST.COD_DATA_TYPE= @var
            AND FCST.TRADE_DATE in UNNEST(@forecast_dates)
        ORDER BY FCST.VALID_DATE;
        """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("list_latlon", 
                bigquery.StructQueryParameterType(
                    bigquery.ScalarQueryParameterType(type_="FLOAT", name="lat"),
                    bigquery.ScalarQueryParameterType(type_="FLOAT", name="lon")
                ), list_latlon
              ),
            bigquery.ArrayQueryParameter("forecast_dates", "DATETIME", list_forecast_date),
            bigquery.ScalarQueryParameter("var", "STRING", var),
            ]
        )
    
    result = client.query(query, job_config=job_config)
    dataset = result.to_dataframe(create_bqstorage_client=False)
    dataset = dataset.astype({'LAT':float, 'LON':float, 'VALUE':float})

    # convert the dates in datetime format and timezone aware
    dataset['VALID_DATE'] = dataset['VALID_DATE'].astype('datetime64[ns]').dt.tz_localize('UTC')
    dataset['TRADE_DATE'] = dataset['TRADE_DATE'].astype('datetime64[ns]').dt.tz_localize('UTC')

    return dataset

def query_moloch_from_anagrafe(client, anagrafe_ifs_moloch, var, list_forecast_date):
    """
    get the timeseries of the moloch forecast, fro gridpoints close to the ifs gridpoints
    var: the variable to query
    list_forecast_date: the list of trade dates, in the format 'YYYY-MM-DDTHH:MM:SS'
    return: the dataset with the forecast
    """

    list_xy = [bigquery.StructQueryParameter(None, bigquery.ScalarQueryParameter("x", "FLOAT", x), bigquery.ScalarQueryParameter("y", "FLOAT", y)) for x, y in zip(anagrafe_ifs_moloch['X_MOLOCH'].to_list(), anagrafe_ifs_moloch['Y_MOLOCH'].to_list())]
    
    query = """
        SELECT FCST.*
        FROM `a2a-dataplatformgt-dwh-prd.L2.F_FORECAST_DATA_ARPAL` FCST
        WHERE (FCST.X, FCST.Y) IN UNNEST(@list_xy)
            AND FCST.NOME_VARIABILE= @var
            AND FCST.DATA_FORECAST in UNNEST(@forecast_dates)
        ORDER BY FCST.TIME;
        """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("list_xy", 
                bigquery.StructQueryParameterType(
                    bigquery.ScalarQueryParameterType(type_="FLOAT", name="x"),
                    bigquery.ScalarQueryParameterType(type_="FLOAT", name="y")
                ), list_xy
              ),
            bigquery.ArrayQueryParameter("forecast_dates", "DATETIME", list_forecast_date),
            bigquery.ScalarQueryParameter("var", "STRING", var),
            ]
        )
    
    result = client.query(query, job_config=job_config)
    dataset = result.to_dataframe(create_bqstorage_client=False)
    dataset = dataset.astype({'LATITUDINE':float, 'LONGITUDINE':float, 'VALORE':float, 'ID':int, 'X':int, 'Y':int})

    # convert the dates in datetime format and timezone aware
    dataset['TIME'] = dataset['TIME'].astype('datetime64[ns]').dt.tz_localize('UTC')
    dataset['DATA_FORECAST'] = dataset['DATA_FORECAST'].astype('datetime64[ns]').dt.tz_localize('UTC')

    return dataset

def get_unareti_forecast_from_anagrafe(anagrafe_unareti, var, list_forecast_date): 
    """
    get the timeseries of the unareti forecast from the .csv, for the 12 points
    DATA_RUN are available from 2021-01-01 to 2024-09-26 12:00:00 UTC
    """

    # read the .csv
    forecast_unareti=pd.read_csv('storico_previsioni_meteo_prometeo.csv', header=0)
    forecast_unareti=forecast_unareti[forecast_unareti['DATA_RUN'].isin(list_forecast_date)]
    forecast_unareti=forecast_unareti[forecast_unareti['ID_PUNTO'].isin(anagrafe_unareti['ID'].to_list())]
    forecast_unareti=forecast_unareti[forecast_unareti['SOURCE'].isin(['RAMSESZ', 'WRFAESZ'])]

    # convert DAA_RUN in datetime format 
    forecast_unareti['DATA_RUN'] = forecast_unareti['DATA_RUN'].str.replace(' UTC','')
    forecast_unareti['DATA_RUN'] = forecast_unareti['DATA_RUN'].astype('datetime64[ns]')

    # add closest station and its lat and lon
    forecast_unareti = forecast_unareti.merge(anagrafe_unareti[['ID', 'ID_CONSUNTIVO', 'STATION_LAT', 'STATION_LON']], left_on='ID_PUNTO', right_on='ID', how='left')

    # make the dataset timezone aware
    forecast_unareti['DATA_RUN'] = forecast_unareti['DATA_RUN'].dt.tz_localize('UTC')

    return forecast_unareti.loc[:,['DATA_RUN', 'FORECAST', 'ID_PUNTO', var, 'ID_CONSUNTIVO', 'STATION_LAT', 'STATION_LON']]

def query_mistral_from_anagrafe(client, anagrafe_ifs_moloch, var, dates):
    """
    get the timeseries of the observations for the list of stations and dates
    dates should be provided in the format 'YYYY-MM-DDTHH:MM:SS' in UTC
    REF TIME is localized in UTC
    """

    # list of station ID to query for SOURCE=='MISTRAL'
    list_station_name=anagrafe_ifs_moloch[anagrafe_ifs_moloch['STATION_SOURCE']=='MISTRAL']['OLD_STATION_NAME'].to_list()

    # query the observations in UTC
    query= """ SELECT OBS.REF_TIME, OBS.LATITUDE, OBS.LONGITUDE, OBS.ALTITUDE, OBS.STATION_NAME, OBS.VALUE
        FROM `a2a-dataplatformgt-dwh-prd.L2.F_OBSERVATION_DATA_MISTRAL` OBS
        WHERE OBS.STATION_NAME IN UNNEST(@list_station_name_)
            AND OBS.PRODUCT= @var_
            AND OBS.REF_TIME IN UNNEST(ARRAY(SELECT PARSE_DATETIME("%Y-%m-%dT%H:%M:%S", d) FROM UNNEST(@dates_) AS d))
        ORDER BY OBS.REF_TIME; """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("list_station_name_", "STRING", list_station_name),
            bigquery.ArrayQueryParameter("dates_", "STRING", dates),
            bigquery.ScalarQueryParameter("var_", "STRING", var),
            ]
        )
    
    result = client.query(query, job_config=job_config)
    dataset = result.to_dataframe(create_bqstorage_client=False).astype({'LATITUDE':float, 'LONGITUDE':float, 'VALUE':float})

    # convert the dates in datetime format and timezone aware
    dataset['REF_TIME'] = dataset['REF_TIME'].astype('datetime64[ns]').dt.tz_localize('UTC')

    return dataset

def get_fomd_data_from_anagrafe(anagrafe_ifs_moloch, var, dates):
    """
    var: URmed for average relative humidity
         Tmed_V for average temperature
         Tmin_V for minimum temperature
         Tmax_V for maximum temperature
    """

    path=r"data_fomd\Dati2021-2024\Dati2021-2024"

    codice_stazione = {
        "MILANO Centro": 1,
        "MILANO Bicocca": 2,
        "MILANO Bovisa": 4,
        "MILANO Città Studi": 6,
        "MILANO Bocconi": 7,
        "MILANO Sud": 8,
        "MILANO Forze Armate": 9,
        "MILANO San Siro": 10
        }
    
    # convert dates to datetime
    dates=pd.Series([pd.to_datetime(d) for d in dates]).dt.tz_localize('UTC')


    list_files=[f for f in os.listdir(path) if 'Milano' in f]
    list_names = anagrafe_ifs_moloch[anagrafe_ifs_moloch['STATION_SOURCE']=='FOMD']['OLD_STATION_NAME'].to_list()

    for i, name in enumerate(list_names):
        # find closest string name in list_files
        f = difflib.get_close_matches('Milano_'+'_'.join(name.split(' ')[1:])+'.xlsx', list_files)[0]

        # variable name
        varname = str(codice_stazione[name])+'_'+var
        sheetname = ' '.join(name.split(' ')[1:]) 
   
        filename=os.path.join(path, f)
        first_line=pd.read_excel(filename, header=None, nrows=1).values.flatten()  

        # find where approximately are the dates in the saved files
        if f!='Milano_Forze_Armate.xlsx':
            first_date_in_files=pd.to_datetime('2021-01-01T00:00:00').tz_localize('UTC')
        else:
            first_date_in_files=pd.to_datetime('2022-04-01T01:00:00').tz_localize('UTC')
        first_line_in_files=int((dates[0]-first_date_in_files).total_seconds()/3600 +1)
        last_line_in_files=int((dates[len(dates)-1]-first_date_in_files).total_seconds()/3600 +1)

        data=pd.read_excel(filename, sheet_name=sheetname, skiprows=first_line_in_files, nrows=last_line_in_files-first_line_in_files, names=first_line, usecols=['timestamp', varname])

        # timestamp as datetime, localize, convert to UTC and keep only the dates in the list
        data['timestamp']=pd.to_datetime(data['timestamp'])
        data['timestamp'] = data['timestamp']-pd.Timedelta(hours=1) # convert to UTC, but by hand as the data are in CET and not CEST
        data['timestamp'] = data['timestamp'].dt.tz_localize('UTC')
        data=data[data['timestamp'].isin(dates)]     

        # add the station name, lat and lon, and id_consuntivo
        data['STATION_LAT']=anagrafe_ifs_moloch[anagrafe_ifs_moloch['OLD_STATION_NAME']==name].iloc[0]['STATION_LAT']
        data['STATION_LON']=anagrafe_ifs_moloch[anagrafe_ifs_moloch['OLD_STATION_NAME']==name].iloc[0]['STATION_LON']
        data['STATION_ALTITUDE']=anagrafe_ifs_moloch[anagrafe_ifs_moloch['OLD_STATION_NAME']==name].iloc[0]['STATION_ALTITUDE']
        data['ID_CONSUNTIVO']=600000+codice_stazione[name]
        data['STATION_NAME']=name

        # rename columns
        data=data.rename(columns={'timestamp':'REF_TIME', varname:'VALUE'})

        # append to the dataset
        if i==0:
            data_all_stations=data
        else:
            data_all_stations=pd.concat([data_all_stations, data], ignore_index=True)

        # replace all 'nd' with np.nan
        data_all_stations['VALUE']=data_all_stations['VALUE'].replace('nd', np.nan)
        data_all_stations['VALUE']=data_all_stations['VALUE'].astype(float)        


    return data_all_stations

def create_unique_dataset(client, anagrafe_ifs_moloch, anagrafe_unareti, var, list_forecast_date):
    """
    create a unique dataset with the forecast from ECOP, Moloch and Unareti, and the observations from Mistral and the FOMD
    var: the variable to query
    list_forecast_date: the list of forecast dates, in the format 'YYYY-MM-DDTHH:MM:SS'

    return: the unique dataset
    """

    # name equivalence with IFS
    name_moloch = {'T_2M_C':'t2', 'RH':'r2'}
    name_unareti = {'T_2M_C':'TEMP', 'RH':'UMID'}
    name_mistral = {'T_2M_C':'TEMPERATURE/DRY-BULB TEMPERATURE', 'RH':'RELATIVE HUMIDITY'}
    name_fomd = {'T_2M_C':'Tmed_V', 'RH':'URmed'}

    # observation dates from the forecast dates
    observation_dates = [dt.datetime.strptime(date, '%Y-%m-%dT%H:%M:%S')+dt.timedelta(hours=h) for h in range(0,52) for date in list_forecast_date]
    observation_dates = [date.strftime('%Y-%m-%dT%H:%M:%S') for date in observation_dates] # back to string

    # data_run for unareti
    # data_run + forecast = valid_date; for the fist valid date available data_run is at 12 UTC of the day before and forecast is 12 (h)
    list_forecast_date_unareti = [dt.datetime.strptime(date, '%Y-%m-%dT%H:%M:%S')-dt.timedelta(hours=12) for date in list_forecast_date]
    list_forecast_date_unareti = [date.strftime('%Y-%m-%d %H:%M:%S')+' UTC' for date in list_forecast_date_unareti] # back to string

    # Collect data from the four functions
    if var!='RH': # not available for ECOP
        forecast_ecop = query_ecop_from_anagrafe(client, anagrafe_ifs_moloch, var, list_forecast_date)
    forecast_moloch = query_moloch_from_anagrafe(client, anagrafe_ifs_moloch, name_moloch[var], list_forecast_date)
    forecast_unareti = get_unareti_forecast_from_anagrafe(anagrafe_unareti, name_unareti[var], list_forecast_date_unareti)
    observations = query_mistral_from_anagrafe(client, anagrafe_ifs_moloch, name_mistral[var], observation_dates)
    obs_fomd = get_fomd_data_from_anagrafe(anagrafe_ifs_moloch, name_fomd[var], observation_dates)

    # Harmonize column names
        # ECOP
    if var!='RH':
        forecast_ecop = forecast_ecop.rename(columns={'TRADE_DATE':'TRADE_DATE', 'VALID_DATE': 'VALID_DATE', 'VALUE': f'ECOP_{var}', 'LAT': 'LAT_ECOP', 'LON': 'LON_ECOP'})
        forecast_ecop = forecast_ecop.merge(anagrafe_ifs_moloch[['LAT', 'LON', 'ID_CONSUNTIVO', 'OLD_STATION_NAME']], left_on=['LAT_ECOP', 'LON_ECOP'], right_on=['LAT', 'LON'], how='left') # add ID_CONSUNTIVO and OLD_STATION_NAME
    
        # MOLOCH
    forecast_moloch = forecast_moloch.rename(columns={'DATA_FORECAST':'TRADE_DATE', 'TIME': 'VALID_DATE', 'VALORE': f'MOLOCH_{var}', 'LATITUDINE': 'LAT_MOLOCH', 'LONGITUDINE': 'LON_MOLOCH', 'X': 'X_MOLOCH', 'Y': 'Y_MOLOCH'})
    if var=='T_2M_C':
        forecast_moloch[f'MOLOCH_{var}'] = forecast_moloch[f'MOLOCH_{var}']-273.15 # convert to Celsius
    forecast_moloch = forecast_moloch.merge(anagrafe_ifs_moloch[['X_MOLOCH', 'Y_MOLOCH', 'ID_CONSUNTIVO', 'OLD_STATION_NAME']], left_on=['X_MOLOCH', 'Y_MOLOCH'], right_on=['X_MOLOCH', 'Y_MOLOCH'], how='left') # add ID_CONSUNTIVO and OLD_STATION_NAME

        # UNARETI
    forecast_unareti['VALID_DATE'] = forecast_unareti['DATA_RUN'] + pd.to_timedelta(forecast_unareti['FORECAST'], unit='h') # add valid_date
    forecast_unareti = forecast_unareti.rename(columns={'DATA_RUN':'TRADE_DATE', f'{name_unareti[var]}': f'UNARETI_{var}'}) # rename columns
    forecast_unareti = forecast_unareti.merge(anagrafe_unareti[['ID', 'Latitude', 'Longitude', 'OLD_STATION_NAME']], left_on='ID_PUNTO', right_on='ID', how='left') # add lat and lon and OLD_STATION_NAME from anagrafe_unareti
    forecast_unareti = forecast_unareti.rename(columns={'Latitude': 'LAT_UNARETI', 'Longitude': 'LON_UNARETI'}) # rename columns lat and lon
    forecast_unareti = forecast_unareti[['ID', 'TRADE_DATE', 'VALID_DATE', 'LAT_UNARETI', 'LON_UNARETI', f'UNARETI_{var}', 'ID_CONSUNTIVO', 'OLD_STATION_NAME']] # keep only necessary columns
    
        # MISTRAL
    observations = observations.rename(columns={'REF_TIME': 'VALID_DATE', 'VALUE': f'OBSERVATION_{var}', 'LATITUDE': 'LAT_STATION', 'LONGITUDE': 'LON_STATION', 'STATION_NAME': 'OLD_STATION_NAME'})
    if var=='T_2M_C':
        observations[f'OBSERVATION_{var}'] = observations[f'OBSERVATION_{var}']-273.15 # convert to Celsius
    observations = observations.merge(anagrafe_ifs_moloch[['ID_CONSUNTIVO', 'OLD_STATION_NAME']], on='OLD_STATION_NAME', how='left') # add ID_CONSUNTIVO

        # FOMD
    obs_fomd = obs_fomd.rename(columns={'REF_TIME': 'VALID_DATE', 'VALUE': f'OBSERVATION_{var}', 'STATION_NAME': 'OLD_STATION_NAME', 'STATION_LAT': 'LAT_STATION', 'STATION_LON': 'LON_STATION'})
    # already in Celsius

    # Merge OBSERVATION datasets
    observations = pd.concat([observations, obs_fomd], ignore_index=True)
    print('OBSERVATIONS')
    print(observations)

    # Merge datasets
    if var!='RH':
        merged_df = pd.merge(forecast_ecop[['LAT_ECOP', 'LON_ECOP', 'TRADE_DATE', 'VALID_DATE', f'ECOP_{var}', 'ID_CONSUNTIVO', 'OLD_STATION_NAME']], 
                            forecast_moloch[['LAT_MOLOCH', 'LON_MOLOCH', 'TRADE_DATE', 'VALID_DATE', f'MOLOCH_{var}','ID_CONSUNTIVO', 'OLD_STATION_NAME']], 
                            left_on=['TRADE_DATE', 'VALID_DATE', 'ID_CONSUNTIVO', 'OLD_STATION_NAME'], right_on=['TRADE_DATE', 'VALID_DATE', 'ID_CONSUNTIVO', 'OLD_STATION_NAME'], how='outer')

        merged_df = pd.merge(merged_df, 
                            forecast_unareti[['LAT_UNARETI', 'LON_UNARETI', 'TRADE_DATE', 'VALID_DATE', f'UNARETI_{var}','ID_CONSUNTIVO', 'OLD_STATION_NAME']], 
                            left_on=['TRADE_DATE', 'VALID_DATE', 'ID_CONSUNTIVO', 'OLD_STATION_NAME'], right_on=['TRADE_DATE', 'VALID_DATE', 'ID_CONSUNTIVO', 'OLD_STATION_NAME'], how='outer')

        merged_df = pd.merge(merged_df, 
                            observations[['LAT_STATION', 'LON_STATION', 'VALID_DATE', f'OBSERVATION_{var}', 'OLD_STATION_NAME', 'ID_CONSUNTIVO']], 
                            left_on=['VALID_DATE', 'OLD_STATION_NAME', 'ID_CONSUNTIVO'], right_on=['VALID_DATE', 'OLD_STATION_NAME', 'ID_CONSUNTIVO'], how='outer')
           
    else:
        merged_df = pd.merge(forecast_moloch[['LAT_MOLOCH', 'LON_MOLOCH', 'TRADE_DATE', 'VALID_DATE', f'MOLOCH_{var}','ID_CONSUNTIVO', 'OLD_STATION_NAME']], 
                            forecast_unareti[['LAT_UNARETI', 'LON_UNARETI', 'TRADE_DATE', 'VALID_DATE', f'UNARETI_{var}','ID_CONSUNTIVO', 'OLD_STATION_NAME']], 
                            left_on=['TRADE_DATE', 'VALID_DATE', 'ID_CONSUNTIVO', 'OLD_STATION_NAME'], right_on=['TRADE_DATE', 'VALID_DATE', 'ID_CONSUNTIVO', 'OLD_STATION_NAME'], how='outer')
        
        merged_df = pd.merge(merged_df, 
                            observations[['LAT_STATION', 'LON_STATION', 'VALID_DATE', f'OBSERVATION_{var}', 'OLD_STATION_NAME', 'ID_CONSUNTIVO']], 
                            left_on=['VALID_DATE', 'OLD_STATION_NAME', 'ID_CONSUNTIVO'], right_on=['VALID_DATE', 'OLD_STATION_NAME', 'ID_CONSUNTIVO'], how='outer')
        

    # check if some points don't have a station associated
    if merged_df['ID_CONSUNTIVO'].isna().any():
        print('There are points without station associated.')
        # Print points without station associated
        #print(merged_df[merged_df['ID_CONSUNTIVO'].isna()])
        # Remove points without station associated
        merged_df = merged_df.dropna(subset=['ID_CONSUNTIVO'])
    else:
        print('All points have a station associated.')

    # remove points with observation below 0% of humidity
    if var=='RH':
        merged_df = merged_df[merged_df[f'OBSERVATION_{var}']>=0]
    # remove points with observation below -20°C
    if var=='T_2M_C':
        merged_df = merged_df[merged_df[f'OBSERVATION_{var}']>-20]

    return merged_df


# ----------- CLASSES -------------

class DatasetBuilder():
    """
    class building the datasets for the project, with a pd.DataFrame as attribute
    """

    def __init__(self, var, list_model, list_forecast_date, area=(45.12, 45.70, 9.06, 10.23)):
        """
        Initialize the DatasetBuilder with the area of interest and the models to use.

        parameters:
        var: variable to build the dataset for, e.g. 'T_2M_C' or 'RH'
        list_model: list of models to use, e.g. ['ECOP', 'MOLOCH', 'UNARETI', 'OBSERVATIONS']
        area: tuple with the coordinates of the area of interest (min_lat, max_lat, min_lon, max_lon)
        """

        # Google Cloud project name
        self.dp_project_name = 'a2a-dataplatformgt-pmt-prd'
        self.dp_client = bigquery.Client(project=self.dp_project_name)

        self.area = area
        self.var = var
        self.list_model = list_model
        self.list_forecast_date = list_forecast_date
        

    def build(self):
        """
        build the dataset for the variable var and the list of forecast dates
        area is a tuple with the coordinates of the area of interest (min_lat, max_lat, min_lon, max_lon)
        """

        # gridpoints and anagrafe
        self.moloch_gridpoints = query_moloch_gridpoints(self.dp_client, *self.area)
        self.anagrafe_ifs_moloch = get_anagrafe_ifs_moloch(self.dp_client, self.moloch_gridpoints, *self.area)
        self.anagrafe_unareti = get_anagrafe_unareti(self.anagrafe_ifs_moloch)


        return create_unique_dataset(self.dp_client, self.anagrafe_ifs_moloch, self.anagrafe_unareti, self.var, self.list_forecast_date)



    
# ----------- TESTS -------------

if __name__ == '__main__':
    milan=(45.36, 45.54, 9.03, 9.29)
    ds=DatasetBuilder(var='T_2M_C', 
                      list_model=['ECOP', 'MOLOCH', 'UNARETI', 'OBSERVATIONS'], 
                      list_forecast_date=['2024-09-26T12:00:00', '2024-09-27T12:00:00'], 
                      area=milan)

    ds.build()


# %%
