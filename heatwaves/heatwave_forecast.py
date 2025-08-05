# -*- coding: utf-8 -*-
"""
Created on Thu Jun 26 12:18:04 2025

@author: enrico.solazzo
"""

# -*- coding: utf-8 -*-
import datetime as dt
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import geopandas as gpd
from open_meteo import OpenMeteo, correct_gmt, add_time_details
import argparse
import os
import sys

def add_humidex(df):
    """Calculates the Humidex and heatwave level based on temperature and relative humidity."""
    label_temperature = [i for i in df.columns if 'temperature_2m' in i]
    label_relativehumidity = [i for i in df.columns if 'relative_humidity_2m' in i]

    if not label_temperature or not label_relativehumidity:
        raise ValueError("Missing 'temperature_2m' or 'relative_humidity_2m' columns in DataFrame. Cannot calculate Humidex.")

    ur = df[label_relativehumidity[0]]
    for label in label_temperature:
        t = df[label]
        model_name_parts = label.split('_2m_')
        model = model_name_parts[1] if len(model_name_parts) > 1 else "unknown_model"

        e = (6.112 * pow(10, (7.5 * t / (237.7 + t))) * ur / 100)
        df['humidex_' + model] = t + 5 / 9 * (e - 10)
        steps = [29, 34, 39, 45, 54] # Humidex levels for heatwave classification
        df['ondata_calore_' + model] = np.sum([df['humidex_' + model] >= s for s in steps], axis=0)

    label_ondata_calore = [i for i in df.columns if 'ondata_calore_' in i]
    if label_ondata_calore:
        df['ondata_calore'] = df[label_ondata_calore].max(axis=1)
    else:
        df['ondata_calore'] = np.nan
    return df

def get_data_comune(lat, lon, hourly_parameters, weather_models, other_parameters):
    """Fetches weather forecast data for a given comune and calculates humidex."""
    geographical_WGS84_coordinate = {'latitude': lat, 'longitude': lon}

    input_api = {'geographical_WGS84_coordinate': geographical_WGS84_coordinate,
                 'hourly_parameters': hourly_parameters,
                 'pressure_level_variables': None,
                 'daily_parameters': None,
                 'weather_models': weather_models,
                 'other_parameters': other_parameters}

    open_meteo = OpenMeteo()
    open_meteo.call_weather_forecast(**input_api)
    open_meteo.set_output_weather_forecast()
    df = open_meteo.details_hourly
    df = correct_gmt(df, 'time')
    df = add_time_details(df, 'time')
    df = df.drop(columns=[col for col in ['ora', 'data'] if col in df.columns], errors='ignore')
    df = add_humidex(df)
    return df

def main():
    parser = argparse.ArgumentParser(description="Calculate and map heatwave levels based on weather forecasts.")
    parser.add_argument("--start_date", type=str, required=True, help="Initial forecast date (YYYY-MM-DD).")
    parser.add_argument("--forecast_days", type=int, default=7, help="Number of forecast days.")
    parser.add_argument("--models", type=str, default="ecmwf_ifs025,icon_eu",
                        help="Comma-separated list of weather models to use (e.g., ecmwf_ifs025,icon_eu).")
    parser.add_argument("--coordinates_file", type=str,
                        default=r'capoluoghi_provincia_coordinate.csv',
                        help="Path to the CSV file containing comune coordinates.")
    parser.add_argument("--shapefile_path", type=str,
                        default=r'ProvCM01012022\ProvCM01012022_WGS84.shp',
                        help="Path to the shapefile for province boundaries.")

    args = parser.parse_args()

    # Get current date for default start_date if not provided by user (for daily scheduled runs)
    if args.start_date:
        try:
            start_date = dt.datetime.strptime(args.start_date, '%Y-%m-%d')
        except ValueError:
            print("Error: Invalid date format for --start_date. Please use YYYY-MM-DD.")
            sys.exit(1)
    else:
        start_date = dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        print(f"No --start_date provided. Using current date: {start_date.strftime('%Y-%m-%d')}")


    num_forecast_days = args.forecast_days
    weather_models = [model.strip() for model in args.models.split(',')]

    output_dir = "heatwave_forecast_output"
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory created/ensured: {os.path.abspath(output_dir)}")

    hourly_parameters = ['temperature_2m', 'relative_humidity_2m', 'apparent_temperature']
    other_parameters = {'forecast_days': num_forecast_days}

    # Load coordinates
    try:
        coordinate = pd.read_csv(args.coordinates_file)
        if coordinate.empty:
            print(f"Warning: Coordinates file {args.coordinates_file} is empty. No data to process.")
            sys.exit(1)
        if not all(col in coordinate.columns for col in ['COMUNE', 'lat', 'lon']):
            print(f"Error: Coordinates file must contain 'COMUNE', 'lat', and 'lon' columns. Please check your CSV.")
            sys.exit(1)

    except FileNotFoundError:
        print(f"Error: Coordinates file not found at {args.coordinates_file}. Please ensure the path is correct.")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading coordinates file: {e}")
        sys.exit(1)

    comune = coordinate['COMUNE']
    latitude = coordinate['lat']
    longitude = coordinate['lon']

    print("\nFetching weather forecast data and calculating humidex...")
    try:
        # Concatenate data for all comunes
        df_weather = pd.concat({name: get_data_comune(lat, lon, hourly_parameters, weather_models, other_parameters)
                                for name, lat, lon in zip(comune, latitude, longitude)}, axis=1)
        print("Weather forecast data fetched successfully.")
        if df_weather.empty:
            print("Warning: Fetched weather data is empty. No humidex calculations performed.")
            sys.exit(1)
    except Exception as e:
        print(f"Error fetching weather data or calculating humidex: {e}")
        sys.exit(1)


    # Save full weather data (optional, useful for debugging)
    full_data_path = os.path.join(output_dir, f'ondate_calore_full_{dt.datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    df_weather.to_csv(full_data_path)
    print(f"Full weather data saved to {full_data_path}")

    # Load shapefile
    try:
        province = gpd.read_file(args.shapefile_path)
        province = province.to_crs(epsg=4326) # Ensure consistent CRS
        print(f"Shapefile loaded successfully from {args.shapefile_path}")
    except FileNotFoundError:
        print(f"Error: Shapefile not found at {args.shapefile_path}. Maps will not be generated.")
        province = None
    except Exception as e:
        print(f"Error loading shapefile: {e}. Maps will not be generated.")
        province = None

    # Color and description settings for heatwave levels
    colori = {
        1: 'deepskyblue',
        2: 'green',
        3: 'yellow',
        4: 'orange',
        5: 'red'
    }
    descrizioni = {
        1: '1 - Malessere debole',
        2: '2 - Malessere moderato',
        3: '3 - Malessere generalizzato',
        4: '4 - Forte malessere',
        5: '5 - Rischio colpi di calore'
    }

    # Ensure the DataFrame index is datetime for time-based slicing
    df_weather.index = pd.to_datetime(df_weather.index)

    print("\nProcessing daily heatwave levels and generating outputs...")
    for day_offset in range(num_forecast_days):
        current_date = start_date + pd.Timedelta(days=day_offset)
        print(f"\n--- Elaborazione giorno {current_date.strftime('%Y-%m-%d')} ---")

        max_humidex_list = []

        # Define time range for the current day (midnight to midnight of the next day)
        start_of_day = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day_exclusive = (current_date + pd.Timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

        for c in comune:
            col_to_check = (c, 'ondata_calore')

            if col_to_check in df_weather.columns:
                # Filter for the current day's data for this comune
                series_c = df_weather.loc[start_of_day:end_of_day_exclusive - pd.Timedelta(seconds=1), col_to_check]

                # Check if the series contains any non-NaN values
                if not series_c.empty and series_c.dropna().any():
                    max_val = series_c.max()
                    max_time = series_c.idxmax()
                else:
                    # If no valid data or all NaNs, assign NaN for level and NaT for time
                    max_val = np.nan
                    max_time = pd.NaT
            else:
                print(f"  Warning: 'ondata_calore' column missing for comune '{c}'. Assigning NaN.")
                max_val = np.nan
                max_time = pd.NaT

            max_humidex_list.append((c, max_val, max_time))


        df_max_humidex_day = pd.DataFrame(max_humidex_list, columns=['comune', 'max_ondata_calore', 'max_time'])

        # Merge with original coordinate DataFrame to get lat/lon
        df_max_humidex_day = pd.merge(df_max_humidex_day, coordinate[['COMUNE', 'lat', 'lon']],
                                      left_on='comune', right_on='COMUNE', how='left')
        df_max_humidex_day.drop(columns='COMUNE', inplace=True) # Drop duplicate comune column

        # DEBUG PRINTS FOR df_max_humidex_day (temporarily added for your previous debugging)
        # print(f"DEBUG heatwave_forecast: df_max_humidex_day before saving (head):\n{df_max_humidex_day.head().to_string()}")
        # print(f"DEBUG heatwave_forecast: df_max_humidex_day dtypes:\n{df_max_humidex_day.dtypes}")
        # print(f"DEBUG heatwave_forecast: Count of NaNs in critical columns (max_ondata_calore, lat, lon):")
        # print(df_max_humidex_day[['max_ondata_calore', 'lat', 'lon']].isnull().sum())
        # END DEBUG PRINTS

        # Save daily data to a text file
        output_filename_txt = os.path.join(output_dir, f'ondata_calore_day_{current_date.strftime("%Y%m%d")}.txt')
        with open(output_filename_txt, 'w') as f:
            f.write(f"Heatwave levels for {current_date.strftime('%Y-%m-%d')}\n\n")
            for index, row in df_max_humidex_day.iterrows():
                comune_name = row['comune']
                max_level = int(row['max_ondata_calore']) if pd.notna(row['max_ondata_calore']) else 'N/A'
                max_time_str = row['max_time'].strftime('%H:%M') if pd.notna(row['max_time']) else 'N/A'
                description = descrizioni.get(max_level, 'No data' if pd.isna(row['max_ondata_calore']) else 'Unknown level')
                f.write(f"Comune: {comune_name}, Max Heatwave Level: {max_level} ({description}), Time of Max: {max_time_str}\n")
        print(f"  Daily heatwave levels (TXT) saved to {output_filename_txt}")

        # Save daily data to a specific CSV for that day (useful for debugging/archiving)
        csv_daily_filename = os.path.join(output_dir, f'max_humidex_day_{current_date.strftime("%Y%m%d")}.csv')
        df_max_humidex_day.to_csv(csv_daily_filename, index=False)
        print(f"  Daily max humidex data (CSV) saved to {csv_daily_filename}")

        # --- CRITICAL PART FOR THE DASHBOARD: Update/Append to cumulative CSV ---
        df_max_humidex_day['forecast_day'] = current_date.strftime('%Y-%m-%d') # Ensure date column is string for consistency
        cumulative_csv_path = os.path.join(output_dir, 'all_heatwave_data.csv')

        if os.path.exists(cumulative_csv_path):
            try:
                existing_df = pd.read_csv(cumulative_csv_path)
                # Convert 'forecast_day' in existing_df to string for direct comparison
                existing_df['forecast_day'] = existing_df['forecast_day'].astype(str)
                # Filter out existing data for the current forecast_day to avoid duplicates on re-run
                existing_df_filtered = existing_df[existing_df['forecast_day'] != df_max_humidex_day['forecast_day'].iloc[0]]
                # Concatenate the filtered existing data with the new day's data
                updated_df = pd.concat([existing_df_filtered, df_max_humidex_day], ignore_index=True)
                updated_df.to_csv(cumulative_csv_path, index=False)
                print(f"  Cumulative data (CSV) updated: {cumulative_csv_path} with {len(df_max_humidex_day)} new rows. Total rows: {len(updated_df)}")
            except Exception as e:
                print(f"  WARNING: Could not update cumulative CSV gracefully ({e}). Overwriting instead.")
                df_max_humidex_day.to_csv(cumulative_csv_path, index=False) # Fallback to overwrite
        else:
            df_max_humidex_day.to_csv(cumulative_csv_path, index=False)
            print(f"  Cumulative data (CSV) created: {cumulative_csv_path} with {len(df_max_humidex_day)} rows.")
        # --- END CRITICAL PART ---

        # Generate map only if province shapefile was loaded successfully
        if province is not None:
            # Filter out rows where max_ondata_calore is NaN for plotting
            df_plot = df_max_humidex_day.dropna(subset=['lat', 'lon', 'max_ondata_calore'])

            if df_plot.empty:
                print(f"  No valid data to plot for {current_date.strftime('%Y-%m-%d')}. Skipping map generation.")
                continue # Skip to the next day

            fig, ax = plt.subplots(figsize=(10, 12))

            province.boundary.plot(ax=ax, linewidth=0.8, edgecolor='grey', zorder=0)

            for livello in colori:
                ax.scatter([], [],
                           color=colori[livello],
                           edgecolor='black',
                           linewidth=0.5,
                           s=100,
                           label=descrizioni[livello])

            gdf_points = gpd.GeoDataFrame(
                df_plot,
                geometry=gpd.points_from_xy(df_plot.lon, df_plot.lat),
                crs='EPSG:4326'
            )

            for livello in sorted(colori.keys()):
                subset = gdf_points[gdf_points['max_ondata_calore'] == livello]
                if not subset.empty:
                    subset.plot(
                        ax=ax,
                        color=colori[livello],
                        markersize=150,
                        edgecolor='black',
                        linewidth=0.5,
                        zorder=3
                    )

            if not gdf_points.empty:
                minx, miny, maxx, maxy = gdf_points.total_bounds
                ax.set_xlim(minx - 1, maxx + 1)
                ax.set_ylim(miny - 1, maxy + 1)
            else:
                ax.set_xlim(6, 19)
                ax.set_ylim(35, 48)

            ax.legend(
                title='Indice di calore (Humidex) massimo',
                loc='upper right',
                fontsize=10,
                title_fontsize=11,
                frameon=True,
                facecolor='white'
            )

            ax.set_title(f'Massimo Indice di Calore per ogni capoluogo - {current_date.strftime("%Y-%m-%d")}', fontsize=16, pad=20)
            ax.set_axis_off()

            map_filename = os.path.join(output_dir, f"mappa_humidex_{current_date.strftime('%Y%m%d')}.png")
            plt.savefig(map_filename, dpi=300, bbox_inches='tight')
            plt.close(fig)
            print(f"  Map saved to {map_filename}")
        else:
            print(f"  Skipping map generation for {current_date.strftime('%Y-%m-%d')} due to missing shapefile.")

    print("\nElaborazione completata!")

if __name__ == '__main__':
    main()