#%%

from google.cloud import bigquery
from google.cloud import storage
import numpy as np
import pandas as pd
import geopandas as gpd
import datetime as dt
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.ticker import ScalarFormatter, MultipleLocator
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from decimal import *
from calendar import monthrange, month_abbr
import cartopy as ctp
import cartopy.crs as ccrs
import cartopy.io.img_tiles as cimgt
from cartopy.io import shapereader
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import io
import base64
import pygrib
import math
import netCDF4
import pytz
import cmocean
import seaborn as sns
from sklearn.metrics import mean_squared_error, confusion_matrix
import matplotlib.dates as mdates
from pytz import timezone, all_timezones
from scipy.stats import spearmanr, pearsonr, linregress
import scipy.signal as signal
from scipy.interpolate import interp1d
from taylor_diagram import TaylorDiagram
import statsmodels.api as sm
import os
import difflib
import folium
from folium.plugins import MarkerCluster, BeautifyIcon
from PIL import Image, ImageDraw
import warnings
import properscoring as ps
import numba
import pprint
from geopy.distance import geodesic
import xarray as xr
from statsmodels.tsa.arima.model import ARIMA

#%%

def get_timeseries_load(fname):

    # Load the dataset
    dataset = pd.read_csv(fname)

    # Convert the 'orario' column to datetime
    dataset['orario'] = pd.to_datetime(dataset['orario'], utc=True)

    # change names
    dataset.rename(columns={'orario':'VALID_DATE', 'load_mwh':'LOAD'}, inplace=True)

    return dataset


def plot_autocorrelation(timeseries, lags=[-240, 240]):
    """
    Plots the autocorrelation of a time series

    Parameters
    ----------
    timeseries : pandas.Series
        Time series to be analyzed
    lags : list
        List of lags to be plotted. Default is [-40, 40]
    """

    autocorr = pd.DataFrame({'lag': range(lags[0], lags[1]+1), 'autocorr': [timeseries.autocorr(lag) for lag in range(lags[0], lags[1]+1)]})

    fig, ax = plt.subplots()
    ax.plot(autocorr['lag'], autocorr['autocorr'])
    ax.set_xlabel('Lag (hours)')
    ax.set_ylabel('Autocorrelation')
    ax.set_title('Autocorrelation of the time series')

    plt.show()
    plt.close()

    return autocorr

# %%


load_2023 = get_timeseries_load('load_CP_MI_2023.csv')
print(load_2023.head(20))

#plot_autocorrelation(load_2023['LOAD'], lags=[-480, 480])
# take AR lag param to be 300

# fit ARIMA model without moving average
model = ARIMA(load_2023['LOAD'], order=(24, 1, 240))

model_fit = model.fit()
print(model_fit.summary())

# predict the next 10 days
forecast = model_fit.forecast(steps=240)
print(forecast)



# %%

# plot the component of the model as a timeseries
fig, ax = plt.subplots(2,1,figsize=(10, 6), sharex=True)
ax[0].plot(load_2023['VALID_DATE'], load_2023['LOAD'], label='Load', linewidth=0.5)
ax[0].plot(load_2023['VALID_DATE'], model_fit.fittedvalues, color='red', label='Fitted', linewidth=0.5)

# plot rolling average
ax[1].plot(load_2023['VALID_DATE'], load_2023['LOAD'].rolling(24).mean(), label='Load', linewidth=0.5)
ax[1].plot(load_2023['VALID_DATE'], model_fit.fittedvalues.rolling(24).mean(), color='red', label='Fitted', linewidth=0.5)

# plot forecast
ax[0].plot(load_2023['VALID_DATE'].iloc[-1] + pd.to_timedelta(np.arange(1, 241), unit='H'), forecast, color='green', label='Forecast', linewidth=0.5)
ax[1].plot(load_2023['VALID_DATE'].iloc[-1] + pd.to_timedelta(np.arange(1, 241), unit='H'), forecast.rolling(24).mean(), color='green', label='Forecast', linewidth=0.5)

ax[1].set_xlabel('Date')
ax[1].set_ylabel('Load (MWh)')
ax[0].set_title('Original and Fitted Load')
ax[0].legend()
plt.show()
plt.close()


# %%
