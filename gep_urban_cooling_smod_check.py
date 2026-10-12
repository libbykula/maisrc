import numpy as np
import os
import pandas as pd
import geopandas as gpd

base_dir = 'C:/Users/kibby/Files/base_data'

smod_dir = os.path.join(base_dir, 'cartographic/urbansspatial-guppd-v1-gpkg/smod_ids_by_country')
countries_list = [f.name[:3] for f in os.scandir(smod_dir)]
# print(countries_list)

gep_values = pd.read_csv(os.path.join(base_dir, 'All Services GEP Values 2026_10_01.xlsx - Libby scratch.csv'))

col = ' Local Climate Regulation (Urban Cooling) '

mask = gep_values[col].isna() | (gep_values[col].astype(str).str.strip() == '') | (gep_values[col].astype(str).str.strip() == '-')

missing_gep_iso = (
    gep_values.loc[mask, 'iso3_r250_label']
    .dropna()
    .str.lower()
    .tolist()
)

# print('hi')

no_smods = [x for x in missing_gep_iso if x not in countries_list]
print(no_smods)

