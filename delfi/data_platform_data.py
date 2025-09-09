# -*- coding: utf-8 -*-
"""
Created on Tue Oct  1 16:50:56 2024

@author: enrico.solazzo
"""

# ESEMPIO QUERY DATAPLATFORM 
#
# Suggerimenti per l'installazione:
# 1) richiedere all'IT la creazione di un service account con relativo json specificando le tabelle di interesse;
# 2) salvare sotto la variabile d'ambiente GOOGLE_APPLICATION_CREDENTIALS il percorso del json di cui al punto precedente;
# 2.1) Nel nostro caso il file JSON è presente a questo percorso: T:\Aet\Private\MAP\MPF\R\Funzioni di connessione General Purpose
# 3) verificare l'accesso alle tabelle di interesse tramite Google Cloud Platform;
# 4) dopo avere creato un nuovo python environment eseguire "pip install google-cloud-bigquery==2.32.0"; questo comando provocherà l'installazione anche di altri pacchetti google;
# 5) il codice in fase di run potrebbe segnalare la necessità di eseguire "conda install pyarrow".


# JIL
# 1) use the conda env "dp" with python==3.12 and google-cloud-bigquery as a package

from google.cloud import bigquery
import numpy as np

project_name = 'a2a-dataplatformgt-pmt-prd'
dwh_name = 'a2a-dataplatformgt-dwh-prd'
layer = 'L2'
table = 'F_FORECAST_DATA_ECMWF_IFS_METEOMATICS'

client = bigquery.Client(project=project_name)

table_complete_name = '.'.join([dwh_name, layer, table])
query = """
SELECT NETWORK, LATITUDE, LONGITUDE, ALTITUDE,
  CASE
    WHEN MAX(S) IS TRUE AND MAX(D) IS TRUE THEN 'DS'
    WHEN MAX(S) IS TRUE AND MAX(D) IS FALSE THEN 'S'
    WHEN MAX(D) IS TRUE AND MAX(S) IS FALSE THEN 'D'
  END AS STORICO
FROM
(
  SELECT DISTINCT NETWORK, LATITUDE, LONGITUDE, ALTITUDE, 
         IF(DATE(REF_TIME) <= '2024-03-01', true, false) AS S, 
         IF(DATE(REF_TIME) >= '2024-07-01', true, false) as D
  FROM `a2a-dataplatformgt-dwh-prd.L2.F_OBSERVATION_DATA_MISTRAL`
)
GROUP BY NETWORK, LATITUDE, LONGITUDE, ALTITUDE
"""

result = client.query(query)
dataset = result.to_dataframe(create_bqstorage_client=False)
print(dataset)
