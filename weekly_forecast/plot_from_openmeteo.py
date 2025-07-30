#%%

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd


cities = {
    0:"Paris, France",
    1:"London, United Kingdom",
    2:"Berlin, Germany",
    3:"Madrid, Spain",
    4:"Rome, Italy",
    5:"Vienna, Austria",
    6:"Budapest, Hungary",
    7:"Warsaw, Poland",
    8:"Amsterdam, Netherlands",
    9:"Brussels, Belgium",
    10:"Lisbon, Portugal",
    11:"Prague, Czech Republic",
    12:"Athens, Greece",
    13:"Dublin, Ireland",
    14:"Stockholm, Sweden",
    15:"Copenhagen, Denmark",
    16:"Helsinki, Finland",
    17:"Oslo, Norway",
    18:"Zurich, Switzerland"
}

# Read the CSV file
file_path = 'C:/Users/jil.etienne/OneDrive - A2A Group/documents/04_projects/weekly_forecast/openmeteo/open-meteo-48.86N2.36E36m.csv'
data = pd.read_csv(file_path, skiprows=21)
print(data.head())

# Extract unique station IDs
station_ids = data['location_id'].unique()

# Plot variables for each station
for station_id in station_ids:
    station_name = cities[station_id]
    station_data = data[data['location_id'] == station_id]
    time = pd.to_datetime(station_data['time'])
    
    fig, axs = plt.subplots(5, 1, figsize=(12, 20), sharex=True)
    fig.suptitle(f'Station {station_id} - {station_name}', fontsize=16)
    
    # Plot temperature
    axs[0].plot(time, station_data['temperature_2m (°C)'], label='Temperature (°C)')
    axs[0].set_title(f'Station {station_id} - Temperature')
    axs[0].set_ylabel('Temperature (°C)')
    axs[0].legend()
    
    # Plot precipitation
    axs[1].plot(time, station_data['precipitation (mm)'], label='Precipitation (mm)')
    axs[1].set_title(f'Station {station_id} - Precipitation')
    axs[1].set_ylabel('Precipitation (mm)')
    axs[1].legend()
    
    # Plot pressure
    axs[2].plot(time, station_data['pressure_msl (hPa)'], label='Pressure (hPa)')
    axs[2].set_title(f'Station {station_id} - Pressure')
    axs[2].set_ylabel('Pressure (hPa)')
    axs[2].legend()
    
    # Plot wind speed
    axs[3].plot(time, station_data['wind_speed_120m (km/h)'], label='Wind Speed (km/h)')
    axs[3].set_title(f'Station {station_id} - Wind Speed')
    axs[3].set_ylabel('Wind Speed (km/h)')
    axs[3].legend()
    
    # Plot shortwave radiation
    axs[4].plot(time, station_data['shortwave_radiation (W/m²)'], label='Shortwave Radiation (W/m²)')
    axs[4].set_title(f'Station {station_id} - Shortwave Radiation')
    axs[4].set_xlabel('Time')
    axs[4].set_ylabel('Shortwave Radiation (W/m²)')
    axs[4].legend()
    
    plt.xticks(rotation=60)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(f'img/station_{station_id}.png')

# %%
