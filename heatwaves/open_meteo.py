# -*- coding: utf-8 -*-
import calendar
import datetime as dt
import json
import os

import pandas as pd

from get_api import get_api_as_dict


def check_subset(sub_list, test_list):
    return all(x in test_list for x in sub_list)


def validate_date_format(date_text, format='%Y-%m-%d'):
    try:
        dt.datetime.strptime(date_text, format)
    except ValueError:
        raise ValueError("Incorrect data format, should be " + format)


def check_integer(nb, message):
    try:
        int(nb)
    except TypeError:
        raise TypeError(message)


class OpenMeteo(object):
    def __init__(self):
        # https://open-meteo.com/en/docs
        self.url = 'https://api.open-meteo.com'
        self.service_weather_forecast = '/v1/forecast'
        self.geographical_WGS84_coordinate = {'latitude': None, 'longitude': None}
        self.hourly_parameters = ['temperature_2m',
                                  'relative_humidity_2m',
                                  'dewpoint_2m',
                                  'apparent_temperature',
                                  'pressure_msl',
                                  'surface_pressure',
                                  'cloudcover',
                                  'cloudcover_low',
                                  'cloudcover_mid',
                                  'cloudcover_high',
                                  'windspeed_10m',
                                  'windspeed_80m',
                                  'windspeed_120m',
                                  'windspeed_180m',
                                  'winddirection_10m',
                                  'winddirection_80m',
                                  'winddirection_120m',
                                  'winddirection_180m',
                                  'windgusts_10m',
                                  'shortwave_radiation',
                                  'direct_radiation',
                                  'direct_normal_irradiance',
                                  'diffuse_radiation',
                                  'vapor_pressure_deficit',
                                  'cape',
                                  'evapotranspiration',
                                  'et0_fao_evapotranspiration',
                                  'precipitation',
                                  'snowfall',
                                  'rain',
                                  'showers',
                                  'weathercode',
                                  'snow_depth',
                                  'freezinglevel_height',
                                  'visibility',
                                  'soil_temperature_0cm',
                                  'soil_temperature_6cm',
                                  'soil_temperature_18cm',
                                  'soil_temperature_54cm',
                                  'soil_moisture_0_1cm',
                                  'soil_moisture_1_3cm',
                                  'soil_moisture_3_9cm',
                                  'soil_moisture_9_27cm',
                                  'soil_moisture_27_81cm']
        self.pressure_level_variables = ['weathercode',
                                         'temperature_%hPa',
                                         'relativehumidity_%hPa',
                                         'dewpoint_%hPa',
                                         'cloudcover_%hPa',
                                         'windspeed_%hPa',
                                         'winddirection_%hPa',
                                         'geopotential_height_%hPa']
        self.weather_models = ['best_match', 'ecmwf_ifs025', 'metno_nordic',
                               'icon_eu', 'icon_seamless', 'icon_global', 'icon_d2',
                               'gfs_seamless', 'gfs_global', 'gfs_hrrr',
                               'gem_seamless', 'gem_global', 'gem_regional', 'gem_hrdps_continental',
                               'jma_seamless', 'jma_msm', 'jma_gsm',
                               'meteofrance_seamless', 'meteofrance_arpege_world', 'meteofrance_arpege_europe',
                               'meteofrance_arome_france', 'meteofrance_arome_france_hd']
        self.daily_parameters = ['temperature_2m_max',
                                 'temperature_2m_min',
                                 'apparent_temperature_max',
                                 'apparent_temperature_min',
                                 'precipitation_sum',
                                 'rain_sum',
                                 'showers_sum',
                                 'snowfall_sum',
                                 'precipitation_hours',
                                 'weathercode',
                                 'sunrise',
                                 'sunset',
                                 'windspeed_10m_max',
                                 'windgusts_10m_max',
                                 'winddirection_10m_dominant',
                                 'shortwave_radiation_sum',
                                 'et0_fao_evapotranspiration']
        self.other_parameters = {'current_weather': ['false', 'true'],
                                 'temperature_unit': ['celsius', 'fahrenheit'],
                                 'windspeed_unit': ['kmh', 'ms', 'mph', 'kn'],
                                 'precipitation_unit': ['mm', 'inch'],
                                 'timeformat': ['iso8601', 'unixtime'],
                                 'timezone': ['GMT', 'CET', 'auto'],
                                 'past_days': None,
                                 'start_date': None,
                                 'end_date': None,
                                 'forecast_days': [1,2, 3,4,5,6, 7, 14, 16]}
        self.output_structure = {'latitude': None,
                                 'longitude': None,
                                 'elevation': None,
                                 'generationtime_ms': None,
                                 'utc_offset_seconds': None,
                                 'timezone': None,
                                 'timezone_abbreviation': None,
                                 'hourly': None,
                                 'hourly_units': None,
                                 'daily': None,
                                 'daily_units': None,
                                 'current_weather': None}
        self.output_error = {"error": True, "reason": None}
        self.output_weather_forecast = None
        self.details_hourly = None
        self.details_daily = None
        self.prefix = ''
        self.path = os.getcwd()

    def check_structure_input(self, geographical_WGS84_coordinate, hourly_parameters=None,
                              pressure_level_variables=None, daily_parameters=None, weather_models=None,
                              other_parameters=None):
        # geographical_WGS84_coordinate
        for key in self.geographical_WGS84_coordinate:
            assert key in geographical_WGS84_coordinate, 'key ' + str(
                key) + ' should be present in geographical_WGS84_coordinate'

        # hourly_parameters
        if hourly_parameters is not None:
            assert check_subset(hourly_parameters,
                                self.hourly_parameters), 'hourly_parameters should be a subset of ' + str(
                self.hourly_parameters)

        # pressure_level_variables
        if pressure_level_variables is not None:
            for p in pressure_level_variables:
                p_split = p.split('_')
                check_variable = p_split[0]
                if len(p_split) > 1:
                    check_variable += '_%hPa'
                    nb = p_split[1].split('hPa')[0]
                    check_integer(nb, 'There should be an integer before hPa: ' + str(p))
                assert check_variable in self.pressure_level_variables, 'variable ' + str(check_variable)
                ' is not in list ' + str(self.pressure_level_variables)

        # daily_parameters
        if daily_parameters is not None:
            assert check_subset(daily_parameters,
                                self.daily_parameters), 'daily_parameters should be a subset of ' + str(
                self.daily_parameters)
            assert 'timezone' in other_parameters, 'if daily_parameters is not None, time_zone is required'

        # weather_models
        if weather_models is not None:
            assert check_subset(weather_models,
                                self.weather_models), 'weather_models should be a subset of ' + str(
                self.weather_models)

        # other_parameters
        if other_parameters is not None:
            assert check_subset(list(other_parameters.keys()),
                                list(self.other_parameters.keys())), 'other_parameters should be a subset of ' + str(
                list(self.other_parameters.keys()))

            # other_parameters: details
            for o in other_parameters:
                if self.other_parameters[o] is not None:
                    assert other_parameters[o] in self.other_parameters[
                        o], 'parameters ' + o + ' should be contained in ' + str(self.other_parameters[o])
                elif o in ['past_days', 'forecast_days']:
                    check_integer(other_parameters[o], o + ' should be an integer')
                else:
                    validate_date_format(other_parameters[o], format='%Y-%m-%d')

    def build_url_weather_forecast(self, geographical_WGS84_coordinate, hourly_parameters, pressure_level_variables,
                                   daily_parameters, weather_models, other_parameters):
        lat = 'latitude=' + str(geographical_WGS84_coordinate['latitude'])
        long = 'longitude=' + str(geographical_WGS84_coordinate['longitude'])
        url = self.url + self.service_weather_forecast + '?' + lat + '&' + long
        hourly_parameters = hourly_parameters if not None else []  # per concatenare comunque con pressure_level_variables
        if pressure_level_variables is not None:
            hourly_parameters.extend(pressure_level_variables)
        if hourly_parameters is not None:
            for h in hourly_parameters:
                url += '&hourly=' + h
        if daily_parameters is not None:
            for d in daily_parameters:
                url += '&daily=' + d
        if weather_models is not None:
            for w in weather_models:
                url += '&models=' + w
        if other_parameters is not None:
            for o in other_parameters:
                url += '&' + o + '=' + str(other_parameters[o])
        return url

    def call_weather_forecast(self, geographical_WGS84_coordinate=None, hourly_parameters=None,
                              pressure_level_variables=None, daily_parameters=None, weather_models=None,
                              other_parameters=None):
        self.check_structure_input(geographical_WGS84_coordinate, hourly_parameters, pressure_level_variables,
                                   daily_parameters, weather_models, other_parameters)
        url = self.build_url_weather_forecast(geographical_WGS84_coordinate, hourly_parameters,
                                              pressure_level_variables, daily_parameters, weather_models,
                                              other_parameters)
        self.output_weather_forecast = get_api_as_dict(url)

    def set_output_weather_forecast(self):
        with open(os.path.join(self.path, self.prefix + 'output_weather_forecast.json'), 'w') as outfile:
            json.dump(self.output_weather_forecast, outfile)

        if 'hourly' in self.output_weather_forecast:
            self.details_hourly = pd.DataFrame(self.output_weather_forecast['hourly'])

        if 'daily' in self.output_weather_forecast:
            self.details_daily = pd.DataFrame(self.output_weather_forecast['daily'])

    def save_output_weather_forecast(self, path):

        self.set_output_weather_forecast()

        if 'hourly' in self.output_weather_forecast:
            self.details_hourly.to_csv(os.path.join(path, self.prefix + 'details_hourly.csv'))

        if 'daily' in self.output_weather_forecast:
            self.details_daily.to_csv(os.path.join(path, self.prefix + 'details_daily.csv'))


class ArpegeArome(OpenMeteo):

    def __init__(self):
        # https://open-meteo.com/en/docs/meteofrance-api
        super(ArpegeArome, self).__init__()
        self.prefix = 'arpege_arome_'
        hourly_not_in_arpegearome = ['windspeed_80m',
                                     'windspeed_120m',
                                     'windspeed_180m',
                                     'winddirection_80m',
                                     'winddirection_120m',
                                     'winddirection_180m',
                                     'evapotranspiration',
                                     'rain',
                                     'showers',
                                     'snow_depth',
                                     'freezinglevel_height',
                                     'visibility',
                                     'soil_temperature_0cm',
                                     'soil_temperature_6cm',
                                     'soil_temperature_18cm',
                                     'soil_temperature_54cm',
                                     'soil_moisture_0_1cm',
                                     'soil_moisture_1_3cm',
                                     'soil_moisture_3_9cm',
                                     'soil_moisture_9_27cm',
                                     'soil_moisture_27_81cm']
        self.hourly_parameters = list(filter(lambda v: v not in hourly_not_in_arpegearome, self.hourly_parameters))
        daily_not_in_arpegearome = ['rain_sum',
                                    'showers_sum',
                                    'weathercode']
        self.daily_parameters = list(filter(lambda v: v not in daily_not_in_arpegearome, self.daily_parameters))


class HistERA5(OpenMeteo):
    def __init__(self):
        # https://open-meteo.com/en/docs/historical-weather-api#api_form
        super(HistERA5, self).__init__()
        self.url = 'https://archive-api.open-meteo.com'
        self.service_weather_forecast = '/v1/archive'
        hourly_not_in_hist = ['windspeed_80m',
                              'windspeed_120m',
                              'windspeed_180m',
                              'winddirection_80m',
                              'winddirection_120m',
                              'winddirection_180m',
                              'cape',
                              'evapotranspiration',
                              'showers',
                              'snow_depth',
                              'freezinglevel_height',
                              'visibility',
                              'soil_temperature_0cm',
                              'soil_temperature_6cm',
                              'soil_temperature_18cm',
                              'soil_temperature_54cm',
                              'soil_moisture_0_1cm',
                              'soil_moisture_1_3cm',
                              'soil_moisture_3_9cm',
                              'soil_moisture_9_27cm',
                              'soil_moisture_27_81cm']
        self.hourly_parameters = list(filter(lambda v: v not in hourly_not_in_hist, self.hourly_parameters))
        hourly_only_in_hist = ['windspeed_100m',
                               'winddirection_100m',
                               'soil_temperature_0_to_7cm',
                               'soil_temperature_7_to_28cm',
                               'soil_temperature_28_to_100cm',
                               'soil_temperature_100_to_255cm',
                               'soil_moisture_0_to_7cm',
                               'soil_moisture_7_to_28cm',
                               'soil_moisture_28_to_100cm',
                               'soil_moisture_100_to_255cm']
        self.hourly_parameters.extend(hourly_only_in_hist)
        self.daily_parameters.remove('showers_sum')
        self.output_structure.pop('current_weather')
        self.pressure_level_variables = []
        self.other_parameters['models'] = ['era5']


def correct_gmt(df, label_time):
    df_time = pd.DatetimeIndex(df[label_time])
    years = set(df_time.year)
    for year in years:
        last_sunday_march = str(year) + '-03-' + str(get_last_sunday(year, 3)) + ' 02:00:00'
        last_sunday_october = str(year) + '-10-' + str(get_last_sunday(year, 10)) + ' 02:00:00'
        id = (df_time >= last_sunday_march) & (df_time < last_sunday_october)
        df.loc[id, label_time] = df_time[id] + pd.to_timedelta(1, unit='h')
    return df


def get_last_sunday(year_number, month_number):
    list_weeks_in_month = calendar.monthcalendar(year_number, month_number)
    return max(list_weeks_in_month[-1][calendar.SUNDAY], list_weeks_in_month[-2][calendar.SUNDAY])


def add_time_details(df, label_time):
    df[label_time] = pd.to_datetime(df[label_time])
    df['data'] = pd.DatetimeIndex(df[label_time]).date
    df['ora'] = pd.DatetimeIndex(df[label_time]).hour
    df.set_index(label_time, inplace=True)
    df.dropna(inplace=True)
    return df


if __name__ == '__main__':
    # Example
    geographical_WGS84_coordinate = {'latitude': 45.59, 'longitude': 9.57}  # Milano
    hourly_parameters = ['temperature_2m', 'pressure_msl', 'cloudcover']

    pressure_level_variables = ['windspeed_1000hPa']
    daily_parameters = ['temperature_2m_max', 'temperature_2m_min', 'precipitation_sum', 'precipitation_hours',
                        'windspeed_10m_max']
    other_parameters = {'past_days': 10, 'timezone': 'GMT'}

    # Default: combination of the best weather models for the given location
    open_meteo = OpenMeteo()
    open_meteo.call_weather_forecast(geographical_WGS84_coordinate, hourly_parameters,
                                     pressure_level_variables, daily_parameters,
                                     other_parameters=other_parameters)
    path = 'C:/temp/'
    open_meteo.save_output_weather_forecast(path)

    # Weather model: Arpege-Arome
    arpege_arome = ArpegeArome()
    arpege_arome.call_weather_forecast(geographical_WGS84_coordinate, hourly_parameters,
                                       pressure_level_variables, daily_parameters,
                                       other_parameters=other_parameters)
    path = 'C:/temp/'
    arpege_arome.save_output_weather_forecast(path)
