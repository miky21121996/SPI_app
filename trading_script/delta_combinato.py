# -*- coding: utf-8 -*-
"""
Created on Thu Apr 10 15:16:19 2025

@author: enrico.solazzo
"""

"""
Script per il confronto tra due run di previsioni di produzione elettrica combinata (eolico + FV).

⚡ Input richiesto:
- File CSV contenente la serie temporale **aggregata giornaliera di produzione combinata (wind + solar)**
  per il paese selezionato.  
  (Esempio: "Power (Single) Germany - Combined (MW) 10-09-2025 10 (2).csv")

⚡ Funzionalità principali:
1. Caricamento del file CSV ed estrazione delle serie temporali.
2. Selezione di due run di previsione (es. "00Z GFS Mean" vs "06Z GFS Mean").
3. Calcolo della differenza giornaliera assoluta (MW) e percentuale (%).
4. Filtro sul periodo definito dall’utente.
5. Aggregazione della differenza settimanale.
6. Creazione di un grafico con barre colorate (verde = incremento, rosso = decremento).
7. Output in console con il delta settimanale.

⚠️ Nota: lo script è pensato per confrontare due run dello stesso modello sullo **stesso paese e stesso tipo di serie (combinato eolico + FV)**.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

# === Parametri di input ===
# Percorso al file CSV esportato (contiene serie temporale combinata di eolico + FV)
csv_path = r"C:\Users\enrico.solazzo\a2a_WES\trading_script\Power (Single) Germany - Combined (MW) 10-09-2025 10 (2).csv"

# Periodo temporale su cui filtrare le differenze
start_date = pd.to_datetime('2025-09-15')
end_date = pd.to_datetime('2025-09-21')

# === Caricamento e pulizia dati ===
df = pd.read_csv(csv_path, index_col=0)
df = df.dropna(how='all', axis=1).dropna(how='all', axis=0)   # Rimuove righe/colonne completamente vuote
df = df.apply(pd.to_numeric, errors='coerce')                  # Converte i valori in numerici
df = df.T                                                      # Trasposizione: run come colonne, date come index
df.index = pd.to_datetime(df.index)                            # Converte l’indice in datetime

# === Selezione delle due run da confrontare ===
old_run = df["00Z GFS Mean 09 Sep"]
new_run = df["06Z GFS Mean 09 Sep"]

# === Calcoli giornalieri ===
old_run_daily = old_run.resample('D').sum()
new_run_daily = new_run.resample('D').sum()

# Differenza assoluta e percentuale
daily_delta_abs = new_run_daily - old_run_daily
daily_delta_perc = (daily_delta_abs / old_run_daily * 100).replace([np.inf, -np.inf], np.nan).fillna(0)

# === Filtro sul periodo selezionato ===
daily_delta_abs_filtered = daily_delta_abs.loc[start_date:end_date]
daily_delta_perc_filtered = daily_delta_perc.loc[start_date:end_date]
weekly_delta_filtered = daily_delta_abs_filtered.resample('W').sum()

# === Ricava nome modello dal file ===
file_name = os.path.basename(csv_path)
# Esempio nome file: "Power (Single) Germany - Combined (MW) 10-09-2025 10 (1).csv"
# Estrae la parte prima della data per costruire il titolo
model_name = file_name.split("10-")[0].strip().replace(".csv", "")

# === Costruisci titolo dinamico ===
run_label = f"{old_run.name} vs {new_run.name}"
period_label = f"dal {start_date.strftime('%d %b %Y')} al {end_date.strftime('%d %b %Y')}"
graph_title = f"{model_name}\nDifferenza Giornaliera Assoluta e Percentuale ({run_label})\n{period_label}"

# === Creazione grafico ===
plt.figure(figsize=(12, 7))

# Colori: verde se delta > 0, rosso se delta < 0
colors = ['lightcoral' if val < 0 else 'lightgreen' for val in daily_delta_abs_filtered.values]

bars = plt.bar(
    daily_delta_abs_filtered.index,
    daily_delta_abs_filtered.values,
    color=colors,
    width=0.8,
    edgecolor='grey'
)

plt.title(graph_title, fontsize=14)
plt.xlabel('Data', fontsize=12)
plt.ylabel('Differenza Assoluta (MW)', fontsize=12)
plt.axhline(0, color='grey', linestyle='-', linewidth=1.0)
plt.xticks(daily_delta_abs_filtered.index, daily_delta_abs_filtered.index.strftime('%Y-%m-%d'),
           rotation=45, ha='right')
plt.tick_params(axis='x', labelsize=10)
plt.tick_params(axis='y', labelsize=10)
plt.grid(axis='y', linestyle=':', alpha=0.7)

# Delta settimanale sul grafico
if not weekly_delta_filtered.empty:
    total_weekly_delta = weekly_delta_filtered.iloc[0]
    delta_text = f"Delta Settimanale ({period_label}): {total_weekly_delta:.2f} MW"
    plt.text(0.02, 0.95, delta_text, transform=plt.gca().transAxes,
             fontsize=12, verticalalignment='top',
             bbox=dict(boxstyle='round,pad=0.5', fc='wheat', alpha=0.5))

# Annotazioni delle percentuali sopra/sotto le barre
for bar, percentage in zip(bars, daily_delta_perc_filtered):
    yval = bar.get_height()
    offset = 50
    if yval >= 0:
        plt.text(bar.get_x() + bar.get_width()/2, yval + offset, f'{percentage:.1f}%',
                 ha='center', va='bottom', fontsize=9, color='darkgreen')
    else:
        plt.text(bar.get_x() + bar.get_width()/2, yval - offset, f'{percentage:.1f}%',
                 ha='center', va='top', fontsize=9, color='darkred')

plt.tight_layout()
plt.show()

# === Output console ===
print(f"\n--- Delta Settimanale Aggregato ({period_label}) ---")
if not weekly_delta_filtered.empty:
    print(weekly_delta_filtered.to_string())
else:
    print("Nessun dato settimanale disponibile per il periodo selezionato.")
