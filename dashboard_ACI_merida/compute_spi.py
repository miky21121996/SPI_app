import os
import glob
import zipfile
import requests
import numpy as np
import xarray as xr
import geopandas as gpd
import rioxarray
import shapely.geometry as sgeom
from scipy.stats import gamma, norm

# =========================
# CONFIG
# =========================
DATA_PATH = r"T:/Aet/Private/MAP/MPF/WES/00_data/merida/lowres"
START_DATE = "2012-01-01"
END_DATE = "2022-12-31"

# =========================
# Download shapefile Lombardia (ISTAT)
# =========================
def download_lombardia():

    if os.path.exists("lombardia.shp"):
        print("Shapefile Lombardia già presente.")
        return

    print("Scarico shapefile ISTAT...")

    url = "https://www.istat.it/storage/cartografia/confini_amministrativi/non_generalizzati/2023/Limiti01012023.zip"
    zip_path = "confini_istat.zip"
    extract_path = "confini_istat"

    if not os.path.exists(zip_path):
        r = requests.get(url)
        with open(zip_path, "wb") as f:
            f.write(r.content)

    if not os.path.exists(extract_path):
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_path)

    print("Ricerca shapefile delle regioni...")

    regioni = None
    shp_trovato = None

    for root, dirs, files in os.walk(extract_path):
        for file in files:
            if file.lower().endswith(".shp"):
                shp_path = os.path.join(root, file)
                try:
                    gdf = gpd.read_file(shp_path)
                    # Se contiene il campo DEN_REG allora è lo shapefile delle regioni
                    if "DEN_REG" in gdf.columns:
                        print(f"Trovato shapefile regioni in: {shp_path}")
                        regioni = gdf
                        shp_trovato = shp_path
                        break
                except:
                    pass
        if regioni is not None:
            break

    if regioni is None:
        raise FileNotFoundError(
            "Non ho trovato nessuno shapefile contenente il campo 'DEN_REG'. "
            "La struttura ISTAT potrebbe essere cambiata."
        )

    print(f"Trovato shapefile regioni: {shp_trovato}")

    lombardia = regioni[regioni["DEN_REG"] == "Lombardia"]

    if lombardia.empty:
        raise ValueError("Non trovo la regione Lombardia nel file ISTAT.")

    lombardia.to_file("lombardia.shp")

    print("Shapefile Lombardia creato correttamente.")



# =========================
# SPI functions
# =========================
import numpy as np
import xarray as xr
from scipy.stats import gamma, norm
import dask
from dask.diagnostics import ProgressBar

def spi_pixel(ts, scale, verbose=False):
    """
    Calcola lo SPI per una serie temporale 1D (pixel singolo).
    
    Parameters:
        ts: np.array di precipitazioni mensili
        scale: int, finestra in mesi (1,3,6,9,12)
        verbose: bool, True per log di debug
        
    Returns:
        np.array dello stesso shape di ts con SPI (NaN per primi scale-1 valori)
    """
    ts = np.array(ts, dtype=float)
    spi = np.full_like(ts, np.nan)
    
    if np.isnan(ts).all():
        return spi
    
    # 1) Calcolo delle somme cumulative mobili di 'scale' mesi
    cum_precip = np.convolve(ts, np.ones(scale), 'valid')
    
    # 2) Fitting Gamma su tutti i valori cumulati positivi
    valid_vals = cum_precip[cum_precip > 0]
    if len(valid_vals) < 10:
        if verbose:
            print(f"Troppi pochi dati validi ({len(valid_vals)}) per calcolare SPI")
        return spi
    
    try:
        shape, loc, scale_param = gamma.fit(valid_vals, floc=0)
        cdf_vals = gamma.cdf(cum_precip, a=shape, loc=0, scale=scale_param)
        spi_vals = norm.ppf(cdf_vals)
    except Exception as e:
        if verbose:
            print(f"Errore nel fitting: {e}")
        return spi
    
    # 3) Allineamento dei valori: primi scale-1 = NaN
    spi[scale-1:] = spi_vals
    
    if verbose:
        print(f"SPI calcolato per pixel, scale={scale}")
    
    return spi

def compute_spi_xarray(da, scale, verbose=True):
    """
    Calcola SPI per un DataArray xarray 3D (time, lat, lon)
    
    Parameters:
        da: xarray DataArray con dimensioni time, lat, lon
        scale: int, finestra in mesi
        verbose: bool, True per monitorare il progresso
    
    Returns:
        xarray DataArray con SPI calcolato
    """
    
    if verbose:
        print(f"Calcolo SPI-{scale} per DataArray di shape {da.shape}...")
    
    with ProgressBar():
        spi_da = xr.apply_ufunc(
            spi_pixel,
            da,
            kwargs={"scale": scale, "verbose": verbose},
            input_core_dims=[["time"]],
            output_core_dims=[["time"]],
            vectorize=True,
            dask="parallelized",
            output_dtypes=[float],
        )
    
    if verbose:
        print(f"SPI-{scale} completato.")
    
    return spi_da


# =========================
# MAIN
# =========================
def main():

    download_lombardia()

    if os.path.exists("pr_monthly_2012_2022.nc"):
        print("Carico pr_monthly_2012_2022.nc già esistente...")
        pr_monthly = xr.open_dataset("pr_monthly_2012_2022.nc")["tp"]
    else:
        print("Caricamento NetCDF...")
        files = sorted(glob.glob(os.path.join(DATA_PATH, "MERIDA_PREC_*.nc")))
        ds = xr.open_mfdataset(files, combine="by_coords")

        ds = ds.sel(time=slice(START_DATE, END_DATE))
        print("Resampling orario → mensile...")
        pr_monthly = ds["tp"].resample(time="1MS").sum()
        pr_monthly.to_netcdf("pr_monthly_2012_2022.nc")
        print("Salvato pr_monthly_2012_2022.nc")


    # Assicuriamoci che il DataArray abbia CRS e dimensioni spaziali corrette
    pr_monthly = pr_monthly.rio.write_crs("EPSG:4326")
    pr_monthly = pr_monthly.rio.set_spatial_dims(x_dim="lon", y_dim="lat")


    lombardia = gpd.read_file("lombardia.shp")
    # Allineamento CRS
    lombardia = lombardia.to_crs(pr_monthly.rio.crs)

    # Geometria unica della Lombardia (metodo moderno)
    geom = lombardia.geometry.union_all()

    # rioxarray vuole una lista di geometrie in formato geo-interface
    geoms = [geom.__geo_interface__]

    # Clip vero e proprio
    pr_lombardia = pr_monthly.rio.clip(
        geoms,
        lombardia.crs,
        drop=True,
        all_touched=True
    )


    for scale in [1, 3, 6, 9, 12]:
        print(f"Calcolo SPI-{scale} ...")
        spi_da = compute_spi_xarray(pr_lombardia, scale)
        out_file = f"SPI_{scale}.nc"
        spi_da.to_netcdf(out_file)
        print(f"Salvato {out_file}")

    print("TUTTO COMPLETATO.")

if __name__ == "__main__":
    main()
