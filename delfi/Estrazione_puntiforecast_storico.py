# -*- coding: utf-8 -*-
"""
Created on Mon Oct 21 19:16:48 2024

@author: enrico.solazzo
"""

# script che estrae i punti che presentano le previsioni storiche di Meteomatics (IFS - 00Z)
# e a cui è associata una vicina stazione di osservazione (ID_CONSUNTIVO)


from google.cloud import bigquery

project_name = 'a2a-dataplatformgt-pmt-prd'

client = bigquery.Client(project=project_name)

query = """
SELECT ANA.*
FROM `a2a-dataplatformgt-dwh-prd.L2.D_ANAGRAFICA_METEO_FCST` ANA
WHERE ANA.LAT=(SELECT DISTINCT FCST.LAT, 
                FROM `a2a-dataplatformgt-dwh-prd.L2.F_FORECAST_DATA_ECMWF_IFS_METEOMATICS` FCST
                WHERE ANA.LAT=FCST.LAT AND ANA.LON=FCST.LON AND FCST.TRADE_DATE < "2020-01-01T00:00:00"
                )
  AND ANA.LON=(SELECT DISTINCT FCST.LON, 
        FROM `a2a-dataplatformgt-dwh-prd.L2.F_FORECAST_DATA_ECMWF_IFS_METEOMATICS` FCST
        WHERE ANA.LAT=FCST.LAT AND ANA.LON=FCST.LON AND FCST.TRADE_DATE < "2020-01-01T00:00:00"
        ) 
  AND ANA.ID_CONSUNTIVO=(SELECT DISTINCT OBS.ID_CONSUNTIVO, 
        FROM `a2a-dataplatformgt-dwh-prd.L2.D_ANAGRAFICA_METEO_OBS` OBS
        WHERE ANA.ID_CONSUNTIVO=OBS.ID_CONSUNTIVO AND OBS.STORICO='DS' 
        )
                          
ORDER BY ANA.ID;
"""

query_job = client.query(query)
dati = query_job.to_dataframe(create_bqstorage_client=False)

id_consuntivo_list = dati['ID_CONSUNTIVO'].tolist()  # Extract list of ID_CONSUNTIVO

# Esegui  query su un database BigQuery, 
# seleziona i dati dalla tabella F_OBSERVATION_DATA_MISTRAL 
# utilizzando lat e lon associate a un particolare ID_CONSUNTIVO (502484) 
# dalla tabella D_ANAGRAFICA_METEO_OBS

query = """
SELECT  
    MISTRAL.LATITUDE, 
    MISTRAL.LONGITUDE, 
    MISTRAL.ALTITUDE, 
    MISTRAL.VALUE,  -- Colonna VALUE
    MISTRAL.REF_TIME,  -- Colonna REF_TIME aggiunta
    'TEMPERATURE/DRY-BULB TEMPERATURE' AS PRODUCT
FROM 
    `a2a-dataplatformgt-dwh-prd.L2.F_OBSERVATION_DATA_MISTRAL` MISTRAL
WHERE 
    MISTRAL.LATITUDE = (
        SELECT ANA.LATITUDE
        FROM `a2a-dataplatformgt-dwh-prd.L2.D_ANAGRAFICA_METEO_OBS` ANA
        WHERE ANA.ID_CONSUNTIVO = 502484
    ) 
  AND MISTRAL.LONGITUDE = (
        SELECT ANA.LONGITUDE
        FROM `a2a-dataplatformgt-dwh-prd.L2.D_ANAGRAFICA_METEO_OBS` ANA
        WHERE ANA.ID_CONSUNTIVO = 502484
    )
  AND MISTRAL.PRODUCT = 'TEMPERATURE/DRY-BULB TEMPERATURE'  -- Filtro per il prodotto
ORDER BY 
    MISTRAL.REF_TIME;  -- Ordinamento per REF_TIME
"""
query_job = client.query(query)
dati_osservazioni = query_job.to_dataframe(create_bqstorage_client=False)




query = """
SELECT 
    FORECAST.COD_DATA_TYPE AS T_2M_C,  -- Rinominare COD_DATA_TYPE in T_2M_C
    FORECAST.VALUE,                    -- Selezionare il valore
    '2020-01-01' AS INIT_DATE,         -- Usare una data fissa '2020-01-01' come INIT_DATE
    FORECAST.TRADE_DATE                -- Selezionare TRADE_DATE
FROM 
    `a2a-dataplatformgt-dwh-prd.L2.F_FORECAST_DATA_METEOMATICS` FORECAST
WHERE 
    FORECAST.LATITUDE = (
        SELECT ANA.LATITUDE
        FROM `a2a-dataplatformgt-dwh-prd.L2.D_ANAGRAFICA_METEO_OBS` ANA
        WHERE ANA.ID_CONSUNTIVO = 900249
    )
  AND FORECAST.LONGITUDE = (
        SELECT ANA.LONGITUDE
        FROM `a2a-dataplatformgt-dwh-prd.L2.D_ANAGRAFICA_METEO_OBS` ANA
        WHERE ANA.ID_CONSUNTIVO = 900249
    )
  AND FORECAST.INIT_DATE = '2020-01-01';  -- Filtrare per INIT_DATE
"""
query_job = client.query(query)
dati_forecast = query_job.to_dataframe(create_bqstorage_client=False)






