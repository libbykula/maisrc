# Libby Kula
# MAISRC FES
# 9/25/2026
# Purpose: Zonal stats of ES by lake 

import numpy as np
import os
import pandas as pd
import geopandas as gpd
import pygeoprocessing as pygeo

# Directory
base_dir = 'C:/Users/kibby/Files/base_data/maisrc'
boundary_dir = os.path.join(base_dir, 'boundaries') # other than the water_national_hypdrography_data.gpkg, I took the folder contents out of mn_es_data
es_dir = os.path.join(base_dir, 'mn_es_data')

# Water National Hydrography gpkg from https://gis.data.mn.gov/maps/aebfea1f26cc4ebc91fdfff5665f3733/about

# this file is huge and only want one or two of the layers, so I'm saving them and deleting the source geopackage
# CRS = EPSG:4269 - NAD83
# wnh_path = os.path.join(boundary_dir, 'water_national_hydrography_data.gpkg')

# waterbody_gdf = gpd.read_file(wnh_path, layer='NHDWaterbody')
# waterbody_gdf.crs = 'EPSG:4326' # WGS84, best for calculations of zonal stats
# waterbody_gdf.to_file(os.path.join(boundary_dir, 'wnh_waterbodies.gpkg'))
# # sort this to get just named lakes?

# lakes_gdf = waterbody_gdf.loc[waterbody_gdf['gnis_name'].notnull()] # Geographic names information system (GNIS)?
# lakes_gdf.to_file(os.path.join(boundary_dir, 'wnh_lakes.gpkg'))

# wbd_hu12_gdf = gpd.read_file(wnh_path, layer='WBDHU12')
# wbd_hu12_gdf.crs = 'EPSG:4326'
# wbd_hu12_gdf.to_file(os.path.join(boundary_dir, 'wnh_wbd_hu12.gpkg'))


# ES Data
# CRS = EPSG:26915 - NAD83 
es_lake_rec_path = os.path.join(es_dir, 'lake_rec', 'lake_rec_metric.tif')
# Do I have to get this in WGS84 before zonal stats? I don't think so, right?


# # Zonal stats 
zonal_stats = pygeo.zonal_statistics(base_raster_path_band=(es_lake_rec_path, 1),
                       aggregate_vector_path=os.path.join(boundary_dir, 'wnh_lakes.gpkg')) # maybe try with just one lake and see what it does???

print(zonal_stats)
print('hi')