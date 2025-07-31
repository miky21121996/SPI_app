# app.py
import streamlit as st
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import os
import datetime as dt

# --- Configurazione e Percorsi ---

# Imposta il layout della pagina per utilizzare l'intera larghezza
st.set_page_config(
    page_title="Dashboard Ondate di Calore Italia",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Percorsi ai dati generati dallo script heatwave_forecast.py
# Questi percorsi sono relativi alla directory in cui si trova app.py
OUTPUT_DIR = "heatwave_forecast_output"
CUMULATIVE_DATA_PATH = os.path.join(OUTPUT_DIR, "all_heatwave_data.csv")
# Assicurati che questi percorsi siano corretti per la tua configurazione locale
# Sono hardcoded qui per semplicità basata sul tuo percorso fornito.
SHAPEFILE_PATH = r'C:\Users\enrico.solazzo\OneDrive - A2A Group\Desktop\qgis\Limiti01012022\Limiti01012022\ProvCM01012022\ProvCM01012022_WGS84.shp'
COORDINATES_PATH = r'C:\Users\enrico.solazzo\OneDrive - A2A Group\Desktop\forecast\ondate di calore\capoluoghi_provincia_coordinate.csv'

# Impostazioni colori e descrizioni (devono corrispondere a quelle dello script principale)
colori = {
    1: 'deepskyblue',      # 1 - Malessere debole
    2: 'green',            # 2 - Malessere moderato
    3: 'yellow',           # 3 - Malessere generalizzato
    4: 'orange',           # 4 - Forte malessere
    5: 'red'               # 5 - Rischio colpi di calore
}
descrizioni = {
    1: '1 - Malessere debole (Humidex 29-33)',
    2: '2 - Malessere moderato (Humidex 34-38)',
    3: '3 - Malessere generalizzato (Humidex 39-44)',
    4: '4 - Forte malessere (Humidex 45-53)',
    5: '5 - Rischio colpi di calore (Humidex 54+)'
}

@st.cache_data # Memorizza i dati nella cache per non ricaricarli ad ogni interazione
def load_data():
    """Carica i dati cumulativi delle ondate di calore."""
    print(f"DEBUG app.py: Trying to load data from: {CUMULATIVE_DATA_PATH}")
    if os.path.exists(CUMULATIVE_DATA_PATH):
        print(f"DEBUG app.py: File found: {CUMULATIVE_DATA_PATH}")
        try:
            df = pd.read_csv(CUMULATIVE_DATA_PATH)
            print(f"DEBUG app.py: DataFrame loaded with {len(df)} rows.")
            if df.empty:
                print("DEBUG app.py: DataFrame is empty after loading CSV.")
                st.warning("Il file dati cumulativi è vuoto. Assicurati che lo script `heatwave_forecast.py` abbia generato dati validi.")
                return pd.DataFrame()

            # Convert columns to datetime, coercing errors to NaT
            # 'forecast_day' should be convertible as YYYY-MM-DD
            # 'max_time' might contain NaT if no max time found
            df['max_time'] = pd.to_datetime(df['max_time'], errors='coerce')
            df['forecast_day'] = pd.to_datetime(df['forecast_day'], errors='coerce')

            # Debugging: Check for NaNs immediately after conversion
            print(f"DEBUG app.py: NaNs in 'max_ondata_calore' after initial load: {df['max_ondata_calore'].isnull().sum()}")
            print(f"DEBUG app.py: NaNs in 'lat' after initial load: {df['lat'].isnull().sum()}")
            print(f"DEBUG app.py: NaNs in 'lon' after initial load: {df['lon'].isnull().sum()}")
            print(f"DEBUG app.py: NaNs in 'forecast_day' after initial load: {df['forecast_day'].isnull().sum()}")


            # Drop rows where critical columns for plotting are NaN (after conversion)
            original_rows = len(df)
            df = df.dropna(subset=['lat', 'lon', 'max_ondata_calore', 'forecast_day'])
            if len(df) < original_rows:
                print(f"DEBUG app.py: Dropped {original_rows - len(df)} rows with NaN in critical columns.")
            if df.empty:
                print("DEBUG app.py: DataFrame became empty after dropping NaNs. This means all rows had missing critical data.")
                st.warning("Nessun dato valido rimasto dopo la pulizia. Controlla il contenuto del CSV.")
                return pd.DataFrame()

            print(f"DEBUG app.py: DataFrame ready for use with {len(df)} valid rows.")
            return df
        except Exception as e:
            print(f"DEBUG app.py: Error reading or processing CSV: {e}")
            st.error(f"Errore nel caricamento o nell'elaborazione del file cumulativo: {e}. Controlla il formato del CSV.")
            return pd.DataFrame()
    else:
        print(f"DEBUG app.py: File NOT found: {CUMULATIVE_DATA_PATH}")
        st.warning(f"File dati cumulativi non trovato: `{CUMULATIVE_DATA_PATH}`. Eseguire lo script `heatwave_forecast.py` per generare i dati.")
    return pd.DataFrame()

@st.cache_data
def load_geodata():
    """Carica lo shapefile delle province e le coordinate dei comuni."""
    province = None
    try:
        if os.path.exists(SHAPEFILE_PATH):
            province = gpd.read_file(SHAPEFILE_PATH)
            province = province.to_crs(epsg=4326)
            print(f"DEBUG app.py: Province shapefile loaded from {SHAPEFILE_PATH}")
        else:
            print(f"DEBUG app.py: Province shapefile NOT found at {SHAPEFILE_PATH}")
            st.warning(f"Shapefile province non trovato a: `{SHAPEFILE_PATH}`. Le mappe non mostreranno i confini delle province.")
    except Exception as e:
        print(f"DEBUG app.py: Error loading province shapefile: {e}")
        st.error(f"Errore nel caricamento dello shapefile: {e}. Le mappe non saranno disponibili.")

    comuni_coords = None
    try:
        if os.path.exists(COORDINATES_PATH):
            comuni_coords = pd.read_csv(COORDINATES_PATH)
            print(f"DEBUG app.py: Comuni coordinates loaded from {COORDINATES_PATH}")
        else:
            print(f"DEBUG app.py: Comuni coordinates NOT found at {COORDINATES_PATH}")
            st.warning(f"File coordinate comuni non trovato a: `{COORDINATES_PATH}`. Alcune funzionalità potrebbero essere limitate.")
    except Exception as e:
        print(f"DEBUG app.py: Error loading comuni coordinates: {e}")
        st.error(f"Errore nel caricamento del file coordinate comuni: {e}.")

    return province, comuni_coords

df_all_data = load_data()
province_gdf, comuni_coords_df = load_geodata()

# --- Titolo e Descrizione Dashboard ---
st.title("☀️ Dashboard Previsioni Ondate di Calore in Italia")
st.markdown("""
Questa dashboard mostra le previsioni giornaliere dell'indice di calore (Humidex) massimo per i capoluoghi di provincia italiani.
""")

# --- Controlli Sidebar ---
st.sidebar.header("Impostazioni")

if not df_all_data.empty:
    available_dates = sorted(df_all_data['forecast_day'].unique(), reverse=True)
    if not available_dates:
        st.info("Nessuna data di previsione valida trovata nei dati.")
        selected_date = None # Imposta selected_date a None se non ci sono date
    else:
        # Default to the most recent date available
        default_date = available_dates[0]
        selected_date = st.sidebar.selectbox(
            "Seleziona la Data di Previsione",
            options=available_dates,
            index=0,
            format_func=lambda x: x.strftime('%Y-%m-%d')
        )
        st.sidebar.markdown(f"Dati aggiornati al: **{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}**")

        df_selected_day = df_all_data[df_all_data['forecast_day'] == selected_date].copy()

        # --- Visualizzazione Dati Principale ---
        st.header(f"Previsione per il {selected_date.strftime('%Y-%m-%d')}")

        tab1, tab2 = st.tabs(["Mappa Interattiva", "Dati Tabellari e Riepilogo"])

        with tab1:
            if province_gdf is None:
                st.info("Impossibile mostrare la mappa senza lo shapefile delle province.")
            elif df_selected_day.empty:
                st.info("Nessun dato di ondata di calore disponibile per la data selezionata per la mappa.")
            else:
                st.subheader("Mappa del Livello Massimo di Ondata di Calore")

                fig, ax = plt.subplots(figsize=(12, 14))

                # Plot province boundaries
                if province_gdf is not None:
                    province_gdf.boundary.plot(ax=ax, linewidth=0.8, edgecolor='grey', zorder=0)

                # Create a "fake" legend for all possible levels
                for livello in sorted(colori.keys()):
                    ax.scatter([], [],
                               color=colori[livello],
                               edgecolor='black',
                               linewidth=0.5,
                               s=100,
                               label=descrizioni[livello])

                # Plot points colored by heatwave level
                gdf_points = gpd.GeoDataFrame(
                    df_selected_day,
                    geometry=gpd.points_from_xy(df_selected_day.lon, df_selected_day.lat),
                    crs='EPSG:4326'
                )

                for livello in sorted(colori.keys()):
                    subset = gdf_points[gdf_points['max_ondata_calore'] == livello]
                    if not subset.empty:
                        subset.plot(
                            ax=ax,
                            color=colori[livello],
                            markersize=180,
                            edgecolor='black',
                            linewidth=0.5,
                            zorder=3
                        )

                # Automatic zoom con buffer
                if not gdf_points.empty:
                    minx, miny, maxx, maxy = gdf_points.total_bounds
                    ax.set_xlim(minx - 1, maxx + 1)
                    ax.set_ylim(miny - 1, maxy + 1)
                else: # Default Italy view
                    ax.set_xlim(6, 19)
                    ax.set_ylim(35, 48)

                ax.legend(
                    title='Livello Ondata Calore (Humidex)',
                    loc='upper left',
                    fontsize=10,
                    title_fontsize=11,
                    frameon=True,
                    facecolor='white'
                )

                ax.set_title(f'Livello Massimo di Ondata di Calore per Capoluogo ({selected_date.strftime("%Y-%m-%d")})', fontsize=16, pad=20)
                ax.set_axis_off()

                st.pyplot(fig) # Mostra la figura di Matplotlib in Streamlit

                # Aggiungi un pulsante per scaricare la mappa del giorno selezionato
                map_filename = os.path.join(OUTPUT_DIR, f"mappa_humidex_{selected_date.strftime('%Y%m%d')}.png")
                if os.path.exists(map_filename):
                    with open(map_filename, "rb") as file:
                        btn = st.download_button(
                            label=f"Scarica Mappa {selected_date.strftime('%Y-%m-%d')}",
                            data=file.read(),
                            file_name=f"mappa_humidex_{selected_date.strftime('%Y%m%d')}.png",
                            mime="image/png"
                        )
                else:
                    st.info(f"Mappa PNG per il {selected_date.strftime('%Y-%m-%d')} non disponibile per il download.")


        with tab2:
            st.subheader("Dati Dettagliati per il Giorno Selezionato")
            if df_selected_day.empty:
                st.info("Nessun dato disponibile per la data selezionata.")
            else:
                # Tabella dei dati
                st.dataframe(df_selected_day[['comune', 'max_ondata_calore', 'max_time', 'lat', 'lon']].sort_values(by='max_ondata_calore', ascending=False).rename(columns={
                    'comune': 'Comune',
                    'max_ondata_calore': 'Livello Max',
                    'max_time': 'Ora Max',
                    'lat': 'Latitudine',
                    'lon': 'Longitudine'
                }))

                # Riepilogo per livello
                st.subheader("Riepilogo Livelli di Allerta")
                level_counts = df_selected_day['max_ondata_calore'].value_counts().sort_index().reset_index()
                level_counts.columns = ['Livello', 'Numero Comuni']
                level_counts['Descrizione'] = level_counts['Livello'].map(descrizioni)
                st.table(level_counts)

                # Dati più alti
                st.subheader("Top 5 Comuni con Livelli di Allerta Più Alti")
                top_5 = df_selected_day.sort_values(by='max_ondata_calore', ascending=False).head(5)
                if not top_5.empty:
                    st.dataframe(top_5[['comune', 'max_ondata_calore', 'max_time']].rename(columns={
                        'comune': 'Comune',
                        'max_ondata_calore': 'Livello Max',
                        'max_time': 'Ora Max'
                    }))
                else:
                    st.info("Nessun comune con livello di allerta elevato trovato.")

                # Aggiungi un pulsante per scaricare il CSV completo dei dati
                st.subheader("Scarica Dati")
                # Prepara il CSV da scaricare (solo i dati del giorno selezionato)
                csv_download_data_day = df_selected_day.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label=f"Scarica Dati CSV per {selected_date.strftime('%Y-%m-%d')}",
                    data=csv_download_data_day,
                    file_name=f"ondata_calore_{selected_date.strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    help="Scarica il file CSV con i dati di tutti i capoluoghi per la data selezionata."
                )

                # Pulsante per scaricare il CSV cumulativo completo
                if os.path.exists(CUMULATIVE_DATA_PATH):
                    with open(CUMULATIVE_DATA_PATH, "rb") as file:
                        st.download_button(
                            label="Scarica Dati CSV Storici Completi",
                            data=file.read(),
                            file_name="all_heatwave_data_cumulative.csv",
                            mime="text/csv",
                            help="Scarica il file CSV contenente tutti i dati storici delle previsioni."
                        )

else:
    st.info("Nessun dato di previsione caricato. Assicurati che lo script `heatwave_forecast.py` sia stato eseguito e abbia generato il file `all_heatwave_data.csv` nella cartella `heatwave_forecast_output`.")

st.sidebar.markdown("---")
st.sidebar.header("Informazioni")
st.sidebar.info("Questa dashboard visualizza previsioni basate sui modelli meteorologici disponibili tramite Open-Meteo API.")
st.sidebar.markdown("Per informazioni o supporto, contatta il responsabile.")