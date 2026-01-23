import xarray as xr
import numpy as np
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output

# =========================
# Load SPI datasets
# =========================
spi_data = {}
for scale in [1, 3, 6, 9, 12]:
    ds = xr.open_dataset(f"SPI_{scale}.nc")
    # la variabile principale si chiama 'tp'
    spi_data[scale] = ds["tp"]


times = spi_data[1]["time"].values

# =========================
# Colorscale SPI
# =========================
colorscale = [
    [0.0, "#67001f"],
    [0.2, "#b2182b"],
    [0.4, "#ef8a62"],
    [0.5, "#f7f7f7"],
    [0.6, "#67a9cf"],
    [0.8, "#2166ac"],
    [1.0, "#053061"],
]

spi_legend_text = """
SPI ≥ 2.0 : Estremamente umido<br>
1.5 – 1.99 : Molto umido<br>
1.0 – 1.49 : Moderatamente umido<br>
-0.99 – 0.99 : Normale<br>
-1.0 – -1.49 : Moderatamente secco<br>
-1.5 – -1.99 : Molto secco<br>
≤ -2.0 : Siccità estrema
"""

# =========================
# Dash App
# =========================
app = Dash(__name__)

app.layout = html.Div([

    html.H2("SPI Lombardia (2012–2022)"),

    html.Div([
        html.Label("Scala SPI (mesi)"),
        dcc.Dropdown(
            options=[{"label": f"SPI-{s}", "value": s} for s in [1,3,6,9,12]],
            value=3,
            id="scale-dropdown"
        ),
    ], style={"width": "20%"}),

    html.Br(),

    html.Div([
        html.Label("Tempo"),
        dcc.Slider(
            min=0,
            max=len(times)-1,
            step=1,
            value=0,
            id="time-slider",
            marks={i: str(np.datetime_as_string(t, unit="M")) for i, t in enumerate(times[::12])}
        ),
    ], style={"width": "80%"}),

    dcc.Graph(id="spi-map"),

    html.Div([
        html.H4("Classificazione SPI"),
        html.Div(spi_legend_text)
    ])
])

# =========================
# Callback
# =========================
@app.callback(
    Output("spi-map", "figure"),
    Input("scale-dropdown", "value"),
    Input("time-slider", "value")
)
def update_map(scale, t_index):

    da = spi_data[scale].isel(time=t_index)

    fig = go.Figure(data=go.Heatmap(
        z=da.values,
        x=da["lon"].values,
        y=da["lat"].values,
        colorscale=colorscale,
        zmin=-2.5,
        zmax=2.5,
        colorbar=dict(title="SPI")
    ))

    fig.update_layout(
        title=f"SPI-{scale}  {str(da['time'].values)[:10]}",
        xaxis_title="Lon",
        yaxis_title="Lat",
        yaxis_scaleanchor="x"
    )

    return fig

# =========================
# Run
# =========================
if __name__ == "__main__":
    app.run(debug=True)

