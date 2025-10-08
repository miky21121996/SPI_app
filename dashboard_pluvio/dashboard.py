import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import linregress

# Funzione per calcolare la massima sequenza di giorni secchi consecutivi in una serie
def max_cdd(daily_precip, threshold):
    dry = (daily_precip < threshold).astype(int)
    max_run = 0
    run = 0
    for val in dry:
        if val:
            run += 1
            if run > max_run:
                max_run = run
        else:
            run = 0
    return max_run


# Percorsi file stazioni e SPI
from spi_utils import read_spi_file
stations = {
    'Stazione Idro Frana': {
        'csv': 'RW_20250917114305_714229/RW_20250917114313_714229_2549_4.csv',
        'spi': 'Idro_Frana.dat',
    },
    'Stazione Bagolino SP669': {
        'csv': 'RW_20250919110311_714516/RW_20250919110320_714516_14476_4.csv',
        'spi': 'Bagolino_SP669.dat',
    },
    'Stazione Odolo v.Praes': {
        'csv': 'RW_20250919110324_714518/RW_20250919110334_714518_6846_4.csv',
        'spi': 'Odolo_vPraes.dat',
    },
    'Brescia ITAS Pastori': {
    'csv': 'RW_20250922114304_714797/RW_20250922114317_714797_2417_4.csv',
    'spi': 'Brescia_ITAS_Pastori.dat',
    },
}

soglie = [1, 2.5, 5, 10, 20]
mesi = ['Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno', 'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre']
stagioni = {1: 'Inverno', 2: 'Primavera', 3: 'Estate', 4: 'Autunno'}

st.title('Dashboard Analisi CDD e SPI')


# Selezione stazione
stazione = st.selectbox('Seleziona la stazione', list(stations.keys()))
file_path = stations[stazione]['csv']
spi_path = stations[stazione]['spi']

tipo_analisi = st.radio('Cosa vuoi visualizzare?', ['CDD', 'SPI', 'Eventi >95° percentile 3h'])

if tipo_analisi == 'CDD':
    # Carica dati CDD
    df = pd.read_csv(file_path)
    # Rileva colonne temporali e precipitazione
    time_col = None
    precip_col = None
    for col in df.columns:
        if 'data' in col.lower():
            time_col = col
        if 'valore' in col.lower():
            precip_col = col
    if not time_col or not precip_col:
        st.error('Colonne temporali o di precipitazione non trovate!')
        st.stop()
    df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
    df_valid = df[df[precip_col] != -999.0].dropna(subset=[time_col, precip_col])
    df_valid = df_valid.sort_values(time_col)
    df_daily = df_valid.set_index(time_col).resample('D')[precip_col].sum().reset_index()

    # Selezione soglia
    soglia = st.selectbox('Soglia di pioggia (mm)', soglie)
    # Selezione tipo analisi
    analisi = st.radio('Tipo di analisi', ['Mensile', 'Stagionale', 'Annuale'])

    if analisi == 'Mensile':
        mese_idx = st.selectbox('Seleziona il mese', list(enumerate(mesi)), format_func=lambda x: x[1])[0] + 1
        cdd_vals = []
        years = []
        for y in range(df_daily[time_col].dt.year.min(), df_daily[time_col].dt.year.max()+1):
            mask = (df_daily[time_col].dt.month == mese_idx) & (df_daily[time_col].dt.year == y)
            sub = df_daily[mask]
            if sub.empty:
                continue
            cdd_val = max_cdd(sub[precip_col], soglia)
            cdd_vals.append(cdd_val)
            years.append(y)
        fig, ax = plt.subplots(figsize=(8,4))
        ax.scatter(years, cdd_vals, color='orange', s=20)
        ax.set_title(f'CDD massimo - soglia {soglia} mm - mese: {mesi[mese_idx-1]}')
        ax.set_xlabel('Anno')
        ax.set_ylabel('CDD massimo (giorni secchi)')
        # Format x axis as integer years
        from matplotlib.ticker import MaxNLocator, FuncFormatter
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{int(x)}'))
        if len(years) > 1:
            slope, intercept, *_ = linregress(years, cdd_vals)
            ax.plot(years, [intercept + slope*x for x in years], 'r--', label=f'Trend: {slope:.2f}/anno')
            ax.legend()
        st.pyplot(fig)
    elif analisi == 'Stagionale':
        stagione_idx = st.selectbox('Seleziona la stagione', list(stagioni.items()), format_func=lambda x: x[1])[0]
        cdd_vals = []
        years = []
        for y in range(df_daily[time_col].dt.year.min(), df_daily[time_col].dt.year.max()+1):
            mask = (df_daily[time_col].dt.quarter == stagione_idx) & (df_daily[time_col].dt.year == y)
            sub = df_daily[mask]
            if sub.empty:
                continue
            cdd_val = max_cdd(sub[precip_col], soglia)
            cdd_vals.append(cdd_val)
            years.append(y)
        fig, ax = plt.subplots(figsize=(8,4))
        ax.scatter(years, cdd_vals, color='orange', s=20)
        ax.set_title(f'CDD massimo - soglia {soglia} mm - stagione: {stagioni[stagione_idx]}')
        ax.set_xlabel('Anno')
        ax.set_ylabel('CDD massimo (giorni secchi)')
        from matplotlib.ticker import MaxNLocator, FuncFormatter
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{int(x)}'))
        if len(years) > 1:
            slope, intercept, *_ = linregress(years, cdd_vals)
            ax.plot(years, [intercept + slope*x for x in years], 'r--', label=f'Trend: {slope:.2f}/anno')
            ax.legend()
        st.pyplot(fig)
    else:  # Annuale
        cdd_vals = []
        years = []
        for y in range(df_daily[time_col].dt.year.min(), df_daily[time_col].dt.year.max()+1):
            mask = (df_daily[time_col].dt.year == y)
            sub = df_daily[mask]
            if sub.empty:
                continue
            cdd_val = max_cdd(sub[precip_col], soglia)
            cdd_vals.append(cdd_val)
            years.append(y)
        fig, ax = plt.subplots(figsize=(8,4))
        ax.scatter(years, cdd_vals, color='orange', s=20)
        ax.set_title(f'CDD massimo annuale - soglia {soglia} mm')
        ax.set_xlabel('Anno')
        ax.set_ylabel('CDD massimo (giorni secchi)')
        from matplotlib.ticker import MaxNLocator, FuncFormatter
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{int(x)}'))
        if len(years) > 1:
            slope, intercept, *_ = linregress(years, cdd_vals)
            ax.plot(years, [intercept + slope*x for x in years], 'r--', label=f'Trend: {slope:.2f}/anno')
            ax.legend()
        st.pyplot(fig)
elif tipo_analisi == 'SPI':
    # Visualizzazione SPI
    try:
        station_name, df_spi = read_spi_file(spi_path)
    except Exception as e:
        st.error(f'Errore nel caricamento del file SPI: {e}')
        st.stop()
    st.write(f"**Stazione SPI:** {station_name}")
    spi_col = st.selectbox('Seleziona la scala SPI', ['SPI-1', 'SPI-3', 'SPI-6', 'SPI-9', 'SPI-12'])
    # Escludi valori non validi (-99.00)
    df_spi_valid = df_spi[df_spi[spi_col] != -99.00].copy()
    # Crea colonna data
    df_spi_valid['Data'] = pd.to_datetime({'year': df_spi_valid['Anno'], 'month': df_spi_valid['Mese'], 'day': 1})
    fig, ax = plt.subplots(figsize=(10,4))
    ax.plot(df_spi_valid['Data'], df_spi_valid[spi_col], marker='o', linestyle='-', color='blue')
    ax.axhline(0, color='gray', linestyle='--', lw=1)
    ax.set_title(f'{spi_col} - {station_name}')
    ax.set_xlabel('Data')
    ax.set_ylabel('SPI')
    st.pyplot(fig)

# === Eventi >95° percentile 3h ===
elif tipo_analisi == 'Eventi >95° percentile 3h':
    st.header(f"Eventi di precipitazione >= 95° percentile (cumulate 3h) - {stazione}")
    # Carica dati
    df = pd.read_csv(file_path)
    # Identifica colonne temporali e di precipitazione
    time_col = None
    precip_col = None
    for col in df.columns:
        if 'data' in col.lower():
            time_col = col
        if 'valore' in col.lower():
            precip_col = col
    if time_col and precip_col:
        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
        df_valid = df[df[precip_col] != -999.0].dropna(subset=[time_col, precip_col])
        df_valid = df_valid.sort_values(time_col)
        df_valid = df_valid.set_index(time_col)
        # Resample 3-hourly
        df_3h = df_valid[precip_col].resample('3h').sum()
        # Calcolo 95° percentile escludendo valori <= 25mm (inclusi zeri)
        df_3h_sel = df_3h[(df_3h.notna()) & (df_3h > 10)]
        perc95 = df_3h_sel.quantile(0.95)
        # Trova eventi >= soglia
        eventi = df_3h >= perc95
        # Plot
        fig, ax = plt.subplots(figsize=(12,5))
        ax.plot(df_3h.index, df_3h.values, label='Precipitazione 3h', color='blue')
        ax.scatter(df_3h.index[eventi], df_3h[eventi], color='red', label=f'>= 95° percentile ({perc95:.1f} mm)', zorder=5)
        ax.axhline(perc95, color='red', linestyle='--', label=f'95° percentile ({perc95:.1f} mm)')
        # Calcolo trend sulla frequenza annuale di eventi >= 95° percentile
        freq_annua = df_3h[eventi].groupby(df_3h.index[eventi].year).size()
        anni_freq = freq_annua.index.values
        valori_freq = freq_annua.values
        if len(valori_freq) > 1:
            slope, intercept, *_ = linregress(anni_freq, valori_freq)
            trend_str = f"Trend frequenza: {slope:.2f} eventi/anno"
        else:
            trend_str = ""
        ax.set_xlabel('Data/Ora')
        ax.set_ylabel('Precipitazione 3h (mm)')
        ax.set_title(f'Eventi >= 95° percentile 3h - {stazione}' + (f'\n{trend_str}' if trend_str else ''))
        ax.legend()
        ax.grid(True)
        plt.tight_layout()
        st.pyplot(fig)
        st.write(f"Numero di eventi >= 95° percentile: {eventi.sum()}")
    else:
        st.error("Colonne temporali o di precipitazione non trovate nel file.")
