import os.path
import sys
import xarray as xr
import pandas as pd
import yaml
import calliope
from euro_calliope_specifications import euro_calliope_specifications
import math
import numpy as np


class pipeline:
    def get_wind_pv_shares(self, config,year):
        if year!=1:
            prev_model = self.model_dict['year {}'.format(year - 1)]
        renewables_share = pd.DataFrame(columns=['country', 'tech', 'share'])
        # for energy_cap in prev_model.results.energy_cap:#.energy_cap:
        for techs in config.wind_pv_loc_techs:
            country = techs[:3]
            technology = techs[5:]
            # print(country+" "+technology+ " "+str(prev_model.results.energy_cap.loc[techs].values))
            if year!=1:
                renewables_share = renewables_share.append(
                    {'country': country, 'tech': technology, 'share': prev_model.results.energy_cap.loc[techs].values},
                    ignore_index=True)
            else:
                renewables_share = renewables_share.append(
                    {'country': country, 'tech': technology, 'share': float(0)},
                    ignore_index=True)



        return renewables_share




    def create_yaml_plan(self,fossil_share,year,energy_prod_model):
        print('create_yaml_plan thinks we are in year:', year)
        # create insert general configurations for model
        example_model = open('build/model/national/example-model-template.yaml')
        example_model = yaml.load(example_model, Loader=yaml.FullLoader)
        example_model['group_constraints'] = {}
        example_model['run']['solver']='gurobi'
        example_model['run']['solver_io']='python'

        #TODO Niklas+Bryn: Discuss if those options make sense
        example_model['run']['solver_options']={'Threads':int(sys.argv[4]),'Method': 2, 'Crossover':0,
            'FeasibilityTol':1e-3, 'OptimalityTol':1e-4, 'BarConvTol':1e-4}
        start_date=sys.argv[2]
        end_date=sys.argv[3]
        example_model['model']['subset_time']=['{}-'.format(self.ts_year)+start_date,'{}-'.format(self.ts_year)+end_date]
        for i in fossil_share.index:

            example_model['group_constraints'][i + '_autarky'] = {'demand_share_min': {'electricity': 0.0},
                                                              'locs': [i]}


            #Add share of nuclear power after step 1
            if i in ['BEL']:

                if self.nuclear_scaling_factor_2025<=1 and self.nuclear_scaling_factor_2025>=0:
                    example_model['group_constraints'][i + '_nuclear'] = {
                        'demand_share_equals': {'electricity': self.nuclear_scaling_factor_2025*float(energy_prod_model['nuclear'][i])}, 'locs': [i],
                        'techs': ['nuclear']}
                else:
                    example_model['group_constraints'][i + '_nuclear'] = {
                        'demand_share_equals': {
                            'electricity': float(0)},
                        'locs': [i],
                        'techs': ['nuclear']}
            elif i in ['DEU']:

                if self.nuclear_scaling_factor_2030<=1 and self.nuclear_scaling_factor_2030>=0:
                    example_model['group_constraints'][i + '_nuclear'] = {
                        'demand_share_equals': {'electricity': self.nuclear_scaling_factor_2030*float(energy_prod_model['nuclear'][i])}, 'locs': [i],
                        'techs': ['nuclear']}
                else:
                    example_model['group_constraints'][i + '_nuclear'] = {
                        'demand_share_equals': {
                            'electricity': float(0)},
                        'locs': [i],
                        'techs': ['nuclear']}
            elif i in ['ESP','CHE']:

                if self.nuclear_scaling_factor_2035<=1 and self.nuclear_scaling_factor_2035>=0:
                    example_model['group_constraints'][i + '_nuclear'] = {
                        'demand_share_equals': {'electricity': self.nuclear_scaling_factor_2035*float(energy_prod_model['nuclear'][i])}, 'locs': [i],
                        'techs': ['nuclear']}
                else:
                    example_model['group_constraints'][i + '_nuclear'] = {
                        'demand_share_equals': {
                            'electricity': float(0)},
                        'locs': [i],
                        'techs': ['nuclear']}
            else:
                example_model['group_constraints'][i + '_nuclear'] = {
                    'demand_share_equals': {'electricity': float(energy_prod_model['nuclear'][i])}, 'locs': [i],
                    'techs': ['nuclear']}

            #Add fossil fuel share in year 0
            example_model['group_constraints'][i + '_fossil'] = {
                'demand_share_equals': {'electricity': float(fossil_share[i])}, 'locs': [i], 'techs': ['coal', 'ccgt']}

        #Add wind and pv shares in year 0
        for i in self.renewables_share.index:
            example_model['group_constraints'][
                self.renewables_share['country'][i] + '_' + self.renewables_share['tech'][i]] = {
                    'energy_cap_min': float(0),
                    'locs': [str(self.renewables_share['country'][i])], 'techs': [str(self.renewables_share['tech'][i])]}


        renewable_techs = open('build/model/renewable-techs.yaml')
        renewable_techs = yaml.load(renewable_techs, Loader=yaml.FullLoader)



        with open('build/model/national/example-model-plan-year{}.yaml'.format(year),
                  'w') as outfile:
            yaml.dump(example_model, outfile)  # , default_flow_style=False)

        locations = open('build/model/national/locations-example.yaml')
        locations = yaml.load(locations, Loader=yaml.FullLoader)

        #Add override for initial wind an PV share
        locations['overrides']['vre_initial']={'locations': {}}


        energy_prod = pd.read_csv('Data/VRE_per_country.csv')
        energy_prod=energy_prod.set_index('id')
        for country in energy_prod.index:

            locations['overrides']['vre_initial']['locations']['{}.techs'.format(country)] ={}
            for tech in energy_prod:
                locations['overrides']['vre_initial']['locations']['{}.techs'.format(country)][tech]={'constraints':{'energy_cap_min':float(energy_prod.loc[country, tech])}}
                #print('country:', country,' tech: ',tech, 'share: ', energy_prod.loc[country, tech])
        with open('build/model/national/locations.yaml'.format(year),
                  'w') as outfile:
            yaml.dump(locations, outfile)  # , default_flow_style=False)




    def run_planning_model(self,year, fossil_share,energy_prod_model):
        capacity_factors=self.euro_calliope_specifications.get_capacity_factors()
        self.capacity_factors[year]=capacity_factors

        if year <= 1:
            self.energy_model = calliope.Model(
                'build/model/national/example-model-plan-year{}.yaml'.format(year),scenario='vre_initial,freeze-hydro-capacities')
            #self.energy_model.run()
            print(self.ts_year)

            ## TODO Bryn+Niklas: agree on naming convention
            self.energy_model.to_netcdf('build/model/paper_{}.nc'.format(self.ts_year))
            exit()
            #print('Not loading yaml, but using .nc file')


        #print(self.model_dict)




    def __init__(self):
        self.capacity_factors={}
        self.model_dict={'plan':{}}

        self.baseline_run=False
        self.euro_calliope_specifications=euro_calliope_specifications()
        self.output_path=""
        self.ts_year=2016
