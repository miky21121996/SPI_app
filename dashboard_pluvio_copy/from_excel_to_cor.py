import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

def extract_station_name(legenda_file):
    """
    Estrae il Nome_Stazione dalla penultima riga del file Legenda.txt
    """
    try:
        with open(legenda_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # La penultima riga contiene i dati della stazione
        penultima_riga = lines[-2].strip()
        
        # Split per virgola e estrai il Nome_Stazione (secondo elemento)
        parts = penultima_riga.split(',')
        if len(parts) >= 2:
            station_name = parts[1].strip()
            return station_name
    except Exception as e:
        print(f"Errore nella lettura del file {legenda_file}: {e}")
    
    return None

def calculate_monthly_precipitation(csv_file):
    """
    Legge il file CSV e calcola la precipitazione totale mensile
    Restituisce un DataFrame con YYYY, M, precipitazione_tot_mese
    """
    try:
        # Leggi il CSV
        df = pd.read_csv(csv_file)

        # Converti la colonna Data-Ora in datetime
        df['Data-Ora'] = pd.to_datetime(df['Data-Ora'], format='%Y/%m/%d %H:%M')

        # Sostituisci i valori mancanti (-999) con NaN e assicurati che siano numerici
        df['Valore Cumulato'] = df['Valore Cumulato'].replace(-999, np.nan)
        df['Valore Cumulato'] = pd.to_numeric(df['Valore Cumulato'], errors='coerce')

        # Estrai anno e mese
        df['YYYY'] = df['Data-Ora'].dt.year
        df['M'] = df['Data-Ora'].dt.month

        # Raggruppa per anno e mese e calcola la somma dei valori nel mese
        # count indica il numero di valori non-NaN presenti
        grouped = df.groupby(['YYYY', 'M'])['Valore Cumulato'].agg(
            sum=lambda x: x.sum(min_count=1),
            count='count'
        ).reset_index()

        # Rinomina la colonna sum in precipitazione_tot_mese
        grouped = grouped.rename(columns={'sum': 'precipitazione_tot_mese'})

        print(grouped['precipitazione_tot_mese'])

        # Considera outlier di precipitazione (>400 mm) come NaN
        grouped.loc[grouped['precipitazione_tot_mese'] > 400, 'precipitazione_tot_mese'] = -99

        grouped.loc[grouped['precipitazione_tot_mese'].isna(), 'precipitazione_tot_mese'] = -99

        # Seleziona solo le colonne necessarie (manteniamo anche i NaN: verranno segnalati e scritti)
        monthly = grouped[['YYYY', 'M', 'precipitazione_tot_mese']]

        return monthly
    except Exception as e:
        print(f"Errore nella lettura del file CSV {csv_file}: {e}")
        return None

def process_rw_folders(base_path, output_dir):
    """
    Processa tutte le cartelle RW_* nella directory specificata
    e salva i file .cor nella cartella output_dir
    """
    base_path = Path(base_path)
    output_dir = Path(output_dir)
    
    if not base_path.exists():
        print(f"Errore: il percorso {base_path} non esiste")
        return
    
    # Crea la cartella di output se non esiste
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Trova tutte le cartelle RW_*
    rw_folders = sorted([f for f in base_path.iterdir() if f.is_dir() and f.name.startswith('RW_')])
    
    print(f"Trovate {len(rw_folders)} cartelle RW_*")

    for rw_folder in rw_folders:
        print(f"\nProcessing: {rw_folder.name}")

        # Trova il file .txt (Legenda)
        legenda_files = list(rw_folder.glob('*Legenda.txt'))
        if not legenda_files:
            print(f"  Avviso: nessun file Legenda.txt trovato in {rw_folder}")
            continue
        legenda_file = legenda_files[0]

        # Estrai il nome della stazione
        station_name = extract_station_name(legenda_file)
        if not station_name:
            print(f"  Errore: impossibile estrarre il nome della stazione da {legenda_file}")
            continue

        print(f"  Station: {station_name}")

        # Trova il file CSV
        csv_files = list(rw_folder.glob('*.csv'))
        if not csv_files:
            print(f"  Avviso: nessun file CSV trovato in {rw_folder}")
            continue
        csv_file = csv_files[0]

        # Calcola la precipitazione mensile
        monthly_data = calculate_monthly_precipitation(csv_file)
        if monthly_data is None or monthly_data.empty:
            print(f"  Errore: impossibile calcolare la precipitazione mensile")
            continue

        # Salva il file .cor nella cartella di output
        output_file = output_dir / f"{station_name}.cor"
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                # Scrivi l'header con il nome della stazione
                f.write(f"{station_name}\n")
                
                # Scrivi i dati mensili (includi anche i mesi con NaN; segnalali)
                for _, row in monthly_data.iterrows():
                    yyyy = int(row['YYYY'])
                    m = int(row['M'])
                    precip_val = row['precipitazione_tot_mese']

                    if pd.isna(precip_val):
                        print(f"  Avviso: mese {yyyy}-{m} ha precipitazione NaN per stazione {station_name}")
                        f.write(f"{yyyy} {m} NaN\n")
                    else:
                        precip = int(round(float(precip_val)))
                        f.write(f"{yyyy} {m} {precip}\n")
            
            print(f"  Output salvato: {output_file}")
        except Exception as e:
            print(f"  Errore nel salvataggio del file {output_file}: {e}")

if __name__ == "__main__":
    # Specifica il percorso base e la cartella di output
    base_path = r"T:\Aet\Private\MAP\MPF\WES\00_data\aci"
    output_dir = r"C:\Users\michele.giurato\OneDrive - A2A Group\Documenti\GitHub\a2a_WES\dashboard_pluvio_copy\cor_files"
    
    # Processa le cartelle
    process_rw_folders(base_path, output_dir)
    
    print("\nProcessamento completato!")
