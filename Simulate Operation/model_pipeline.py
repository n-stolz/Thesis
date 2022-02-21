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

        example_model['import']=['../interest-rate.yaml','../renewable-techs.yaml','../storage-techs.yaml','../tech-costs.yaml',
        '../link-techs.yaml','../demand-techs.yaml','locations{}.yaml'.format(sys.argv[1]),'load-shedding.yaml','directional-rooftop.yaml','link-all-neighbours{}.yaml'.format(sys.argv[1])]


        example_model['run']['ensure_feasibility'] = True
        example_model['run']['solver']='gurobi'
        example_model['run']['solver_io']='python'
        example_model['run']['solver_options'] = {'Threads': int(15), 'Method': 2, 'Crossover': 0,
                                                  'FeasibilityTol': 1e-6, 'OptimalityTol': 1e-6, 'BarConvTol': 1e-8,'bigM':10}
        start_date='01-01'
        end_date='12-31'
        example_model['model']['subset_time']=['{}-'.format(year)+start_date,'{}-'.format(year)+end_date]

          # , default_flow_style=False)

        locations = open('build/model/national/locations_template.yaml')
        locations=yaml.load(locations, Loader=yaml.FullLoader)

        #read energy cap from optimized model
        if self.baseline_run==True:
            energy_system = xr.open_dataset(
                os.path.join(self.model_path, 'baseline', 'model_step_1.nc'))
            energy_cap=energy_system.energy_cap.to_dataframe()
            energy_cap['loc_techs']=energy_cap.index
            energy_cap['locs']=energy_cap['loc_techs'].astype(str).str[:3]
            energy_cap['techs']=energy_cap['loc_techs'].astype(str).str[5:]
            energy_cap=energy_cap.drop(['loc_techs'],axis=1)
            energy_cap=energy_cap.reset_index()
            energy_cap=energy_cap.drop(['loc_techs'],axis=1)
        else:
            energy_system = xr.open_dataset(os.path.join(self.model_path, 'adjusted_costs', 'model_step_6.nc'))
            energy_cap=energy_system.energy_cap.to_dataframe()
            energy_cap['loc_techs']=energy_cap.index
            energy_cap['locs']=energy_cap['loc_techs'].astype(str).str[:3]
            energy_cap['techs']=energy_cap['loc_techs'].astype(str).str[5:]
            energy_cap=energy_cap.drop(['loc_techs'],axis=1)
            energy_cap=energy_cap.reset_index()
            energy_cap=energy_cap.drop(['loc_techs'],axis=1)

        for i in energy_cap.index:
            loc=energy_cap['locs'][i]
            tech=energy_cap['techs'][i]
            if 'transmission' not in tech and 'demand_elec' not in tech:
                if 'biofuel' not in tech:
                    try:
                        locations['locations'][loc]['techs'][tech]['constraints']={'energy_cap_equals':float(energy_cap['energy_cap'][i])}
                    except:
                        locations['locations'][loc]['techs'][tech]={'constraints':{}}
                        locations['locations'][loc]['techs'][tech]['constraints']= {'energy_cap_equals':float(
                            energy_cap['energy_cap'][i])}
                else:
                    locations['locations'][loc]['techs'][tech]['constraints']['energy_cap_equals']=float(energy_cap['energy_cap'][i])

        #read storage cap from optimized model
        if self.baseline_run == True:
            energy_system = xr.open_dataset(
                os.path.join(self.model_path, 'baseline', 'model_step_1.nc'))
            storage_cap=energy_system.storage_cap.to_dataframe()
            storage_cap['loc_techs_store']=storage_cap.index
            storage_cap['locs']=storage_cap['loc_techs_store'].astype(str).str[:3]
            storage_cap['techs']=storage_cap['loc_techs_store'].astype(str).str[5:]
            storage_cap=storage_cap.drop(['loc_techs_store'],axis=1)
            storage_cap=storage_cap.reset_index()
            storage_cap=storage_cap.drop(['loc_techs_store'],axis=1)
        else:
            energy_system = xr.open_dataset(os.path.join(self.model_path, 'adjusted_costs', 'model_step_6.nc'))
            storage_cap=energy_system.storage_cap.to_dataframe()
            storage_cap['loc_techs_store']=storage_cap.index
            storage_cap['locs']=storage_cap['loc_techs_store'].astype(str).str[:3]
            storage_cap['techs']=storage_cap['loc_techs_store'].astype(str).str[5:]
            storage_cap=storage_cap.drop(['loc_techs_store'],axis=1)
            storage_cap=storage_cap.reset_index()
            storage_cap=storage_cap.drop(['loc_techs_store'],axis=1)

        for i in storage_cap.index:
            loc = storage_cap['locs'][i]
            tech = storage_cap['techs'][i]

            if 'transmission' not in tech:
                locations['locations'][loc]['techs'][tech]['constraints']['storage_cap_equals'] =  float(storage_cap['storage_cap'][i])



        nuclear_prod=float(energy_system.carrier_prod[energy_system.carrier_prod.loc_tech_carriers_prod.str.contains('nuclear')].sum())
        #decrease nuclear production if optimization year was leap year to ensure model feasibility
        if float(sys.argv[1])==2012 or sys.argv[1]==2016:
            nuclear_prod=nuclear_prod*(365/366)
        example_model['group_constraints']['nuclear_constraint']['carrier_prod_equals']['electricity']=nuclear_prod
        with open('build/model/national/example-model-plan-year{}.yaml'.format(sys.argv[1]),
                  'w') as outfile:
            yaml.dump(example_model, outfile)
        with open('build/model/national/locations{}.yaml'.format(sys.argv[1]),'w') as outfile:
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
        with open('build/model/national/link-all-neighbours{}.yaml'.format(sys.argv[1]),'w') as outfile:
            yaml.dump(link,outfile)







    def run_planning_model(self,year):


            calliope.set_log_verbosity("INFO")
            self.energy_model = calliope.Model(
                 'build/model/national/example-model-plan-year{}.yaml'.format(sys.argv[1]),scenario='load-shedding')
            self.energy_model.save_commented_model_yaml('/cluster/scratch/nstolz/model.yaml')
            #self.energy_model.to_netcdf('/cluster/work/cpesm/shared/incentive-scheming/hydrogen_issue/input_model_optimization_2013_tight_tol.nc')
            self.energy_model.run()
            # self.energy_model.to_netcdf('build/model/model_{}.nc'.format(self.ts_year))
            # exit()

            self.model_dict['year {}'.format(year)] = self.energy_model
        #self.energy_model.to_netcdf('build/model/model_{}.nc'.format(year))

        #print(self.model_dict)


    def save_model(self,year):
        #self.model_dict['year {}'.format(year)].to_netcdf('/cluster/work/cpesm/shared/incentive-scheming/hydrogen_issue/output_model_optimization_2013_2010_operation_tight_tol.nc')
        if self.baseline_run==False:
            self.model_dict['year {}'.format(year)].to_netcdf(os.path.join(self.output_path,'adjusted_costs/model_step_{}.nc'.format(year)))

        else:
            self.model_dict['year {}'.format(year)].to_netcdf(os.path.join(self.output_path,'baseline/model_step_{}.nc'.format(year)))

    def __init__(self):



        self.model_dict={'plan':{}}

        #After running scenario baseline_run will be set to True to solve baseline with no incentives
        self.baseline_run=False

        self.output_path=""
        self.ts_year=2016

        #self.renewables_share=self.get_wind_pv_shares(config, year)
