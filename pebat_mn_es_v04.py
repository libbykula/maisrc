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
es_dir = os.path.join(base_dir, 'maisrc', 'mn_es_data')

# lakes_gdf = gpd.read_file(os.path.join(boundary_dir, 'lake_at_geometries.shp'))
# lakes_gdf = lakes_gdf.to_crs('EPSG:26915')
# lakes_gdf.to_file(os.path.join(boundary_dir, 'lake_at_geometries_epsg26915.gpkg'))

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


# Source - https://stackoverflow.com/a/40347279
# Posted by user136036, modified by community. See post 'Timeline' for change history
# Retrieved 2026-10-05, License - CC BY-SA 4.0


STATS = ['min', 'max', 'count', 'nodata_count', 'sum', 'average']

def run_all_es(es_list):
    boundary_path = os.path.join(boundary_dir, 'lake_at_geometries_epsg26915.gpkg')
    all_results_gdf = None

    for es in es_list:
        print(es)
        es_path = os.path.join(es_dir, es, es + '_metric.tif')
        result_gdf = zonal_stats_to_gdf(es_path, boundary_path)

        # rename only the stat columns, e.g. min -> min_birdwatching
        renamed = result_gdf[STATS].rename(columns={s: f'{s}_{es}' for s in STATS})

        if all_results_gdf is None:
            # first ES: keep geometry and all non-stat columns as the base
            base = result_gdf.drop(columns=STATS)
            all_results_gdf = gpd.GeoDataFrame(
                pd.concat([base, renamed], axis=1), crs=result_gdf.crs
            )
        else:
            all_results_gdf = pd.concat([all_results_gdf, renamed], axis=1)

    all_results_gdf.to_file(
        os.path.join(es_dir, '1_pebat_lakes_zonal_stats.gpkg'), driver='GPKG'
    )
    return all_results_gdf

subdirs_list = [f.name for f in os.scandir(es_dir) if f.is_dir() ]

# run_all_es(subdirs_list)

# also just get the overall average score... can I do this from the aggregated? with the sums?

# ES Data
# CRS = EPSG:26915 - NAD83 
# es_lake_rec_path = os.path.join(es_dir, 'lake_rec', 'lake_rec_metric.tif')
# Do I have to get this in WGS84 before zonal stats? I don't think so, right?

