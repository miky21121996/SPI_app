# Module of the DELFI project to model underground temperature from atmospheric variables
# @jil.etienne@a2a.it

# INPUT DATA
# -> Surface coverage properties 


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
import warnings
import pprint
import xarray as xr
import folium as folium
from folium.plugins import MarkerCluster, BeautifyIcon
import rasterio
from shapely.geometry import box
from rasterio.warp import calculate_default_transform, reproject, Resampling



#%%

def plot_land_cover_and_group(raster_path, save=True):
    """
    Plot a raster file with a background map using Cartopy and rasterio.
    
    Parameters:
    raster_path (str): Path to the raster file (e.g., .tif or .nc).
    """

    # ------------ LOAD DATA ---------------

     # Open the raster file
    with rasterio.open(raster_path) as src:
     
        unique_values = np.unique(src.read(1))   

        # open legend (.txt) and load the data as pandas DataFrame
        legend_path = "CLC2018_CLC2018_V2018_20_QGIS.txt"
        legend_df = pd.DataFrame(columns=["code","R","G","B","trasparency" , "CLC code", 'description'])
        # open the file and read it line by line
        with open(legend_path, 'r') as f: 
            for i,line in enumerate(f):
                if i<2:
                    continue
                values = line.split(sep=" ", maxsplit=6)
                # if description more than 30 char, insert a \n
                if len(values[6])>47:
                    values[6] = values[6][:47] + "\n" + values[6][47:]
                legend_df = legend_df._append({
                        "code": int(values[0]),
                        "R": int(values[1]),
                        "G": int(values[2]),
                        "B": int(values[3]),
                        "trasparency": float(values[4]),
                        "CLC code": int(values[5]),
                        'description': values[6][2:-1]
                    }, ignore_index=True)
        legend_df.set_index("code", inplace=True)
        legend_df = legend_df.astype({"R": float, "G": float, "B": float, "trasparency": float, "CLC code": int})

        # drop rows not with a code in unique_values
        legend_df = legend_df[legend_df.index.isin(unique_values)]

        # ------------ PLOT ORIGINAL RASTER ---------------

        # create a colormap dictionary from the RGB columns in legend, with the LCL code as key
        colormap = {-128: (1, 1, 1, 1)}  # Initialize with a default color for -128
        for idx, row in legend_df.iterrows():
            code = idx
            r = row["R"]/255
            g = row["G"]/255
            b = row["B"]/255
            a = row["trasparency"]/255
            colormap[code] = (r, g, b, a)

        # Create a ListedColormap and BoundaryNorm
        cmap = mcolors.ListedColormap([colormap[val] for val in unique_values])
        norm = mcolors.BoundaryNorm(boundaries=np.append(unique_values, unique_values[-1] + 1), ncolors=len(unique_values))

        # Reproject the raster to EPSG:4326
        dst_crs = 'EPSG:4326'
        transform, width, height = calculate_default_transform(src.crs, dst_crs, src.width, src.height, *src.bounds)
        kwargs = src.meta.copy()
        kwargs.update({'crs': dst_crs,'transform': transform,'width': width,'height': height})
        
        with rasterio.MemoryFile() as memfile:
            with memfile.open(**kwargs) as dst:
                reproject(
                    source=rasterio.band(src, 1),
                    destination=rasterio.band(dst, 1),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.nearest)
                
                # Read the reprojected raster data
                raster_data = dst.read(1)
                extent = [dst.bounds.left, dst.bounds.right, dst.bounds.bottom, dst.bounds.top]

        # change 0 introduced by reprojection to -128
        raster_data[raster_data == 0] = -128
                      
        # Create a figure and axis with Cartopy
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw={'projection': ccrs.PlateCarree()})
        
        # Plot the raster data with the discrete colormap
        img = ax.imshow(raster_data, extent=extent, transform=ccrs.PlateCarree(), cmap=cmap, norm=norm, alpha=0.7, origin='upper')
        
        # add lat, lon
        gl = ax.gridlines(draw_labels=True, alpha=0.8, linestyle='-', color='k')
        gl.xlocator = MultipleLocator(0.2)
        gl.ylocator = MultipleLocator(0.2)
        gl.xformatter = LONGITUDE_FORMATTER
        gl.yformatter = LATITUDE_FORMATTER

        # add a custom legend, with a patch of color for each element in te dict colormap
        legend_elements = [mpatches.Patch(color=mcolors.to_hex(value), label=f'{legend_df.loc[key, 'CLC code']} {legend_df.loc[key, 'description']}') for key, value in colormap.items() if key != -128]
        ax.legend(handles=legend_elements, loc='upper left', title='Land Cover Codes', fontsize='small', title_fontsize='medium', ncols=2, bbox_to_anchor=(0.05, -0.05), borderaxespad=0.)
        
        # Set the title and labels
        ax.set_title('Reprojected Raster Plot')
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        
        # Show the plot
        plt.show()

        # --------- GROUP BY LARGER GROUPS ------------------

        data_grouped = [[1, 204, 0, 0, 255, 'asphalt'],
                        [2, 242, 166, 77, 255, 'bare soil'],
                        [3, 166, 242, 0, 255, 'soil with grass or cultures'],
                        [4, 0, 166, 0, 255, 'forest and shrubland'],
                        [5, 0, 204, 242, 255, 'water body']]
        legend_df_grouped = pd.DataFrame(columns=["group code","R","G","B","trasparency" ,'description'], data=data_grouped)    
        legend_df_grouped.set_index("group code", inplace=True)

        # grouping scheme for the CLC codes
        grouping_scheme = {
            1: {111, 112, 121, 122, 124, 142}, # asphalt 
            2: {131, 133}, # bare soil
            3: {141, 211, 213, 222, 231, 241, 242, 243}, # soil with grass or cultures
            4: {311, 312, 313, 324}, # forest and shrubland
            5: {511, 512}, # water body
        }

        # copy the raster and change the values to the group code
        raster_data_grouped = raster_data.copy()
        for group_code, clc_codes in grouping_scheme.items():
            for clc_code in clc_codes:
                original_code = legend_df[legend_df['CLC code'] == clc_code].index[0]
                raster_data_grouped[raster_data == original_code] = group_code

        unique_values_grouped = np.unique(raster_data_grouped)
        
        # Create a colormap dictionary from the RGB columns in legend, with the group code as key
        colormap_grouped = {-128: (1, 1, 1, 1)}  # Initialize with a default color for -128
        for idx, row in legend_df_grouped.iterrows():
            code = idx
            r = row["R"]/255
            g = row["G"]/255
            b = row["B"]/255
            a = row["trasparency"]/255
            colormap_grouped[code] = (r, g, b, a)
        
        # Create a ListedColormap and BoundaryNorm
        cmap_grouped = mcolors.ListedColormap([colormap_grouped[val] for val in unique_values_grouped])
        norm_grouped = mcolors.BoundaryNorm(boundaries=np.append(unique_values_grouped, unique_values_grouped[-1] + 1), ncolors=len(unique_values_grouped))

        # Create a figure and axis with Cartopy
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw={'projection': ccrs.PlateCarree()})
        
        # Plot the raster data with the discrete colormap
        img = ax.imshow(raster_data_grouped, extent=extent, transform=ccrs.PlateCarree(), cmap=cmap_grouped, norm=norm_grouped, alpha=0.7, origin='upper')
        
        # add lat, lon
        gl = ax.gridlines(draw_labels=True, alpha=0.8, linestyle='-', color='k')
        gl.xlocator = MultipleLocator(0.2)
        gl.ylocator = MultipleLocator(0.2)
        gl.xformatter = LONGITUDE_FORMATTER
        gl.yformatter = LATITUDE_FORMATTER

        # add a custom legend, with a patch of color for each element in te dict colormap
        legend_elements = [mpatches.Patch(color=mcolors.to_hex(value), label=f'{key} {legend_df_grouped.loc[key, 'description']}') for key, value in colormap_grouped.items() if key != -128]
        ax.legend(handles=legend_elements, loc='upper left', title='Custom Land Cover Codes', fontsize='small', title_fontsize='medium', ncols=5, bbox_to_anchor=(0.02, -0.05), borderaxespad=0.)
        
        # Set the title and labels
        ax.set_title('Reprojected Raster Plot')
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        
        # Show the plot
        plt.show()

        if save:
            # save the new raster and legend to a new file
            new_raster_path = raster_path.replace('.tif', '_grouped.tif')
            with rasterio.open(new_raster_path, 'w', **kwargs) as dst:
                dst.write(raster_data_grouped.astype(np.uint8), 1)
                dst.write_colormap(1, colormap_grouped)
                dst.update_tags(1, description='Custom Land Cover Codes')
            
            print(f"Grouped raster saved to {new_raster_path}")

            # save the legend to a new file
            new_legend_path = raster_path.replace('.tif', '_grouped_legend.txt')
            legend_df_grouped.to_csv(new_legend_path, sep=" ", header=False, index=True)
            print(f"Grouped legend saved to {new_legend_path}")
        
    return None

#%%

def tif_to_netcdf(tif_file, netcdf_file):
    """
    Load a raster .tif file, compute latitude and longitude arrays, and save the data to a NetCDF file.

    Parameters:
        tif_file (str): Path to the input .tif file.
        netcdf_file (str): Path to the output NetCDF file.
    """
    # Open the .tif file using rasterio
    with rasterio.open(tif_file) as src:
        # Read the data
        data = src.read(1)  # Read the first (and only) band
        nodata = src.nodata  # Get the nodata value
        transform = src.transform  # Get the affine transform
        width = src.width
        height = src.height

        # Mask nodata values
        data = np.where(data == nodata, np.nan, data)

        # Compute longitude and latitude arrays
        # The transform provides the top-left corner and pixel size
        lon = np.arange(width) * transform[0] + transform[2]
        lat = np.arange(height) * transform[4] + transform[5]

        # Adjust latitude to be in descending order (if necessary)
        if transform[4] < 0:  # Negative pixel size in y-direction
            lat = lat[::-1]
            data = data[::-1, :]  # Flip the data along the latitude axis

    # Create an xarray Dataset
    ds = xr.Dataset(
        {
            "land_cover_type": (["lat", "lon"], data)
        },
        coords={
            "lat": lat,
            "lon": lon
        },
        attrs={
            "description": "Land cover type data from raster .tif file",
            "nodata_value": nodata
        }
    )

    # Save the dataset to a NetCDF file
    ds.to_netcdf(netcdf_file, format="NETCDF4")
    print(f"NetCDF file saved to {netcdf_file}")

    return ds

#%% 


#%%

# Uncomment to plot the original land cover dataset and compute the new grouping
# plot_land_cover_and_group("CLC_1_CORINE_2018_MILANO.tif", save=True)

# uncomment to convert the .tif into a .netCDF
land_cover = tif_to_netcdf("CLC_1_CORINE_2018_MILANO_grouped.tif", "land_cover_grouped.nc")
display(land_cover)
# %%
