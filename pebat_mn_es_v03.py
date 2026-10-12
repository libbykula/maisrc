# Libby Kula
# MAISRC FES
# 10/5/2026
# Purpose: Zonal stats of ES by lake 
# Update: Swapping out the wnh boundaries for the ones Molly sent me 

import numpy as np
import os
import pandas as pd
import geopandas as gpd
import pygeoprocessing.geoprocessing as pygeo

# Directory
base_dir = 'C:/Users/kibby/Files/base_data'
boundary_dir = os.path.join(base_dir, 'cartographic', 'lake_boundaries') 
es_dir = os.path.join(base_dir, 'maisrc_mn_es_data')

lakes_gdf = gpd.read_file(os.path.join(boundary_dir, 'lake_at_geometries.shp'))
lakes_gdf = lakes_gdf.to_crs('EPSG:26915')
lakes_gdf.to_file(os.path.join(boundary_dir, 'lake_at_geometries_epsg26915.gpkg'))

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
result_gdf = zonal_stats_to_gdf(es_lake_rec_path, os.path.join(boundary_dir, 'lake_at_geometries_epsg26915.gpkg'))
result_gdf.to_file(os.path.join(es_dir, 'lake_rec', 'lake_rec_zonal_stats.gpkg'))
print(result_gdf.head())