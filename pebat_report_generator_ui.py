import numpy as np
import geopandas as gp
import pandas as pd
import rasterstats
# from rasterstats import zonal_stats # INTERESTING NOTE ABOUT PROJECT FLOW, cant import actual function names as they get pulled int model_functions
import matplotlib.pyplot as plt
import os, sys
from collections import OrderedDict
import hazelbean as hb
from hazelbean.ui import model, inputs
import logging


class TkErrorCatcher:
    '''
    In some cases tkinter will only print the traceback.
    Enables the program to catch tkinter errors normally

    To use
    import tkinter
    tkinter.CallWrapper = TkErrorCatcher
    '''

    def __init__(self, func, subst, widget):
        self.func = func
        self.subst = subst
        self.widget = widget

    def __call__(self, *args):
        try:
            if self.subst:
                args = self.subst(*args)
            return self.func(*args)
        except SystemExit as msg:
            raise SystemExit(msg)
        except Exception as err:
            raise err


import tkinter

tkinter.CallWrapper = TkErrorCatcher

hb.model.LOGGER.setLevel(logging.WARNING)
hb.inputs.LOGGER.setLevel(logging.WARNING)


def mean_parcel_score(parcel_df, metric_paths_dict):
    # Use all_touched strategy when scoring parcels except those from the 'all_parcels' set (forty_id starts with 'f')
    parcel_type = parcel_df.at[0, 'forty_id'][:1]
    all_touched = True
    if parcel_type == 'f':
        all_touched = False

    for metric in metric_paths_dict:
        statslist = ['mean']
        score_mean = rasterstats.zonal_stats(parcel_df, metric_paths_dict[metric], stats=statslist,
                                             all_touched=all_touched)
        score_mean = pd.DataFrame(score_mean)
        parcel_df = parcel_df.join(score_mean)
        for stat in statslist:
            parcel_df.rename(columns={stat: metric + '_' + stat}, inplace=True)
            parcel_df[metric + '_' + stat].fillna(0, inplace=True)

    return parcel_df


def calc_index(all_parcels_df, metric_list):
    for metric in metric_list:
        metric = metric + '_mean'
        col_min = all_parcels_df[metric].min()
        col_max = all_parcels_df[metric].max()
        col_range = col_max - col_min
        all_parcels_df['idx_' + metric] = (all_parcels_df[metric] - col_min) / col_range
        pastacq_df = all_parcels_df.loc[all_parcels_df['forty_id'].str.startswith('e')].copy()
        proposed_df = all_parcels_df.loc[all_parcels_df['forty_id'].str.startswith('p')].copy()
    return pastacq_df, all_parcels_df, proposed_df


def get_metric_stats(df, metric_list, col_prefix):
    mean_df = df.mean(axis=0, numeric_only=True).to_frame().transpose()
    sd_df = df.std(axis=0, numeric_only=True).to_frame().transpose()
    mean_list, sd_list, sd2_list = [], [], []
    for metric in metric_list:
        metric = col_prefix + metric + '_mean'
        m = mean_df.at[0, metric]
        sd = sd_df.at[0, metric]
        mean_1sd = m + sd
        mean_2sd = m + sd * 2
        mean_list.append(m)
        sd_list.append(mean_1sd)
        sd2_list.append(mean_2sd)
    return mean_list, sd_list, sd2_list


def generate_args():
    args = OrderedDict()
    args['shapefile_path'] = ''
    args['run_in_batch_mode'] = ''
    args['batch_dir'] = ''
    args['price_per_acre'] = ''
    args['data_dir'] = ''
    args['output_dir'] = ''

    return args


def execute(p):
    os.chdir(p.args['data_dir'])

    p.metric_list = ['gwn', 'trout_angling', 'trails',  'bird_watching', 'lake_rec',
               'wild_rice', 'pheasant_hunting', 'pollination', 'carbon', 'population', 'risk_of_change']

    p.metric_paths = {
        'pollination': 'pollination/pollination_metric.tif',
        'lake_rec': 'lake_rec/lake_rec_metric.tif',
        'gwn': 'gwn/gwn_metric.tif',
        'trails': 'trails/trails_metric.tif',
        'carbon': 'carbon/carbon_metric.tif',
        'trout_angling': 'trout_angling/trout_angling_metric.tif',
        'bird_watching': 'bird_watching/bird_watching_metric.tif',
        'pheasant_hunting': 'pheasant_hunting/pheasant_hunting_metric.tif',
        'wild_rice': 'wild_rice/wild_rice_metric.tif',
        'population': 'population/population_metric.tif',
        'risk_of_change': 'risk_of_change/risk_of_change_metric.tif'}

    p.print_metrics = {
        'pollination': 'Pollination',
        'lake_rec': 'Lake Recreation',
        'gwn': 'Groundwater Nitrate',
        'trails': 'Recreation Trails',
        'carbon': 'Soil Carbon',
        'trout_angling': 'Trout Angling',
        'bird_watching': 'Bird Watching',
        'pheasant_hunting': 'Pheasant Production',
        'wild_rice': 'Wild Rice',
        'population': 'Nearby Population',
        'risk_of_change': 'Risk of Conversion'}

    p.print_list = []
    for metric in p.metric_list:
        p.print_list.append(p.print_metrics[metric])

    current_metric_vector = {}

    def calc_metrics_for_shapefile(shapefile_path):

        p.proposed = gp.read_file(shapefile_path)

        try:
            if not (p.proposed.crs['init'] == 'epsg:26915' or p.proposed.crs['init'] == 'epsg:4326'):
                raise NameError(
                    'Input shapefile not in correct projection. Reproject your shapefile to UTM15N (epsg:26915)')
        except:
            raise NameError('Unable to interpret shapefile projection. Reproject your shapefile to UTM15N (epsg:26915)')

        if p.proposed.crs['init'] == 'epsg:4326':
            p.proposed = p.proposed.to_crs({'init': 'epsg:26915'})

        p.proposed['forty_id'] = 'p' + p.proposed.index.astype(str)
        p.proposed = mean_parcel_score(p.proposed, p.metric_paths)
        p.proposed = p.proposed.drop('geometry', axis=1)

        p.potential = pd.read_csv('tables/metric_scores/forty_scored.csv')
        p.pastacq = pd.read_csv('tables/metric_scores/past_acquisitions_scored.csv')
        p.pastacq_cost = pd.read_csv('tables/aux_data/pastacq_cost.csv')
        p.viable_path = 'tables/viable_parcels/viable_fortys.csv'

        p.viable = pd.read_csv(p.viable_path, usecols=['forty_id'])
        p.potential = pd.merge(p.potential, p.viable, how='inner', on='forty_id')

        p.all_parcels = pd.concat([p.potential, p.pastacq, p.proposed])
        p.pastacq, p.all_parcels, p.proposed = calc_index(p.all_parcels, p.metric_list)

        p.pastacq = pd.merge(p.pastacq, p.pastacq_cost, on='forty_id')
        p.proposed['total_$_ac'] = float(p.args['price_per_acre'])

        for metric in p.metric_list:
            p.pastacq['roi_' + metric + '_mean'] = (p.pastacq['idx_' + metric + '_mean'] * 10000) / (
                p.pastacq['total_$_ac'])
            p.proposed['roi_' + metric + '_mean'] = (p.proposed['idx_' + metric + '_mean'] * 10000) / (
                p.proposed['total_$_ac'])

        ax1 = None
        ax2 = None
        fig = None
        plt = None

        import matplotlib
        import matplotlib.pyplot as plt
        matplotlib.use('Qt4Agg', warn=False, force=True)

        # Create figure
        fig = plt.figure(figsize=(11, 8.5))
        ax1 = fig.add_subplot(2, 1, 1)
        ax2 = fig.add_subplot(2, 1, 2)

        # Metric scores bar graph
        y_pos = np.arange(len(p.metric_list))

        proposed_scores, proposed_sd, proposed_sd_2x = get_metric_stats(p.proposed, p.metric_list, 'idx_')
        viable_mean, viable_sd, viable_sd_2x = get_metric_stats(p.all_parcels, p.metric_list, 'idx_')

        ax1.barh(y_pos, [1] * len(p.metric_list), height=0.4, color='#EBF5DF', align='center', label='Max score = 1')
        ax1.barh(y_pos, viable_sd_2x, height=0.4, color='#C5E39F', align='center', label='Far above average')
        ax1.barh(y_pos, viable_sd, height=0.4, color='#9ED060', align='center', label='Above average')
        ax1.barh(y_pos, viable_mean, height=0.4, color='#78BE21', align='center', label='Viable parcels average')
        ax1.barh(y_pos, proposed_scores, height=0.0, linewidth='1', yerr=[0.4] * len(p.metric_list),
                 error_kw=dict(ecolor='#E57200', lw=3.5),
                 edgecolor='#E57200', fill=True, facecolor='#E57200', align='center', label='Proposed acquisition')

        ax1.set_title('Comparisons of proposed parcel to all viable parcels', fontweight='bold')
        ax1.set_yticks(y_pos)
        ax1.set_yticklabels(p.print_list)
        ax1.set_xlabel('Environmental Benefit Score')
        ax1.set_xlim([0, 1.05])
        handles, labels = ax1.get_legend_handles_labels()
        order = [4, 3, 2, 1, 0]
        ax1.legend([handles[idx] for idx in order], [labels[idx] for idx in order], framealpha=0.8)

        # ROI bar graph
        pastacq_roi_mean, pastacq_roi_sd, pastacq_roi_sd_2x = get_metric_stats(p.pastacq, p.metric_list, 'roi_')
        proposed_roi, proposed_roi_sd, proposed_roi_sd_2x = get_metric_stats(p.proposed, p.metric_list, 'roi_')

        ax2.barh(y_pos, [0] * len(p.metric_list), height=0.4, color='white', align='center',
                 label='Price per acre = $' + str(p.args['price_per_acre']))
        ax2.barh(y_pos, pastacq_roi_mean, height=0.4, color='#003865', align='center',
                 label='Past acquisitions average')
        ax2.barh(y_pos, proposed_roi, height=0.0, linewidth='1', yerr=[0.4] * len(p.metric_list),
                 error_kw=dict(ecolor='#E57200', lw=3.5),
                 edgecolor='#E57200', facecolor='#E57200', align='center',
                 label='Proposed acquisition')

        ax2.set_title('Environmental Benefit Score: Return on Investment', fontweight='bold')
        ax2.set_yticks(y_pos)
        ax2.set_yticklabels(p.print_list)
        ax2.set_xlabel('Environmental Benefit Score / Cost')
        handles, labels = ax2.get_legend_handles_labels()
        order = [1, 2, 0]
        ax2.legend([handles[idx] for idx in order], [labels[idx] for idx in order], framealpha=0.8)
        ax2.text(0.01, 0.01, "Generated with version 1.2", transform=fig.transFigure)

        #
        # name = hb.explode_path(shapefile_path)['file_root']
        name = os.path.split(os.path.splitext(shapefile_path)[0])[1]

        plt.tight_layout()
        # plt.show()
        output_path = os.path.join(p.args['output_dir'], 'report_' + name + '_' + hb.pretty_time() + '.pdf')

        fig.savefig(output_path, dpi=fig.dpi, bbox_inches='tight')

        for metric in p.metric_list:
            p.proposed_weighted_score_idx = p.proposed.at[0, 'idx_' + metric + '_mean']
            current_metric_vector[metric] = float(p.proposed_weighted_score_idx)

    if p.args['run_in_batch_mode']:
        print ('RUNNING IN BATCH MODE')
        inputted_dir = p.args['batch_dir']

        num_paths = 0
        for path in hb.list_filtered_paths_recursively(inputted_dir, include_extensions='.shp', depth=1):
            num_paths += 1

        if num_paths == 0:
            raise NameError('Batch mode enabled but there were no shapefiles in ' + str(p.args['batch_dir']))

        output_df_path = hb.ruri(os.path.join(p.args['output_dir'], 'indicator_scores_for_each_parcel.csv'))
        cols_list = ['filename'] + p.metric_list
        output_df = pd.DataFrame(index=np.arange(0, num_paths + 1), columns=cols_list)

        num_paths = 0
        x = 0
        for x, path in enumerate(hb.list_filtered_paths_recursively(inputted_dir, include_extensions='.shp', depth=1)):
            # current_file_root = hb.explode_path(path)['file_root']
            current_file_root = os.path.split(os.path.splitext(path)[0])[1]
            num_paths += 1

            calc_metrics_for_shapefile(path)

            to_append = [current_file_root] + list(current_metric_vector.values())
            output_df.loc[x] = to_append

        # output_df.reset_index(inplace=True)
        output_df.to_csv(output_df_path, index=False)
    else:
        print('RUNNING IN SINGLE INSTANCE MODE')
        calc_metrics_for_shapefile(p.args['shapefile_path'])
        # current_file_root = hb.explode_path(p.args['shapefile_path'])['file_root']
        # to_append = [current_file_root] + list(current_metric_vector.values())
        #
        # output_df.loc[x] = to_append
        # output_df_path = hb.ruri(os.path.join(p.args['output_dir'], current_file_root + '_scores.csv'))
        # # output_df.reset_index(inplace=True)
        #
        # output_df.to_csv(output_df_path, index=False)


def validate(args, limit_to=None):
    validation_error_list = []
    return validation_error_list


if __name__ == '__main__':
    exclude_from_tasks = ['mean_parcel_score',
                          'calc_index',
                          'generate_args',
                          'get_metric_stats',
                          ]

    p = hb.ProjectFlow('report_generator', exclude_from_tasks=exclude_from_tasks)
    p.args = generate_args()

    ui = hb.AutoUI(p)
    p.args = ui.assemble_args()

    ui.run()

    # Enter the Qt application event loop
    EXITCODE = inputs.QT_APP.exec_()
