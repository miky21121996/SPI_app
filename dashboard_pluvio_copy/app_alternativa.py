import os
import pandas as pd
import dash
import numpy as np
from dash import dcc, html, Input, Output
import plotly.express as px
import plotly.graph_objects as go
from waitress import serve
from scipy.stats import gamma, norm

# ------------------------
# Percorsi
# ------------------------
DATA_FOLDER = r"./cor_files"
CSV_STAZIONI = r"./localizzazione.csv"

# ------------------------
# Lettura CSV coordinate
# ------------------------
stazioni = pd.read_csv(CSV_STAZIONI)

# ------------------------
# Funzione calcolo SPI
# ------------------------
def compute_spi(df, scale):
    """Calcola SPI per una serie mensile con finestra scale"""
    spi = pd.Series(index=df.index, dtype=float)
    rolling_sum = df['Precipitazione'].rolling(window=scale, min_periods=scale).sum()
    
    for month in range(1, 13):
        idx = df.index[df['Mese'] == month]
        vals = rolling_sum.loc[idx].dropna()
        if len(vals) < 2:
            spi.loc[idx] = np.nan
            continue
        # Gamma fit: tutti i valori > 0
        vals = vals.clip(lower=0.01)
        fit_alpha, fit_loc, fit_beta = gamma.fit(vals, floc=0)
        cdf_vals = gamma.cdf(rolling_sum.loc[idx].clip(lower=0.01), fit_alpha, loc=fit_loc, scale=fit_beta)
        spi.loc[idx] = norm.ppf(cdf_vals)
    return spi
# ------------------------
# Lettura file .cor e calcolo SPI
# ------------------------
def read_cor_file(filepath):
    rows = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Salta la prima riga: nome stazione
    for l in lines[1:]:
        parts = l.strip().split()
        if len(parts) < 3:
            continue
        year, month, prec = int(parts[0]), int(parts[1]), float(parts[2])
        if prec == -99:
            prec = np.nan
        rows.append({"Anno": year, "Mese": month, "Precipitazione": prec})

    df = pd.DataFrame(rows)
    # Ora possiamo costruire le date senza problemi
    df['Data'] = pd.to_datetime(dict(year=df['Anno'], month=df['Mese'], day=1))
    df = df.sort_values('Data').reset_index(drop=True)

    # Calcola SPI
    df['SPI_1'] = compute_spi(df, 1)
    df['SPI_3'] = compute_spi(df, 3)
    df['SPI_6'] = compute_spi(df, 6)
    df['SPI_9'] = compute_spi(df, 9)
    df['SPI_12'] = compute_spi(df, 12)

    return df


# Carica tutti i file .cor
spi_data = {}
for file in os.listdir(DATA_FOLDER):
    if file.endswith(".cor"):
        name = os.path.splitext(file)[0]
        df = read_cor_file(os.path.join(DATA_FOLDER, file))
        spi_data[name] = df

# ------------------------
# App Dash
# ------------------------
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H2("SPI Lombardia – Dashboard Interattiva"),

    dcc.Dropdown(
        id="spi-selector",
        options=[
            {"label": "SPI 1 mese", "value": "SPI_1"},
            {"label": "SPI 3 mesi", "value": "SPI_3"},
            {"label": "SPI 6 mesi", "value": "SPI_6"},
            {"label": "SPI 9 mesi", "value": "SPI_9"},
            {"label": "SPI 12 mesi", "value": "SPI_12"},
        ],
        value="SPI_3",
        clearable=False
    ),

    dcc.Graph(id="map"),
    dcc.Graph(id="spi-plot")
])

# ------------------------
# Mappa
# ------------------------
@app.callback(
    Output("map", "figure"),
    Input("spi-selector", "value")
)
def update_map(spi_type):
    fig = px.scatter_mapbox(
        stazioni,
        lat="Latitudine",
        lon="Longitudine",
        hover_name="Località",
        zoom=7,
        height=450
    )
    fig.update_layout(mapbox_style="open-street-map")
    return fig

# ------------------------
# Plot SPI
# ------------------------
@app.callback(
    Output("spi-plot", "figure"),
    Input("map", "clickData"),
    Input("spi-selector", "value")
)
def update_spi_plot(clickData, spi_type):
    if clickData is None:
        return go.Figure()

    station = clickData["points"][0]["hovertext"]
    df = spi_data.get(station, None)

    if df is None or df.empty:
        return go.Figure()

    df_plot = df.dropna(subset=[spi_type])

    fig = px.line(df_plot, x="Data", y=spi_type,
                  title=f"{station} – {spi_type}")
    fig.update_yaxes(title="SPI Index")
    fig.update_xaxes(title="Data")
    return fig

# ------------------------
if __name__ == "__main__":
    print("Entrato nel main, avvio server...")
    serve(app.server, host="0.0.0.0", port=8050)
