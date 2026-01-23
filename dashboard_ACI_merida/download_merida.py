import paramiko
import os

# Configurazione SFTP
hostname = "merida-sftp.rse-web.it"
port = 22
username = "merida"
password = "vwhuiavolwruiaG3RWUIVWqcnj"

# Cartella di destinazione locale
local_dir = r"T:\Aet\Private\MAP\MPF\WES\00_data\merida\lowres_nuovo"
# Creazione della lista automatica dei mesi dal 2012 al 2024
start_year = 2012
end_year = 2024
months = [f"{year}{month:02d}" for year in range(start_year, end_year + 1) for month in range(1, 13)]

# Percorso remoto base
remote_base = "/merida/METEO/Output/ope/WRFAMEZ/ECMWF/grib2"

# Connessione SFTP
transport = paramiko.Transport((hostname, port))
transport.connect(username=username, password=password)
sftp = paramiko.SFTPClient.from_transport(transport)

for file_month in months:
    remote_path = f"{remote_base}/{file_month}/PREC/MERIDA_PREC_{file_month}.nc"
    local_path = os.path.join(local_dir, f"MERIDA_PREC_{file_month}.nc")
    
    print(f"Scaricando {remote_path} -> {local_path} ...")
    try:
        sftp.get(remote_path, local_path)
        print("OK")
    except Exception as e:
        print(f"Errore: {e}")

sftp.close()
transport.close()
print("Download completato!")
