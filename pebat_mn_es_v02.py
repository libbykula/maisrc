# Libby Kula
# MAISRC FES
# 9/25/2026
# Purpose: Zonal stats of ES by lake 

import numpy as np
import os
import pandas as pd
import geopandas as gpd
import pygeoprocessing.geoprocessing as pygeo

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
lakes_gdf = gpd.read_file(os.path.join(boundary_dir, 'wnh_lakes.gpkg'))
lakes_gdf = lakes_gdf.to_crs('EPSG:26915')
lakes_gdf.to_file(os.path.join(boundary_dir, 'wnh_lakes_epsg26915.gpkg'))

# wbd_hu12_gdf = gpd.read_file(wnh_path, layer='WBDHU12')
# wbd_hu12_gdf.crs = 'EPSG:4326'
# wbd_hu12_gdf.to_file(os.path.join(boundary_dir, 'wnh_wbd_hu12.gpkg'))


# ES Data
# CRS = EPSG:26915 - NAD83 
es_lake_rec_path = os.path.join(es_dir, 'lake_rec', 'lake_rec_metric.tif')
# Do I have to get this in WGS84 before zonal stats? I don't think so, right?

def zonal_stats_to_gdf(raster_path, vector_path, band=1, stats=('min', 'max', 'count',  'nodata_count', 'sum', 'average')):
    """
    Run pygeoprocessing zonal_statistics and attach results as new columns
    on the aggregate vector's polygons.

    Parameters
    ----------
    raster_path : str
        Path to the raster to summarize.
    vector_path : str
        Path to the vector (polygons) to aggregate over. Must share the
        raster's CRS.
    band : int
        Raster band index (1-based).
    stats : tuple of str
        Which stat keys to pull from the zonal_statistics result
        (e.g. 'min', 'max', 'count', 'nodata_count', 'sum', 'average').

    Returns
    -------
    GeoDataFrame
        The original vector's attributes/geometry plus one new column
        per requested stat.
    """
    gdf = gpd.read_file(vector_path)

    zs = pygeo.zonal_statistics(
        base_raster_path_band=(raster_path, band),
        aggregate_vector_path=vector_path
    )

    # zs keys are FIDs matching the vector's feature order (0-based)
    for stat in stats:
        gdf[stat] = [zs.get(i + 1, {}).get(stat) for i in gdf.index]

    return gdf


# Usage
result_gdf = zonal_stats_to_gdf(es_lake_rec_path, os.path.join(boundary_dir, 'wnh_lakes_epsg26915.gpkg'))
result_gdf.to_file(os.path.join(es_dir, 'lake_rec', 'lake_rec_zonal_stats.gpkg'))
print(result_gdf.head())