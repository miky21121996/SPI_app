#!/usr/bin/env python3
"""
Radar DPC GeoTIFF Plotter
- SRI → intensità di pioggia (mm/h)
- VMI → riflettività (dBZ)
- Overlay shapefile province italiane
- Overlay shapefile opere idroelettriche e tracciati A2A
- Supporto animazioni per più timestamp consecutivi
"""

import os
import glob
import re
import numpy as np
import rasterio
from rasterio.warp import transform_bounds
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from mpl_toolkits.basemap import Basemap
from datetime import datetime
import geopandas as gpd
from matplotlib import animation

# === Percorsi shapefile ===
SHAPEFILE_PROVINCE = r"C:\Users\enrico.solazzo\OneDrive - A2A Group\Desktop\qgis\Limiti01012022\Limiti01012022\ProvCM01012022.shp"
SHAPEFILES_OPERE = r"C:\Users\enrico.solazzo\OneDrive - A2A Group\Desktop\qgis\opere_a2a"

# === Funzioni utility ===

def list_products(base_dir="./downloads"):
    products = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    return sorted(products)

def list_files(product, base_dir="./downloads"):
    path = os.path.join(base_dir, product, "**", "*.tif")
    files = sorted(glob.glob(path, recursive=True))
    return files

def parse_timestamp(fname):
    if re.match(r"^\d{12}$", fname):
        return fname
    try:
        dt = datetime.strptime(fname, "%d-%m-%Y-%H-%M")
        return dt.strftime("%Y%m%d%H%M")
    except ValueError:
        pass
    return None

def get_files_with_timestamps(product, base_dir="./downloads"):
    files = list_files(product, base_dir)
    result = []
    for f in files:
        fname = os.path.basename(f).split(".")[0]
        ts = parse_timestamp(fname)
        if ts:
            result.append((f, ts))
    return sorted(result, key=lambda x: x[1])

def get_colormap(product):
    if product == "SRI":
        bounds = [0.2,0.5,1,2,3,4,5,7,10,20,30,50,60,80,100]
        colors_rgb = [
            (0,0,255), (0,90,255), (0,190,255), (0,225,255),
            (0,130,0), (0,155,0), (0,180,0), (0,210,0),
            (0,255,0), (255,255,0), (255,190,0), (255,90,0),
            (180,30,30), (255,80,240), (180,45,180)
        ]
        colors = [(r/255, g/255, b/255, 1) for r,g,b in colors_rgb]
        cmap = ListedColormap(colors)
        norm = BoundaryNorm(bounds, cmap.N)
        label = "Pioggia (mm/h)"

    elif product == "VMI":
        bounds = [-8,-4,0,4,8,12,16,20,24,26,32,36,40,44,48,52,56,60,64]
        colors_rgb = [
            (255, 255, 255), (180, 180, 180), (140, 140, 140),
            (0, 0, 255), (0,90,255), (0,225,255), (0,190,255),
            (0,130,0), (0,155,0), (0,180,0), (0,210,0), (0,255,0),
            (255,255,0), (255,190,0), (255,90,0), (180,30,30),
            (255,80,240), (180,45,180)
        ]
        colors = [(r/255, g/255, b/255, 1) for r,g,b in colors_rgb]
        while len(colors) < len(bounds)-1:
            colors.append(colors[-1])
        cmap = ListedColormap(colors)
        norm = BoundaryNorm(bounds, cmap.N)
        label = "Riflettività (dBZ)"
    else:
        cmap = "jet"
        norm = None
        label = "Valore radar"
    return cmap, norm, label

def plot_geotiff(tif_path, product, title="Radar DPC"):
    with rasterio.open(tif_path) as src:
        bounds = src.bounds
        crs = src.crs
        bounds_wgs84 = transform_bounds(crs, "EPSG:4326",
                                        bounds.left, bounds.bottom,
                                        bounds.right, bounds.top)
        llcrnrlon, llcrnrlat, urcrnrlon, urcrnrlat = bounds_wgs84
        data = src.read(1).astype(float)
        if src.nodata is not None:
            data = np.ma.masked_where(data == src.nodata, data)
        if product == "SRI":
            data = np.ma.masked_where(data < -10, data)

    fig, ax = plt.subplots(figsize=(10, 10))
    m = Basemap(projection="merc",
                llcrnrlon=llcrnrlon, llcrnrlat=llcrnrlat,
                urcrnrlon=urcrnrlon, urcrnrlat=urcrnrlat,
                resolution="i", ax=ax)
    m.drawcoastlines()
    m.drawcountries()
    m.drawparallels(range(-90, 91, 2), labels=[1,0,0,0], fontsize=8)
    m.drawmeridians(range(-180, 181, 2), labels=[0,0,0,1], fontsize=8)

    cmap, norm, label = get_colormap(product)
    im = m.imshow(data, origin="upper", cmap=cmap, norm=norm, zorder=1)

    # Province
    if os.path.exists(SHAPEFILE_PROVINCE):
        try:
            gdf = gpd.read_file(SHAPEFILE_PROVINCE).to_crs("EPSG:4326")
            for _, row in gdf.iterrows():
                geoms = [row.geometry] if row.geometry.geom_type=="Polygon" else row.geometry.geoms
                for geom in geoms:
                    x, y = m(*geom.exterior.xy)
                    ax.plot(x, y, color="black", linewidth=0.5, zorder=2)
        except Exception as e:
            print(f"⚠️ Errore shapefile province: {e}")

    # Opere A2A
    if os.path.exists(SHAPEFILES_OPERE):
        for shp_name, color in [
            ("tracciati_val.shp", "black"),
            ("tracciati_cal.shp", "black"),
            ("tracciati_friuli.shp", "black"),
            ("tracciati_mese.shp", "black")
        ]:
            shp_path = os.path.join(SHAPEFILES_OPERE, shp_name)
            if os.path.exists(shp_path):
                try:
                    gdf = gpd.read_file(shp_path).to_crs("EPSG:4326")
                    for _, row in gdf.iterrows():
                        geom_type = row.geometry.geom_type
                        if geom_type == "Point":
                            x, y = m(row.geometry.x, row.geometry.y)
                            ax.scatter(x, y, s=40, color=color, edgecolors="black", linewidth=0.5, zorder=3)
                        elif geom_type in ["LineString", "LinearRing"]:
                            x, y = m(*row.geometry.xy)
                            ax.plot(x, y, color=color, linewidth=1, zorder=3)
                        elif geom_type == "Polygon":
                            x, y = m(*row.geometry.exterior.xy)
                            ax.plot(x, y, color=color, linewidth=1, zorder=3)
                        elif geom_type == "MultiPolygon":
                            for geom in row.geometry:
                                x, y = m(*geom.exterior.xy)
                                ax.plot(x, y, color=color, linewidth=1, zorder=3)
                except Exception as e:
                    print(f"⚠️ Errore shapefile {shp_name}: {e}")

    plt.title(title)
    plt.colorbar(im, label=label, shrink=0.7)
    plt.show()

def plot_animation(files_with_ts, product, output_file="animation.gif", interval=500):
    fig, ax = plt.subplots(figsize=(10,10))
    ims = []
    for tif_path, ts in files_with_ts:
        with rasterio.open(tif_path) as src:
            bounds = src.bounds
            crs = src.crs
            bounds_wgs84 = transform_bounds(crs, "EPSG:4326",
                                            bounds.left, bounds.bottom,
                                            bounds.right, bounds.top)
            llcrnrlon, llcrnrlat, urcrnrlon, urcrnrlat = bounds_wgs84
            data = src.read(1).astype(float)
            if src.nodata is not None:
                data = np.ma.masked_where(data == src.nodata, data)
            if product=="SRI":
                data = np.ma.masked_where(data < -10, data)
        ax.clear()
        m = Basemap(projection="merc",
                    llcrnrlon=llcrnrlon, llcrnrlat=llcrnrlat,
                    urcrnrlon=urcrnrlon, urcrnrlat=urcrnrlat,
                    resolution="i", ax=ax)
        m.drawcoastlines()
        m.drawcountries()
        m.drawparallels(range(-90,91,2), labels=[1,0,0,0], fontsize=8)
        m.drawmeridians(range(-180,181,2), labels=[0,0,0,1], fontsize=8)
        cmap, norm, label = get_colormap(product)
        im = m.imshow(data, origin="upper", cmap=cmap, norm=norm, zorder=1)
        title = ax.text(0.5,1.05,f"{product} @ {ts}", transform=ax.transAxes, ha="center")
        ims.append([im, title])
    ani = animation.ArtistAnimation(fig, ims, interval=interval, blit=True)
    ani.save(output_file, writer='pillow')
    print(f"✅ Animazione salvata in {output_file}")

def main():
    base_dir = "./downloads"
    products = list_products(base_dir)
    if not products:
        print("⚠️ Nessun prodotto trovato in ./downloads")
        return

    print("\nProdotti disponibili:", ", ".join(products))
    product = input("Inserisci il prodotto (es. VMI, SRI, TEMP): ").strip().upper()
    if product not in products:
        print(f"⚠️ Prodotto {product} non trovato in {base_dir}")
        return

    files_with_ts = get_files_with_timestamps(product, base_dir)
    if not files_with_ts:
        print(f"⚠️ Nessun file .tif valido trovato per {product}")
        return

    timestamp = input("Inserisci il timestamp (YYYYMMDDHHMM), 'ultimo', o intervallo separato da virgola: ").strip().lower()

    if timestamp=="ultimo":
        match, ts = files_with_ts[-1]
        print(f"\n📡 Plotting ultimo file: {match}")
        plot_geotiff(match, product, f"{product} @ {ts}")
    elif "," in timestamp:
        ts_list = [t.strip() for t in timestamp.split(",")]
        selected_files = [(f, ts) for f, ts in files_with_ts if ts in ts_list]
        if not selected_files:
            print("⚠️ Nessun file trovato per i timestamp selezionati")
        else:
            plot_animation(selected_files, product, output_file=f"{product}_anim.gif")
    else:
        match, ts = None, None
        for f, ts_candidate in files_with_ts:
            if ts_candidate==timestamp:
                match, ts = f, ts_candidate
                break
        if not match:
            print(f"⚠️ Nessun file trovato per {product} con timestamp {timestamp}")
        else:
            plot_geotiff(match, product, f"{product} @ {ts}")

if __name__ == "__main__":
    main()
