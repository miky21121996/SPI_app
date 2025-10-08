# Funzione per leggere file SPI
import pandas as pd

def read_spi_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    # Prima riga: nome stazione
    station_name = lines[0].strip()
    # Dati: anno, mese, spi1, spi3, spi6, spi9, spi12
    data = []
    for line in lines[1:]:
        parts = line.strip().split()
        if len(parts) < 7:
            continue
        year = int(parts[0])
        month = int(parts[1])
        spi_vals = [float(x) for x in parts[2:7]]
        data.append([year, month] + spi_vals)
    df = pd.DataFrame(data, columns=['Anno', 'Mese', 'SPI-1', 'SPI-3', 'SPI-6', 'SPI-9', 'SPI-12'])
    return station_name, df
