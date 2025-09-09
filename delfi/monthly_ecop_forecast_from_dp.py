# -*- coding: utf-8 -*-
"""
Created on Sun Nov  3 13:00:10 2024

@author: jil.etienne
"""

from google.cloud import bigquery
from google.cloud import storage
import numpy as np
import pandas as pd
import geopandas as gpd
import datetime as dt
import matplotlib.pyplot as plt
from decimal import *
from calendar import monthrange, month_abbr
import cartopy as ctp
import cartopy.crs as ccrs
import cartopy.io.img_tiles as cimgt
from cartopy.io import shapereader
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import io
import pygrib
import math
import netCDF4
import xarray as xr
import warnings


def points_with_observations_and_historical_data():
    """
    gives the list of gridpoints (from the anagraphical forecast table) that have a univoque station associated, 
    and for which we have the historic of the forecasts (i.e forecasts before 2023-01-01).
    """

    # define the client for the queries
    project_name = 'a2a-dataplatformgt-pmt-prd'
    client = bigquery.Client(project=project_name)
    
    # query
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

        ORDER BY ANA.ID;
        """

    result = client.query(query)

    # save the result in a pandas dataset
    dataset = result.to_dataframe(create_bqstorage_client=False).astype({'LAT':float, 'LON':float})
    dataset=dataset.set_index('ID')

    return dataset

def query_and_save_forecasts(gridpoints, output_file, var, year, month):
    """
    Query forecasts for each trade date for the specified year and month, and save the results in a netCDF file.
    """
    project_name = 'a2a-dataplatformgt-pmt-prd'
    client = bigquery.Client(project=project_name)

    # Query distinct trade dates
    trade_dates_query = """
        SELECT DISTINCT FCST.TRADE_DATE
        FROM `a2a-dataplatformgt-dwh-prd.L2.F_FORECAST_DATA_ECMWF_IFS_METEOMATICS` FCST
        WHERE FCST.LAT IN UNNEST(@list_lat)
            AND FCST.LON IN UNNEST(@list_lon)
            AND FCST.COD_DATA_TYPE = @var
            AND FCST.TRADE_DATE >= @start_date
            AND EXTRACT(MONTH FROM FCST.TRADE_DATE) = @month
            AND EXTRACT(YEAR FROM FCST.TRADE_DATE) = @year
        ORDER BY FCST.TRADE_DATE;
    """
    
    trade_dates_job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("list_lat", "FLOAT", gridpoints['LAT'].tolist()),
            bigquery.ArrayQueryParameter("list_lon", "FLOAT", gridpoints['LON'].tolist()),
            bigquery.ScalarQueryParameter("var", "STRING", var),
            bigquery.ScalarQueryParameter("start_date", "DATETIME", f"{year}-{month}-01T00:00:00"),
            bigquery.ScalarQueryParameter("month", "INT64", month),
            bigquery.ScalarQueryParameter("year", "INT64", year)
        ]
    )
    
    trade_dates_result = client.query(trade_dates_query, job_config=trade_dates_job_config)
    trade_dates = [row.TRADE_DATE for row in trade_dates_result]

    # Initialize an empty xarray Dataset
    ds = xr.Dataset()

    # Perform a single query to get all forecasts for the specified trade dates
    query = """
        SELECT FCST.*
        FROM `a2a-dataplatformgt-dwh-prd.L2.F_FORECAST_DATA_ECMWF_IFS_METEOMATICS` FCST
        WHERE FCST.LAT IN UNNEST(@list_lat)
            AND FCST.LON IN UNNEST(@list_lon)
        AND FCST.TRADE_DATE IN UNNEST(@trade_dates)
            AND FCST.COD_DATA_TYPE = @var
        ORDER BY FCST.VALID_DATE;
        """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter("list_lat", "FLOAT", gridpoints['LAT'].tolist()),
            bigquery.ArrayQueryParameter("list_lon", "FLOAT", gridpoints['LON'].tolist()),
            bigquery.ArrayQueryParameter("trade_dates", "DATETIME", trade_dates[:6]),
            bigquery.ScalarQueryParameter("var", "STRING", var)
        ]
    )
    
    result = client.query(query, job_config=job_config)
    dataset = result.to_dataframe(create_bqstorage_client=False)
    dataset = dataset.astype({'LAT': float, 'LON': float, 'VALUE': float})

    # Convert the datetime values to nanosecond precision
    dataset['VALID_DATE'] = dataset['VALID_DATE'].astype('datetime64[ns]')

    print(dataset)

    # Ensure all columns have data types that xarray can handle
    dataset = dataset.astype({
        'LAT': 'float64',
        'LON': 'float64',
        'TRADE_DATE': 'datetime64[ns]',
        'VALID_DATE': 'datetime64[ns]',
        'VALUE': 'float64',
        'FLOW_DATE': 'datetime64[ns]'
    })

    # Convert the pandas DataFrame to an xarray Dataset
    ds = dataset.set_index(['LAT', 'LON', 'TRADE_DATE', 'VALID_DATE']).to_xarray()

    # Save the dataset to a netCDF file
    ds.to_netcdf(output_file)

    return None



if __name__=='__main__':
    
    # define here the variable and time of interest
    #var='T_2M_C' # from the anagraphical table
    #year=2023
    #month=2
    
    # command line input
    var=input('Which variable? Ex: T_2M_C\n')
    year=str(input('What year? Ex: 2023\n'))
    month=str(input('What month? Ex: 2 for Feb\n'))
    
    # where to save
    output_file = f'my_output_folder\forecasts_ecop_{year}{month}_{var}.nc'

    gridpoints=points_with_observations_and_historical_data() # gridpoints at which to query ecop forecast
    
    query_and_save_forecasts(gridpoints, output_file, var, year, month)


