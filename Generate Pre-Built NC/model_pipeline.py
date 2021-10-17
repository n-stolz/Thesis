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

    def get_production_timeseries(self,year):
        if self.baseline_run==False:
            carrier_prod = pd.read_csv(os.path.join(self.output_path,'adjusted_costs/model_csv_year_{}/results_carrier_prod.csv'.format(year - 1)))
            carrier_con = pd.read_csv(os.path.join(self.output_path,'adjusted_costs/model_csv_year_{}/results_carrier_con.csv'.format(year - 1)))
            time_steps = pd.read_csv(os.path.join(self.output_path,'adjusted_costs/model_csv_year_{}/inputs_timestep_resolution.csv'.format(year - 1)))
        else:
            carrier_prod = pd.read_csv(os.path.join(self.output_path,'baseline_model/model_csv_year_{}/results_carrier_prod.csv'.format(year - 1)))
            carrier_con = pd.read_csv(os.path.join(self.output_path,'baseline_model/model_csv_year_{}/results_carrier_con.csv'.format(year - 1)))
            time_steps = pd.read_csv(os.path.join(self.output_path,'baseline_model/model_csv_year_{}/inputs_timestep_resolution.csv'.format(year - 1)))
        electricity_net = pd.DataFrame()
        carrier_prod=carrier_prod[carrier_prod['techs'].isin(['roof_mounted_pv', 'open_field_pv', 'wind_onshore_competing',
                                                              'wind_onshore_monopoly','wind_offshore'])]

        carrier_con = carrier_con[carrier_con['techs'].isin(['demand_elec'])]


        electricity_net = carrier_prod.groupby(['locs', 'techs', 'timesteps']).sum().add(
            carrier_con.groupby(['locs', 'techs', 'timesteps']).sum(), fill_value=0).reset_index()
        electricity_net = electricity_net.fillna(0)

        electricity_net['residual'] = electricity_net['carrier_prod'] + electricity_net['carrier_con']

        electricity_net['timesteps']=electricity_net['timesteps'].astype('datetime64[ns]')

        self.residual_load_country = electricity_net.groupby(['locs', 'timesteps']).sum().reset_index()
        self.residual_load_europe=electricity_net.groupby(['timesteps']).sum().reset_index()

        return time_steps

    def get_national_sd(self, name, group, time_range,year):

        self.standard_deviations_national[name] = {}
        self.standard_deviations_national_daily[name]={}
        self.standard_deviations_national_weekly[name]={}
        self.standard_deviations_national_monthly[name]={}
        self.standard_deviations_national_seasonally[name]={}

        group['residual'] = group['residual'] / group['residual'].abs().mean()

        country = group.reset_index()
        country_daily = country.set_index('timesteps').resample('D').sum()
        country_weekly = country.set_index('timesteps').resample('W').sum()
        country_monthly = country.set_index('timesteps').resample('M').sum()
        country_seasonally= country.set_index('timesteps').resample('Q').sum()

        for key in self.capacity_factors[year-1].keys():
            #Here seems to be the issue
            cf = self.capacity_factors[year-1][key][['time', name]]

            #norm with mean cf to make comparison between technologies fair


            cf = cf[cf['time'].isin(time_range)]
            cf['time']=cf['time'].astype('datetime64[ns]')

            cf[name] = cf[name] / cf[name].abs().mean()
            #print(cf)
            cf_daily=cf.set_index('time').resample('D').sum()
            cf_weekly=cf.set_index('time').resample('W').sum()
            cf_monthly=cf.set_index('time').resample('M').sum()
            cf_seasonally=cf.set_index('time').resample('Q').sum()

            #cf_daily[name]=cf_daily[cf_daily.columns[0]]
            #print(cf_daily.reset_index()[name])
            self.standard_deviations_national[name][key] = (cf.reset_index()[name] + country.reset_index()['residual']).std()
            self.standard_deviations_national_daily[name][key] = (cf_daily.reset_index()[name] + country_daily.reset_index()['residual']).std()
            self.standard_deviations_national_weekly[name][key] = (
                        cf_weekly.reset_index()[name] + country_weekly.reset_index()['residual']).std()
            self.standard_deviations_national_monthly[name][key] = (
                        cf_monthly.reset_index()[name] + country_monthly.reset_index()['residual']).std()
            self.standard_deviations_national_seasonally[name][key] = (
                        cf_seasonally.reset_index()[name] + country_seasonally.reset_index()['residual']).std()

    def get_european_sd(self, name,time_range,year):
        self.standard_deviations_europe[name]={}
        self.standard_deviations_europe_daily[name]={}
        self.standard_deviations_europe_weekly[name]={}
        self.standard_deviations_europe_monthly[name]={}
        self.standard_deviations_europe_seasonally[name]={}

        self.residual_load_europe['residual']=self.residual_load_europe['residual']/self.residual_load_europe['residual'].abs().mean()

        europe_sd_daily=self.residual_load_europe.set_index('timesteps')['residual'].resample('D').sum()
        europe_sd_weekly = self.residual_load_europe.set_index('timesteps')['residual'].resample('W').sum()
        europe_sd_monthly = self.residual_load_europe.set_index('timesteps')['residual'].resample('M').sum()
        europe_sd_seasonally = self.residual_load_europe.set_index('timesteps')['residual'].resample('Q').sum()


        for key in self.capacity_factors[year-1].keys():
            cf = self.capacity_factors[year-1][key][['time', name]]
            cf = cf[cf['time'].isin(time_range)]
            cf[name] = cf[name] / cf[name].mean()
            cf['time'] = cf['time'].astype('datetime64[ns]')
            cf_daily=cf.set_index('time').resample('D').sum()
            cf_weekly=cf.set_index('time').resample('W').sum()
            cf_monthly=cf.set_index('time').resample('M').sum()
            cf_seasonally=cf.set_index('time').resample('Q').sum()

            self.standard_deviations_europe[name][key] = (cf.reset_index()[name] +self.residual_load_europe.reset_index()['residual']).std()
            self.standard_deviations_europe_daily[name][key] = (cf_daily.reset_index()[name] + europe_sd_daily.reset_index()['residual']).std()
            self.standard_deviations_europe_weekly[name][key] = (
                        cf_weekly.reset_index()[name] + europe_sd_weekly.reset_index()['residual']).std()
            self.standard_deviations_europe_monthly[name][key] = (
                        cf_monthly.reset_index()[name] + europe_sd_monthly.reset_index()['residual']).std()
            self.standard_deviations_europe_seasonally[name][key] = (
                        cf_seasonally.reset_index()[name] + europe_sd_seasonally.reset_index()['residual']).std()



    def get_national_score(self):
        sd_list=[self.standard_deviations_national,self.standard_deviations_national_daily,self.standard_deviations_national_weekly,self.standard_deviations_national_monthly,self.standard_deviations_national_seasonally]



        for standard_deviation in sd_list:
            standard_deviations_df=pd.DataFrame.from_dict(standard_deviation)

            for country in standard_deviations_df:
                if country not in self.national_score.keys():
                    self.national_score[country]={}
                sd_max=standard_deviations_df[country].max()
                sd_min=standard_deviations_df[country].min()
                for i in standard_deviations_df[country].index:

                    sd=standard_deviations_df[country][i]

                    if sd_max!=sd_min and not math.isnan(sd):
                        try:
                            self.national_score[country][i]+=(1-(sd-sd_min)/(sd_max-sd_min))
                        except:
                            self.national_score[country][i] = (1 - (sd - sd_min) / (sd_max - sd_min))

                    else:
                        try:
                            self.national_score[country][i]+=0
                        except:
                            self.national_score[country][i] = 0





    def get_european_score(self):
        sd_list = [self.standard_deviations_europe, self.standard_deviations_europe_daily,
                   self.standard_deviations_europe_weekly, self.standard_deviations_europe_monthly,
                   self.standard_deviations_europe_seasonally]
        for standard_deviation in sd_list:
            standard_deviations_df = pd.DataFrame.from_dict(standard_deviation)
            sd_max = np.nanmax(standard_deviations_df.to_numpy())
            sd_min = np.nanmin(standard_deviations_df.to_numpy())

            for country in standard_deviations_df:

                if country not in self.european_score.keys():
                    self.european_score[country]={}


                for i in standard_deviations_df[country].index:

                    sd=standard_deviations_df[country][i]
                    if sd_max!=sd_min and not math.isnan(sd):
                        try:
                            self.european_score[country][i]+=(1-(sd-sd_min)/(sd_max-sd_min))
                        except:
                            self.european_score[country][i] = (1 - (sd - sd_min) / (sd_max - sd_min))


                    else:
                        try:
                            self.european_score[country][i]+=0
                        except:
                            self.european_score[country][i] = 0



    def adjust_costs(self, year):
        all_locations = open('build/model/national/locations.yaml')
        all_locations = yaml.load(all_locations, Loader=yaml.FullLoader)


        for country in all_locations['locations'].keys():

            self.incentive_dict[country]={}
            for tech in self.national_score[country].keys():
                if tech=='wind_onshore':
                    self.energy_model.backend.update_param('cost_om_prod',
                                                           {('monetary', country + '::' + tech+'_competing'): self.cost_calculator(
                                                               country, tech)})
                    self.energy_model.backend.update_param('cost_om_prod',
                                                        {('monetary', country+'::'+tech+'_monopoly'): self.cost_calculator(country, tech)})
                else:
                    self.energy_model.backend.update_param('cost_om_prod',{('monetary', country + '::' + tech): self.cost_calculator(
                                                               country, tech)})
                # if tech != 'wind_onshore':
                #     example_model['overrides']['cost_adjustments']['locations'][country]['techs'][tech] = {
                #         'costs': {'monetary': {'om_prod': self.cost_calculator(country, tech)}}}
                #     # example_model['overrides']['locations'][country]['techs']={tech:{'costs':{'monetary'}}['monetary']['om_prod']['costs']['om_prod']=cost_calculator()
                # else:
                #     example_model['overrides']['cost_adjustments']['locations'][country]['techs'][
                #         'wind_onshore_competing'] = {'costs': {'monetary': {'om_prod': self.cost_calculator(country, tech)}}}
                #     example_model['overrides']['cost_adjustments']['locations'][country]['techs'][
                #         'wind_onshore_monopoly'] = {'costs': {'monetary': {'om_prod': self.cost_calculator(country, tech)}}}
        pd.DataFrame.from_dict(self.incentive_dict).to_csv(os.path.join(self.output_path,'incentives_step_{}'.format(year)))

    def cost_calculator(self, country, tech):
        x = (self.national_score[country][tech]+self.european_score[country][tech])/2
        incentive= 2*(x/10000)
        print(self.VRE_om_prod)
        if math.isnan(x) or math.isnan(self.VRE_om_prod[tech]+x):
            print(tech,country)
            self.incentive_dict[country][tech]= np.nan
            return self.VRE_om_prod[tech]
        else:
            self.incentive_dict[country][tech]=incentive
            return (float(self.VRE_om_prod[tech] - incentive))

    def create_yaml_plan(self,fossil_share,year,energy_prod_model):
        print('create_yaml_plan thinks we are in year:', year)
        example_model = open('build/model/national/example-model-template.yaml')
        example_model = yaml.load(example_model, Loader=yaml.FullLoader)
        example_model['group_constraints'] = {}
        example_model['run']['solver']='gurobi'
        example_model['run']['solver_io']='python'
        example_model['run']['solver_options']={'Threads':int(sys.argv[4]),'Method': 2, 'Crossover':0,
            'FeasibilityTol':1e-3, 'OptimalityTol':1e-4, 'BarConvTol':1e-4}
        start_date=sys.argv[2]
        end_date=sys.argv[3]
        example_model['model']['subset_time']=['{}-'.format(self.ts_year)+start_date,'{}-'.format(self.ts_year)+end_date]
        for i in fossil_share.index:
            if year==1:
                example_model['group_constraints'][i + '_autarky'] = {'demand_share_min': {'electricity': 0.0},
                                                              'locs': [i]}

            if i in ['DEU','BEL','ESP','CHE']:

                if self.nuclear_scaling_factor<=1 and self.nuclear_scaling_factor>=0:
                    example_model['group_constraints'][i + '_nuclear'] = {
                        'demand_share_equals': {'electricity': self.nuclear_scaling_factor*float(energy_prod_model['nuclear'][i])}, 'locs': [i],
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

            example_model['group_constraints'][i + '_fossil'] = {
                'demand_share_equals': {'electricity': float(fossil_share[i])}, 'locs': [i], 'techs': ['coal', 'ccgt']}

        for i in self.renewables_share.index:
            example_model['group_constraints'][
                self.renewables_share['country'][i] + '_' + self.renewables_share['tech'][i]] = {
                    'energy_cap_min': float(0),
                    'locs': [str(self.renewables_share['country'][i])], 'techs': [str(self.renewables_share['tech'][i])]}


        renewable_techs = open('build/model/renewable-techs.yaml')
        renewable_techs = yaml.load(renewable_techs, Loader=yaml.FullLoader)
        for tech in ['wind_offshore', 'wind_onshore', 'open_field_pv', 'roof_mounted_pv']:
            try:
                self.VRE_om_prod[tech] = renewable_techs['techs'][tech]['costs']['monetary']['om_prod']

            except:
                self.VRE_om_prod[tech] = renewable_techs['tech_groups'][tech]['costs']['monetary']['om_prod']
        #     # print(tech, renewable_techs['tech_groups'][tech]['costs']['monetary']['om_prod'])
        #
        #     grouped = self.residual_load_country[['locs', 'timesteps', 'residual']].groupby('locs')
        #     time_range = self.time_steps['timesteps'].to_list()
        #     for name, group in grouped:
        #
        #         self.get_national_sd(name, group, time_range,year)
        #         self.get_european_sd(name, time_range,year)
        #     self.get_national_score()
        #     self.get_european_score()
        #
        #     if self.baseline_run==False:
        #         example_model = self.adjust_costs(example_model,year)

        with open('build/model/national/example-model-plan-year{}.yaml'.format(year),
                  'w') as outfile:
            yaml.dump(example_model, outfile)  # , default_flow_style=False)

        locations = open('build/model/national/locations-example.yaml')
        locations = yaml.load(locations, Loader=yaml.FullLoader)

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
    def energy_autarky(self,year, fossil_share,energy_prod_model):


        for i in fossil_share.index:

            self.energy_model.backend.update_param('group_demand_share_min',{('electricity','{}_autarky'.format(i)):0.95})

            #print(self.energy_model.inputs['group_demand_share_min'])
            if i in ['DEU','BEL','ESP','CHE']:
                if self.nuclear_scaling_factor<=1 and self.nuclear_scaling_factor>=0:
                    self.energy_model.backend.update_param('group_demand_share_equals',{('electricity','{}_nuclear'.format(i)):self.nuclear_scaling_factor*float(energy_prod_model['nuclear'][i])})

                else:
                    self.energy_model.backend.update_param('group_demand_share_equals',{('electricity','{}_nuclear'.format(i)): float(0)})
            else:
                self.energy_model.backend.update_param('group_demand_share_equals',
                                                       {('electricity', '{}_nuclear'.format(i)): float(energy_prod_model['nuclear'][i])})

            self.energy_model.backend.update_param('group_demand_share_equals',
                                                  {('electricity', '{}_fossil'.format(i)): float(fossil_share[i])})

        for i in self.renewables_share.index:
            self.energy_model.backend.update_param('group_energy_cap_min',
                                                   {(self.renewables_share['country'][i] + '_' + self.renewables_share['tech'][i]): float(self.renewables_share['share'][i])})

       #adjust technology costs

        grouped = self.residual_load_country[['locs', 'timesteps', 'residual']].groupby('locs')
        time_range = self.time_steps['timesteps'].to_list()
        for name, group in grouped:

            self.get_national_sd(name, group, time_range,year)
            self.get_european_sd(name, time_range,year)

        self.get_national_score()
        self.get_european_score()

        pd.DataFrame.from_dict(self.standard_deviations_national).to_csv(os.path.join(self.output_path,'sd_national_hourly_step_{}'.format(year)))
        pd.DataFrame.from_dict(self.standard_deviations_national_daily).to_csv(
            os.path.join(self.output_path, 'sd_national_daily_step_{}'.format(year)))
        pd.DataFrame.from_dict(self.standard_deviations_national_weekly).to_csv(
            os.path.join(self.output_path, 'sd_national_weekly_step_{}'.format(year)))
        pd.DataFrame.from_dict(self.standard_deviations_national_monthly).to_csv(
            os.path.join(self.output_path, 'sd_national_monthly_step_{}'.format(year)))
        pd.DataFrame.from_dict(self.standard_deviations_national_seasonally).to_csv(
            os.path.join(self.output_path, 'sd_national_seasonally_step_{}'.format(year)))

        pd.DataFrame.from_dict(self.standard_deviations_europe).to_csv(os.path.join(self.output_path,'sd_europe_hourly_step_{}'.format(year)))
        pd.DataFrame.from_dict(self.standard_deviations_europe_daily).to_csv(
            os.path.join(self.output_path, 'sd_europe_daily_step_{}'.format(year)))
        pd.DataFrame.from_dict(self.standard_deviations_europe_weekly).to_csv(
            os.path.join(self.output_path, 'sd_europe_weekly_step_{}'.format(year)))
        pd.DataFrame.from_dict(self.standard_deviations_europe_monthly).to_csv(
            os.path.join(self.output_path, 'sd_europe_monthly_step_{}'.format(year)))
        pd.DataFrame.from_dict(self.standard_deviations_europe_seasonally).to_csv(
            os.path.join(self.output_path, 'sd_europe_seasonally_step_{}'.format(year)))



        print('European Score:', self.european_score)
        print('National Score:', self.national_score)

        if self.baseline_run==False:
            self.adjust_costs(year)


    def run_planning_model(self,year, fossil_share,energy_prod_model):
        capacity_factors=self.euro_calliope_specifications.get_capacity_factors()
        self.capacity_factors[year]=capacity_factors

        if year <= 1:
            self.energy_model = calliope.Model(
                'build/model/national/example-model-plan-year{}.yaml'.format(year),scenario='vre_initial,freeze-hydro-capacities')
            #self.energy_model.run()
            print(self.ts_year)
            self.energy_model.to_netcdf('build/model/model_4h_00_autarky_scenario.nc')
            exit()
            #print('Not loading yaml, but using .nc file')


        #print(self.model_dict)


    def save_model(self,year):
        if self.baseline_run==False:
            self.model_dict['year {}'.format(year)].to_csv(os.path.join(self.output_path,'adjusted_costs/model_csv_year_{}'.format(year)))
        else:
            self.model_dict['year {}'.format(year)].to_csv(os.path.join(self.output_path,'baseline/model_csv_year_{}'.format(year)))

    def __init__(self):
        self.capacity_factors={}
        self.model_dict={'plan':{}}
        self.ranking={}

        self.standard_deviations_national={}
        self.standard_deviations_national_daily={}
        self.standard_deviations_national_weekly = {}
        self.standard_deviations_national_monthly = {}
        self.standard_deviations_national_seasonally = {}

        self.standard_deviations_europe_daily={}
        self.standard_deviations_europe_weekly={}
        self.standard_deviations_europe_monthly={}
        self.standard_deviations_europe_seasonally={}

        self.national_score={}
        self.national_score_daily={}
        self.national_score_weekly = {}
        self.national_score_monthly = {}
        self.national_score_seasonally = {}

        self.standard_deviations_europe = {}
        self.VRE_om_prod = {}
        self.national_score={}
        self.european_score={}
        self.baseline_run=False
        self.euro_calliope_specifications=euro_calliope_specifications()
        self.output_path=""
        self.ts_year=2016
        self.nuclear_scaling_factor=0
        self.incentive_dict={}
        #self.renewables_share=self.get_wind_pv_shares(config, year)
