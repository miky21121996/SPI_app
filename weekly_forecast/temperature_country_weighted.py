#%%
import datetime as dt
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import meteomatics.api as api
import pygrib
import cartopy as ctp
import cartopy.crs as ccrs
from shapely.geometry import Polygon
import requests
import datetime as datetime



def get_init_dates(var, startdate, model='ecmwf-ens'):
    """query the model runs.
    ec46 runs once daily at 00UTC, so usually the data of the first datetime is from the previous day run, 
    and the following from the request day run."""
    
    username, password=open("../zz_keys/meteomatics_credentials.txt", "r").read().split('\n')

    ens_select = 'member:0-50'  
    
    enddate = startdate + dt.timedelta(days=7)
    interval = dt.timedelta(hours=12)
    
    df_init_dates = api.query_init_date(startdate, 
                                        enddate, 
                                        interval,
                                        var,
                                        username,
                                        password,
                                        model)
    
    #print(df_init_dates.columns)

    return df_init_dates

def outlines_of_country(country):
    """return a list of coordinates (lat, lon) to be the vertices of a polygon query
    those coordinates are the simplified polygon of the country.
    saved in gridpoints/simplified_coordinates_{country}.csv"""
    
    europe=gpd.read_file(r'shapefiles\shapefile_europe\europe_regions.shp') # exploded europe shapefile
    # CRS epsg:4326
    
    # compute area of polygons
    europe['area']=europe.to_crs({'proj':'cea'}).area/(10**6)
    
    # # plot the country before and after convex transformation
    # fig, ax=plt.subplots(1,2, figsize=(14,8), sharex=True, sharey=True)
    # plt.tight_layout()
    paese=europe[europe['NAME']==country]
    # paese.plot(ax=ax[0], color='k')
    
    paese_simple=paese[paese['area']>=1000]
    paese_simple=paese_simple.simplify(tolerance=.5) # potatoise
    # paese_simple.plot(ax=ax[1], color='k')

    # ax[0].axis(False)
    # ax[1].axis(False)
    # plt.show()
    # plt.close()
    
    # build list of coordinates
    df=paese_simple.geometry.apply(lambda geometry: list(geometry.exterior.coords))        
    
    list_of_points=[]
    for poly_coords in df:
        list_of_points.append(poly_coords)
    
    # remove according to filter
    for ilp, lp in enumerate(list_of_points):
        for ipp, pp in enumerate(lp):
            lon, lat = pp
            if lat<43.7:
                lp.pop(ipp)
                list_of_points[ilp]=lp
    
    # invert lat and lon to have (lat, lon) instead of (lon, lat)
    for ilp, lp in enumerate(list_of_points):
        for ipp, pp in enumerate(lp):
            lon, lat = pp
            list_of_points[ilp][ipp] = (lat, lon)

    # save list_of_points to a csv file
    # columns are lat and lon, extra column for the polygon id (1, 2, ...)
    df_points = pd.DataFrame(columns=['lat', 'lon', 'pid'])
    for i, sublist in enumerate(list_of_points):
        for point in sublist:
            df_points.loc[len(df_points)] = {'lat': point[0], 'lon': point[1], 'pid': i + 1}
    df_points.to_csv(f"gridpoints/simplified_coordinates_{country}.csv", index=False, encoding='utf-8')

    return paese, list_of_points # return the original polygon and the simplified polygon coordinates


def grid_from_file(fname):
    """read a grib file and return a list of coordinates (lat, lon) to be the available grid points for ec eps.
    keep only points in Europe. -> lat between 30 and 70, lon between (345,360)union(0,35)
    save the coordinates to a csv file gridpoints/gridpoints_eceps.csv
    """

    coordinates = []
    with pygrib.open(fname) as grbs: # only one grib file
        lat, lon = grbs[1].latlons()
        lat, lon = lat[:,0], lon[0,:] # 1d arrays
        
        # filter coordinates to keep only those in Europe
        for i in range(len(lat)):
            for j in range(len(lon)):
                if 30 <= lat[i] <= 70 and (345 <= lon[j] <= 360 or 0 <= lon[j] <= 35):
                    coordinates.append((lat[i], lon[j]))
                    
    # remove duplicates
    coordinates = list(set(coordinates))
    # sort coordinates by lat, then by lon
    coordinates.sort(key=lambda x: (x[0], x[1]))
    # save to csv
    df = pd.DataFrame(coordinates, columns=['lat', 'lon'])
    df.to_csv(f"gridpoints/gridpoints_eceps.csv", index=False)

    print(f"Grid points from {fname} retrieved successfully. Total points: {len(coordinates)}")

    return coordinates 


def closest_model_grid(coordinates, country): 
    """
    return the closest model grid point to the coordinates of the polygon

    Parameters
    ----------
    coordinates : list of tuples
        list of coordinates (lat, lon) to be the vertices of a polygon query.
    country : str
        name of the country to which the coordinates belong.

    Returns
    -------
    list of tuples
        list of coordinates (lat, lon) of the closest model grid point.
    """

    #print(coordinates)

    all_lons = [c[0] for pol in coordinates for c in pol]
    all_lats = [c[1] for pol in coordinates for c in pol]

    # max lat and lon from coordinates
    lat_max, lon_max = max(all_lats), max(all_lons)
    lat_min, lon_min = min(all_lats), min(all_lons)

    #print(lat_max)
    
    # # query the model grid points
    # username, password=open("../zz_keys/meteomatics_credentials.txt", "r").read().split('\n')
    # model='ecmwf-ens'

    # startdate=dt.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - dt.timedelta(days=1)
    # enddate = startdate + dt.timedelta(days=1)
    # #print(startdate, enddate)
    # df_grid = api.query_grid(model=model, 
    #                          username=username.strip(), 
    #                          password=password.strip(),
    #                          startdate=startdate,
    #                          #enddate=enddate,
    #                          interval=dt.timedelta(hours=1),
    #                          lat_N=lat_max,
    #                          lat_S=lat_min,
    #                          lon_E=lon_max,
    #                          lon_W=lon_min,
    #                          res_lat=0.1,  # 0.1 degree resolution
    #                          res_lon=0.1,  # 0.1 degree resolution
    #                          parameter_grid='t_2m:C'  # temperature at 2m
    #                          )

    # # the first line and the first column are the lon and lat of the grid points
    # lons = df_grid.columns[1:].astype(float).tolist()
    # lats = df_grid.index.astype(float).tolist()
    # model_latlon = list(zip(lons, lats))

    # grid from eceps .csv file
    model_latlon = pd.read_csv(f"gridpoints/gridpoints_eceps.csv")

    closest_points = []
    for poly in coordinates:
        polyest_points = []
        for point in poly:
            lat, lon = point
            # find the closest model grid point
            closest_point = tuple(min(model_latlon.values, key=lambda x: (x[0] - lat) ** 2 + (x[1] - lon) ** 2))
            polyest_points.append(closest_point)
            #print(f"Closest point to {point} is {closest_point}")
        # append polyest_points to closest_points if the number of points is greater than 2 (otherwise it's a line and the API is not happy with it)
        if len(polyest_points) > 2:
            closest_points.append(polyest_points)

    # save the closest points to a csv file
    df_closest_points = pd.DataFrame(columns=['lat', 'lon', 'pid'])
    for i, sublist in enumerate(closest_points):
        for point in sublist:
            df_closest_points.loc[len(df_closest_points)] = {'lat': point[0], 'lon': point[1], 'pid': i + 1}
    df_closest_points.to_csv(f"gridpoints/closest_model_coordinates_{country}.csv", index=False, encoding='utf-8')

    return closest_points


def request_polygon(var, country, startdate, save=True):
    """ request a timeseries of EC46 for 7 days, every 3h (native) averaged by country, for each ensemble member.
    """
    username, password=open("../zz_keys/meteomatics_credentials.txt", "r").read().split('\n')
    
    # request the init date of the data
    df_init_dates = get_init_dates(var, startdate)
    print(df_init_dates)
    
    # coordinates for the query
    coordinates=outlines_of_country(country)
    #coordinates=[[(20., 40.), (22., 40.), (22., 37.), (20., 37.)]]
    
    parameters = [var]
    polygon_sampling='adaptive_grid' 
    aggregation=['mean']
    operator='U'
    
    model='ecmwf-vareps'
    ens_select = 'member:0-100'  
    
    enddate = startdate + dt.timedelta(days=7)
    interval = dt.timedelta(hours=3)
    
    df = api.query_polygon(latlon_tuple_lists=coordinates, 
                            startdate=startdate, 
                            enddate=enddate, 
                            interval=interval, 
                            parameters=parameters, 
                            aggregation=aggregation,
                            username=username, 
                            password=password, 
                            operator=operator,
                            model=model, 
                            polygon_sampling=polygon_sampling,
                            ens_select=ens_select
                            )

    # save
    strstart=startdate.strftime('%Y-%m-%d-%HZ')
    strend=enddate.strftime('%Y-%m-%d-%HZ')
    df.to_csv(r"requests\{}_{}_{}_{}_members_{}_{}.csv".format(var.replace(':', '_'), aggregation[0], country, model, strstart, strend), encoding="utf-8")
    
    return df

def request_polygon2(var, country, startdate, save=True):
    """ request a timeseries of ecEPS mean for 10 days, every 3h (native) averaged by country.
    """
    username, password=open("../zz_keys/meteomatics_credentials.txt", "r").read().split('\n')
    

    # request the init date of the data
    # print("Requesting init dates...")
    # df_init_dates = get_init_dates(var, startdate)
    # print('Done. Latest init date: ', df_init_dates.iloc[-1]['init_date'])

    #print(df_init_dates)
    
    # country coordinates from saved csv
    coordinates = pd.read_csv(f"gridpoints/closest_model_coordinates_{country}.csv") # DataFrame with columns ['lat', 'lon', 'pid']
    # convert of list of lists of tuples
    coordinates = [list(zip(coordinates['lat'][coordinates['pid'] == pid], coordinates['lon'][coordinates['pid'] == pid])) for pid in coordinates['pid'].unique()]

    # coordinates contains a list of lists of tuples (lat, lon) for each polygon in the country
    # we must pass the lists of tuples to the query one by one
    
    parameters = [var]
    polygon_sampling='adaptive_grid' 
    aggregation=['mean']
    operator='U'
    
    model='ecmwf-ens'
    ens_select = 'mean'
    
    enddate = startdate + dt.timedelta(days=14)
    interval = dt.timedelta(hours=1)

    p=0
    for tcoords in coordinates:
        # convert the list of tuples to a list of lists
        latlon_tuple_lists = [[(lat, lon) for lat, lon in tcoords]]
        
        df = api.query_polygon(latlon_tuple_lists=latlon_tuple_lists, 
                            startdate=startdate, 
                            enddate=enddate, 
                            interval=interval, 
                            parameters=parameters, 
                            aggregation=aggregation,
                            username=username, 
                            password=password, 
                            operator=operator,
                            model=model, 
                            polygon_sampling=polygon_sampling,
                            ens_select=ens_select
                            )
        if p==0:
            df.reset_index(inplace=True)
            df_all = df.copy()
        else:
            df.reset_index(inplace=True)
            df['station_id'] = f'polygon{p+1}'
            df_all = pd.concat([df_all, df], axis=0)
        p+=1

    if save:
        strstart=startdate.strftime('%Y-%m-%d-%HZ')
        strend=enddate.strftime('%Y-%m-%d-%HZ')
        df_all.to_csv(r"raw_meteomatics\{}_{}_{}_{}_{}_{}.csv".format(var.replace(':', '_'), aggregation[0], country, model, strstart, strend), encoding="utf-8")
        
    return df_all

def request_geopotential_week(startdate, member, save=True):
    """ request a timeseries of EC46 for 7 days, every 3h (native) on a grid 1degx1deg.
    only one member allowed.
    """
    #NotFound: Parameter climatological_regime:idx not available in model ecmwf-vareps
    
    username, password=open("../meteomatics_credentials.txt", "r").read().split('\n')
    
    parameters=['geopotential_height_500hPa:m']
    
    lat_N = 65
    lon_W = -10
    lat_S = 30
    lon_E = 30
    res_lat = 2 # how to retrieve on the native grid???
    res_lon = 2
    
    enddate = startdate + dt.timedelta(days=7)
    interval = dt.timedelta(hours=3)
    
    model='ecmwf-vareps'
    ens_select = 'member:{}'.format(member)  
    #cluster_select = 'cluster:1-6' 
    

    df = api.query_grid_timeseries(startdate, 
                                    enddate, 
                                    interval, 
                                    parameters, 
                                    lat_N, lon_W, lat_S, lon_E,
                                    res_lat, res_lon,
                                    username, 
                                    password, 
                                    model,
                                    ens_select=ens_select
                                    )
    

    # save
    strstart=startdate.strftime('%Y-%m-%d-%HZ')
    strend=enddate.strftime('%Y-%m-%d-%HZ')
    str_var='_'.join(parameters).replace(':', '_')
    df.to_csv(r"requests\{}_{}_m{}_{}_{}.csv".format(str_var, model, member, strstart, strend), encoding="utf-8")
      
    return df
    
def compute_area_of_polygon(coordinates):
    """compute the area of a polygon given a list of its coordinates (lat, lon)"""
    # Create a Polygon from the coordinates
    poly = Polygon(coordinates)
    gdf = gpd.GeoDataFrame(geometry=[poly])
    gdf = gdf.set_crs(epsg=4326)  # set the CRS to WGS84
    gdf = gdf.to_crs(epsg=3395)   # convert to a projected CRS (Mercator)
    return gdf.geometry.area.iloc[0] / 1e6  # return area in km²

def plot_temperature_from_csv(countries, startdate, enddate):
    """Plot temperature from a CSV file for a list of countries and start date."""
    
    # Plot the temperature
    plt.figure(figsize=(10, 6))

    colors ={'Germany': 'orange', 'France': 'blue', 'Italy': 'red', 'Romania': 'maroon'}

    climate = {'Germany': 11.5, 'France': 15.2, 'Italy': 17.3, 'Romania': 13.2}  # to change manually

    for country in countries:
        # Read the CSV file
        file_path = f'raw_meteomatics/t_2m_C_mean_{country}_ecmwf-ens_{startdate.strftime("%Y-%m-%d-%HZ")}_{enddate.strftime("%Y-%m-%d-%HZ")}.csv'
        t2m = pd.read_csv(file_path)

        # separate the dataframe by column station_id (gives the id of the polygon)
        # weight the temperature by the area of the polygon
        coordinates_country = pd.read_csv(f"gridpoints/closest_model_coordinates_{country}.csv")
        coordinates = [list(zip(coordinates_country['lat'][coordinates_country['pid'] == pid], coordinates_country['lon'][coordinates_country['pid'] == pid])) for pid in coordinates_country['pid'].unique()]
        areas = [compute_area_of_polygon(poly) for poly in coordinates]
        t2m['station_id'] = [int(k[7:]) for k in t2m['station_id']]  # ensure station_id is int for indexing
        colname_value= t2m.columns[-1]  # assuming the last column is the temperature value

        # group by validdate and compute the weighted mean temperature across all polygons
        t2m['validdate'] = pd.to_datetime(t2m['validdate'])
        # create a mapping from station_id to area
        area_map = {i + 1: area for i, area in enumerate(areas)}
        
        def weighted_temp(group):
            temps = group[colname_value].values
            sids = group['station_id'].values
            weights = [area_map[sid] for sid in sids]
            return pd.Series({'weighted_temp': (temps * weights).sum() / sum(weights)})
        
        t2m_weighted = t2m.groupby('validdate').apply(weighted_temp).reset_index()

        # plot the maximum daily temperature, minimum daily temperature and mean daily temperature
        t2m_daily = t2m_weighted.resample('D', on='validdate').agg({'weighted_temp': ['max', 'min', 'mean']})
        t2m_daily.columns = ['max_temp', 'min_temp', 'mean_temp']
        t2m_daily.reset_index(inplace=True)

        plt.plot(pd.to_datetime(t2m_daily['validdate']), t2m_daily['mean_temp'], linestyle='-', linewidth=2, color=colors[country], label=f'{country}')
        # plt.fill_between(pd.to_datetime(t2m_daily['validdate']),
        #                  t2m_daily['min_temp'], 
        #                  t2m_daily['max_temp'], 
        #                  color=colors[country], 
        #                  alpha=0.3, 
        #                  label=f'{country} Temp Range')

        #plt.plot(pd.to_datetime(t2m_weighted['validdate']), t2m_weighted['weighted_temp'], linestyle='-', color= colors[country], label=country)
    
        # add manually the climatic value for the country as a dashed line
        plt.axhline(y=climate[country], color=colors[country], linestyle='--', linewidth=2, label=f'Climate {country}')

    plt.title(f'Temperature from {startdate.strftime("%Y-%m-%d")} to {enddate.strftime("%Y-%m-%d")}')
    plt.xlabel('Date')
    plt.ylabel('Temperature (°C)')
    plt.xticks(rotation=45)
    plt.grid()
    plt.tight_layout()
    #plt.ylim(15, 30)  # set y-axis limits
    end_xlim = pd.to_datetime((enddate - datetime.timedelta(days=3)).strftime("%Y-%m-%d"))
    plt.xlim(pd.to_datetime(startdate.strftime("%Y-%m-%d")), end_xlim)

    # legend in 2 columns inside the plot
    plt.legend(ncol=2, fontsize='small')

    # save the plot
    plt.savefig(f'img/temperature_{startdate.strftime("%Y-%m-%d")}_{enddate.strftime("%Y-%m-%d")}.png')

    plt.show()
    return None

def query_10y_average(country, var, startdate, save=True):
    """query the climatic value for a country from the Meteomatics API (they do not indicate where it comes from)
    saves the data to a csv file in raw_metdesk/climate_{country}.csv"""
    
    username, password=open("../zz_keys/meteomatics_credentials.txt", "r").read().split('\n')
    
    # country coordinates from saved csv
    coordinates = pd.read_csv(f"gridpoints/closest_model_coordinates_{country}.csv") # DataFrame with columns ['lat', 'lon', 'pid']
    # convert of list of lists of tuples
    coordinates = [list(zip(coordinates['lat'][coordinates['pid'] == pid], coordinates['lon'][coordinates['pid'] == pid])) for pid in coordinates['pid'].unique()]

    # coordinates contains a list of lists of tuples (lat, lon) for each polygon in the country
    # we must pass the lists of tuples to the query one by one
    
    parameters = ['t_2m_10y_mean:C']  # 10 year average temperature
    polygon_sampling='adaptive_grid' 
    aggregation=['mean']
    operator='U'
    
    model='ecmwf-ens'
    #ens_select = 'mean'
    
    enddate = startdate + dt.timedelta(days=14)
    interval = dt.timedelta(hours=1)

    p=0
    for tcoords in coordinates:
        # convert the list of tuples to a list of lists
        latlon_tuple_lists = [[(lat, lon) for lat, lon in tcoords]]
        
        df = api.query_polygon(latlon_tuple_lists=latlon_tuple_lists, 
                            startdate=startdate, 
                            #enddate=enddate, 
                            interval=interval, 
                            parameters=parameters, 
                            aggregation=aggregation,
                            duration='1D',  # 1 day period
                            step='3H',  # tri-hourly step
                            username=username, 
                            password=password, 
                            operator=operator,
                            #model=model, 
                            polygon_sampling=polygon_sampling,
                            #ens_select=ens_select,
                            timeout_seconds=3000  # increase timeout for large queries because the api is slow af
                            )
        if p==0:
            df.reset_index(inplace=True)
            df_all = df.copy()
        else:
            df.reset_index(inplace=True)
            df['station_id'] = f'polygon{p+1}'
            df_all = pd.concat([df_all, df], axis=0)
        p+=1

    if save:
        strstart=startdate.strftime('%Y-%m-%d-%HZ')
        df_all.to_csv(r"raw_meteomatics\average_10y_{}_{}_{}_{}.csv".format(var.replace(':', '_'), aggregation[0], country, strstart), encoding="utf-8")
        
    return df_all

if __name__=='__main__':
       
    var='t_2m:C'
    #var='geopotential_height_500hPa:m'
    param=['t_2m:C']
    #param=['climatological_regime:idx']
    #model='ecmwf-vareps'
    
    startdate = dt.datetime(2025, 10, 2, 0, 0, 0)
    enddate = startdate + dt.timedelta(days=14)

    countries=['Germany', 'France', 'Italy', 'Romania']

    for country in countries:

        print(get_init_dates(var, startdate, model='ecmwf-ifs'))
            
        #------------ get native ECEPSgrid ---------- (saved in gridpoints/gridpoints_eceps.csv)

        #gridpoints_eceps = grid_from_file(r'random_forecast_for_grid.grib')

        #----------- compute country coordinates from shapefile ----------- (saved in gridpoints/closest_model_coordinates_{country}.csv)
        #paese, coordinates = outlines_of_country(country)
        #and find the closest model grid points
        #coordinates2 = closest_model_grid(coordinates, country)
        
        #---------- POLYGON REQUEST -----------
        # call api
        print(f"Requesting {var} for {country} from {startdate.strftime('%Y-%m-%d')} to {(startdate + dt.timedelta(days=7)).strftime('%Y-%m-%d')}")
        df=request_polygon2(var, country, startdate, save=True)
        print(f"Data for {country} saved successfully.")


        # ----------- query climatic temperature data ---------------
        # print(f"Querying 10 year average temperature for {country} from {startdate.strftime('%Y-%m-%d')}")
        # df_climate = query_10y_average(country, var, startdate, save=True)

    # ------------ plot temperature from csv ------------
    plot_temperature_from_csv(countries, startdate, enddate)

# %%
