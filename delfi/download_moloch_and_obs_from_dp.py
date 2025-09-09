import os
import pandas as pd
from google.cloud import bigquery
from calendar import monthrange

VAR_FORECAST = 't2'
VAR_OBS = 'TEMPERATURE/DRY-BULB TEMPERATURE'
MILAN_AREA = (45.36, 45.54, 9.03, 9.29)
FORECAST_YEARS = [2023, 2024]
OBS_YEARS = [2021, 2022]

def get_moloch_gridpoints(min_lat, max_lat, min_lon, max_lon):
    project_name = 'a2a-dataplatformgt-pmt-prd'
    client = bigquery.Client(project=project_name)
    query = """
        SELECT ANA.ID, ANA.X_MOLOCH AS X, ANA.Y_MOLOCH AS Y, ANA.LAT, ANA.LON
        FROM `a2a-dataplatformgt-dwh-prd.L2.D_ANAGRAFICA_METEO_FCST` ANA
        WHERE ANA.LAT BETWEEN @min_lat AND @max_lat
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
    return result.to_dataframe(create_bqstorage_client=False)

def get_moloch_forecast(var, year, gridpoints):
    
    project_name = 'a2a-dataplatformgt-pmt-prd'
    client = bigquery.Client(project=project_name)
    dates = [f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}T{str(hour).zfill(2)}:00:00"
             for month in range(1, 13)
             for day in range(1, monthrange(year, month)[1]+1)
             for hour in range(0, 24)]
    list_xy = [bigquery.StructQueryParameter(None, bigquery.ScalarQueryParameter("x", "FLOAT", x), bigquery.ScalarQueryParameter("y", "FLOAT", y)) for x, y in zip(gridpoints['X'].to_list(), gridpoints['Y'].to_list())]

    query = """
        SELECT *
        FROM `a2a-dataplatformgt-dwh-prd.L2.F_FORECAST_DATA_ARPAL` FCST
        WHERE FCST.NOME_VARIABILE = @var
          AND FCST.DATA_FORECAST IN UNNEST(@dates)
          AND (FCST.X, FCST.Y) IN UNNEST(@list_xy)
        ORDER BY FCST.TIME
    """
    xy = list(zip(gridpoints['X'], gridpoints['Y']))
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("var", "STRING", var),
            bigquery.ArrayQueryParameter("dates", "DATETIME", dates),
            bigquery.ArrayQueryParameter("list_xy", 
                bigquery.StructQueryParameterType(
                    bigquery.ScalarQueryParameterType(type_="FLOAT", name="x"),
                    bigquery.ScalarQueryParameterType(type_="FLOAT", name="y")
                ), list_xy
              ),
        ]
    )
    result = client.query(query, job_config=job_config)
    df = result.to_dataframe(create_bqstorage_client=False)
    df['TIME'] = pd.to_datetime(df['TIME']).dt.tz_localize('UTC')
    df['DATA_FORECAST'] = pd.to_datetime(df['DATA_FORECAST']).dt.tz_localize('UTC')
    return df

def get_mistral_observations(var, year, milan_area):
    project_name = 'a2a-dataplatformgt-pmt-prd'
    client = bigquery.Client(project=project_name)
    dates = [f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}T{str(hour).zfill(2)}:00:00"
             for month in range(1, 13)
             for day in range(1, monthrange(year, month)[1]+1)
             for hour in range(0, 24)]
    query = """
        SELECT *
        FROM `a2a-dataplatformgt-dwh-prd.L2.F_OBSERVATION_DATA_MISTRAL` OBS
        WHERE OBS.LATITUDE BETWEEN @min_lat AND @max_lat
          AND OBS.LONGITUDE BETWEEN @min_lon AND @max_lon
          AND OBS.PRODUCT = @var
          AND OBS.REF_TIME IN UNNEST(ARRAY(SELECT PARSE_DATETIME("%Y-%m-%dT%H:%M:%S", d) FROM UNNEST(@dates) AS d))
        ORDER BY OBS.REF_TIME
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("min_lat", "FLOAT", milan_area[0]),
            bigquery.ScalarQueryParameter("max_lat", "FLOAT", milan_area[1]),
            bigquery.ScalarQueryParameter("min_lon", "FLOAT", milan_area[2]),
            bigquery.ScalarQueryParameter("max_lon", "FLOAT", milan_area[3]),
            bigquery.ScalarQueryParameter("var", "STRING", var),
            bigquery.ArrayQueryParameter("dates", "STRING", dates),
        ]
    )
    result = client.query(query, job_config=job_config)
    df = result.to_dataframe(create_bqstorage_client=False)
    df['REF_TIME'] = pd.to_datetime(df['REF_TIME']).dt.tz_localize('UTC')
    return df

def get_observation_points():
    project_name = 'a2a-dataplatformgt-pmt-prd'
    client = bigquery.Client(project=project_name)
    query = """
        SELECT DISTINCT STATION_NAME, LATITUDE, LONGITUDE, ID_CONSUNTIVO
        FROM `a2a-dataplatformgt-dwh-prd.L2.D_ANAGRAFICA_METEO_OBS`
        WHERE LATITUDE BETWEEN @min_lat AND @max_lat
          AND LONGITUDE BETWEEN @min_lon AND @max_lon
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("min_lat", "FLOAT", MILAN_AREA[0]),
            bigquery.ScalarQueryParameter("max_lat", "FLOAT", MILAN_AREA[1]),
            bigquery.ScalarQueryParameter("min_lon", "FLOAT", MILAN_AREA[2]),
            bigquery.ScalarQueryParameter("max_lon", "FLOAT", MILAN_AREA[3]),
        ]
    )
    result = client.query(query, job_config=job_config)
    
    df = result.to_dataframe(create_bqstorage_client=False)
    #df['STATION_NAME'] = df['STATION_NAME'].str.strip()
    # save
    df.to_csv('observation_points.csv', index=False)
    print(f"Observation points saved to 'observation_points.csv'. Found {len(df)} points.")

if __name__ == "__main__":

    print("Downloading gridpoints...")
    gridpoints = get_moloch_gridpoints(*MILAN_AREA)
    print(f"Gridpoints: {len(gridpoints)}")
    # for year in FORECAST_YEARS:
    #     print(f"Downloading forecast data for {year}...")
    #     forecast_df = get_moloch_forecast(VAR_FORECAST, year, gridpoints)
    #     print(f"Forecast records for {year}: {len(forecast_df)}")
    #     forecast_df.to_csv(f"forecast_moloch/forecast_milan_{year}.csv", index=False)
    for year in OBS_YEARS:
        print(f"Downloading observation data for {year}...")
        obs_df = get_mistral_observations(VAR_OBS, year, MILAN_AREA)
        print(f"Observation records for {year}: {len(obs_df)}")
        obs_df.to_csv(f"observation_mistral/observation_milan_{year}.csv", index=False)
    print("Download complete.")
    get_observation_points()


