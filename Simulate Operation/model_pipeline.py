import os.path
import sys
import xarray as xr
import pandas as pd
import yaml
import calliope
import math
import numpy as np


class pipeline:

    #Adjust Yaml file for model and include the correct energy caps
    def create_yaml_operate(self,year,energy_prod_model):

        example_model = open('build/model/national/example-model-plan.yaml')
        example_model = yaml.load(example_model, Loader=yaml.FullLoader)

        example_model['run']['ensure_feasibility'] = True
        example_model['run']['solver']='gurobi'
        example_model['run']['solver_io']='python'
        example_model['run']['solver_options'] = {'Threads': int(sys.argv[4]), 'Method': 2, 'Crossover': 0,
                                                  'FeasibilityTol': 1e-3, 'OptimalityTol': 1e-4, 'BarConvTol': 1e-4}
        start_date=sys.argv[2]
        end_date=sys.argv[3]
        example_model['model']['subset_time']=['{}-'.format(year)+start_date,'{}-'.format(year)+end_date]

        with open('build/model/national/example-model-plan-year{}.yaml'.format(year),
                  'w') as outfile:
            yaml.dump(example_model, outfile)  # , default_flow_style=False)

        locations = open('build/model/national/locations_template.yaml')
        locations=yaml.load(locations, Loader=yaml.FullLoader)

        #read energy cap from optimized model
        if self.baseline_run==True:
            energy_cap=pd.read_csv(os.path.join(self.model_path,'baseline','model_csv_year_1', 'results_energy_cap.csv'))
        else:
            energy_cap = pd.read_csv(os.path.join(self.model_path, 'adjusted_costs','model_csv_year_6', 'results_energy_cap.csv'))
        for i in energy_cap.index:
            loc=energy_cap['locs'][i]
            tech=energy_cap['techs'][i]
            if 'transmission' not in tech and 'demand_elec' not in tech:
                try:
                    locations['locations'][loc]['techs'][tech]['constraints']={'energy_cap_equals':float(energy_cap['energy_cap'][i])}
                except:
                    locations['locations'][loc]['techs'][tech]={'constraints':{}}
                    locations['locations'][loc]['techs'][tech]['constraints']= {'energy_cap_equals':float(
                        energy_cap['energy_cap'][i])}

        #read storage cap from optimized model
        if self.baseline_run == True:
            storage_cap = pd.read_csv(
                os.path.join(self.model_path, 'baseline', 'model_csv_year_1', 'results_storage_cap.csv'))
        else:
            storage_cap = pd.read_csv(os.path.join(self.model_path, 'adjusted_costs', 'model_csv_year_6',
                                                  'results_storage_cap.csv'))
        for i in storage_cap.index:
            loc = storage_cap['locs'][i]
            tech = storage_cap['techs'][i]

            if 'transmission' not in tech:
                locations['locations'][loc]['techs'][tech]['constraints']['storage_cap_equals'] =  float(storage_cap['storage_cap'][i])

        with open('build/model/national/locations.yaml','w') as outfile:
            yaml.dump(locations,outfile)


        link = open('build/model/national/link-all-neighbours_template.yaml')
        link=yaml.load(link, Loader=yaml.FullLoader)

        #insert transmission techs
        for i in energy_cap.index:
            loc=energy_cap['locs'][i]
            tech=energy_cap['techs'][i]
            if 'transmission' in tech:
                countryA=energy_cap['locs'][i]
                countryB=energy_cap['techs'][i][-3:]
                AB_key=countryA+','+countryB
            try:
                link['links'][AB_key]['techs']['ac_transmission']={'constraints':{'energy_cap_equals':float(energy_cap['energy_cap'][i])}}
            except:
                pass
        with open('build/model/national/link-all-neighbours.yaml','w') as outfile:
            yaml.dump(link,outfile)







    def run_planning_model(self,year):



            self.energy_model = calliope.Model(
                 'build/model/national/example-model-plan-year{}.yaml'.format(year))
            self.energy_model.save_commented_model_yaml('/cluster/scratch/nstolz/model.yaml')
            self.energy_model.run()
            # self.energy_model.to_netcdf('build/model/model_{}.nc'.format(self.ts_year))
            # exit()

            self.model_dict['year {}'.format(year)] = self.energy_model
        #self.energy_model.to_netcdf('build/model/model_{}.nc'.format(year))

        #print(self.model_dict)


    def save_model(self,year):
        if self.baseline_run==False:
            self.model_dict['year {}'.format(year)].to_csv(os.path.join(self.output_path,'adjusted_costs/model_csv_year_{}'.format(year)))
        else:
            self.model_dict['year {}'.format(year)].to_csv(os.path.join(self.output_path,'baseline/model_csv_year_{}'.format(year)))


    def __init__(self):



        self.model_dict={'plan':{}}

        #After running scenario baseline_run will be set to True to solve baseline with no incentives
        self.baseline_run=False

        self.output_path=""
        self.ts_year=2016

        #self.renewables_share=self.get_wind_pv_shares(config, year)
