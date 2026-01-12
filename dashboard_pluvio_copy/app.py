import os
import pandas as pd
import dash
import numpy as np
from dash import dcc, html, Input, Output
import plotly.express as px
import plotly.graph_objects as go
from waitress import serve

# Percorsi
DATA_FOLDER = r"./cor_files"
CSV_STAZIONI = r"./localizzazione.csv"

# ------------------------
# Lettura CSV coordinate
# ------------------------
stazioni = pd.read_csv(CSV_STAZIONI)

# ------------------------
# Lettura file .dat
# ------------------------
def read_spi_file(filepath):
    rows = []
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Use the filename (without extension) as station name instead of the first line
    nome = os.path.splitext(os.path.basename(filepath))[0]
    for l in lines[1:]:
        parts = l.split()
        #print(parts)
        year = int(parts[0])
        month = int(parts[1])
        spi = list(map(float, parts[2:]))

        rows.append({
            "date": pd.Timestamp(year, month, 1),
            "SPI_1": spi[0],
            "SPI_3": spi[1],
            "SPI_6": spi[2],
            "SPI_9": spi[3],
            "SPI_12": spi[4],
        })

    df = pd.DataFrame(rows)
    return nome, df

spi_data = {}
for file in os.listdir(DATA_FOLDER):
    if file.endswith(".dat"):
        name, df = read_spi_file(os.path.join(DATA_FOLDER, file))
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
    df = spi_data[station]

    if df is None or df.empty:
        return go.Figure()

    # Trova il primo indice con valore diverso da -99 e plotta a partire da lì
    mask = df[spi_type].to_numpy() != -99
    if not mask.any():
        return go.Figure()
    start_pos = np.where(mask)[0][0]
    df_plot = df.iloc[start_pos:]

    fig = px.line(df_plot, x="date", y=spi_type,
                  title=f"{station} – {spi_type}")
    fig.update_yaxes(title="SPI Index")
    fig.update_xaxes(title="Data")
    return fig


if __name__ == "__main__":
    print("Entrato nel main, avvio server...")
    serve(app.server, host="0.0.0.0", port=8050)

