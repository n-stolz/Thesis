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

    # gets wind and pv capacity of previous time step. CAUTION: name says shares, but it actually returns capacity -> TODO: Change name of function and variable to ..._cap
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

    #returns residual load on national an european level
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

        #Generation timeseries from wind and solar power
        carrier_prod=carrier_prod[carrier_prod['techs'].isin(['roof_mounted_pv', 'open_field_pv', 'wind_onshore_competing',
                                                              'wind_onshore_monopoly','wind_offshore'])]
        #Demand timeseries without electricity that goes to storage and is transmited
        carrier_con = carrier_con[carrier_con['techs'].isin(['demand_elec'])]

        #generation-demand
        electricity_net = carrier_prod.groupby(['locs', 'techs', 'timesteps']).sum().add(
            carrier_con.groupby(['locs', 'techs', 'timesteps']).sum(), fill_value=0).reset_index()
        electricity_net = electricity_net.fillna(0)

        electricity_net['residual'] = electricity_net['carrier_prod'] + electricity_net['carrier_con']

        electricity_net['timesteps']=electricity_net['timesteps'].astype('datetime64[ns]')

        self.residual_load_country = electricity_net.groupby(['locs', 'timesteps']).sum().reset_index()
        self.residual_load_europe=electricity_net.groupby(['timesteps']).sum().reset_index()

        return time_steps

    # get sd of residual load on multiple temporal horizons if one unit of a technology is added
    def get_national_sd(self, name, group, time_range,year):

        #Add name of country as key
        self.standard_deviations_national[name] = {}
        self.standard_deviations_national_daily[name]={}
        self.standard_deviations_national_weekly[name]={}
        self.standard_deviations_national_monthly[name]={}
        self.standard_deviations_national_seasonally[name]={}

        #resample national residual load on daily, weekly, monthly and quaterly level
        country = group.reset_index()
        country_daily = country.set_index('timesteps').resample('D').sum()
        country_weekly = country.set_index('timesteps').resample('W').sum()
        country_monthly = country.set_index('timesteps').resample('M').sum()
        country_seasonally= country.set_index('timesteps').resample('Q').sum()

        # This was used in a previous version. Not needed atm. TODO: remove if not needed in the future
        self.sd_baseline_national[name] = {'hourly': country.reset_index()['residual'].std(),
                                  'daily': country_daily.reset_index()['residual'].std(),
                                  'weekly': country_weekly.reset_index()['residual'].std(),
                                  'monthly': country_monthly.reset_index()['residual'].std(),
                                  'seasonally': country_seasonally.reset_index()['residual'].std()}
        print(self.sd_baseline_national)


        #loop through generation technologies
        for key in self.capacity_factors[year-1].keys():

            #get capacity factor of specific tech during the timerange of interest and bring to right formate
            cf = self.capacity_factors[year-1][key][['time', name]]
            cf = cf[cf['time'].isin(time_range)]
            cf['time']=cf['time'].astype('datetime64[ns]')


            #resample capacity factors on daily, weekly, monthly and quaterly level
            cf_daily=cf.set_index('time').resample('D').mean()
            cf_weekly=cf.set_index('time').resample('W').mean()
            cf_monthly=cf.set_index('time').resample('M').mean()
            cf_seasonally=cf.set_index('time').resample('Q').mean()

            #make a list of shoreless countries to ignore them for offshore wind scores
            if (cf[name] == 0).all() and key=='wind_offshore':
                self.shoreless_countries.append(name)

           #add capacity factor time series to residual load time series and take sd
            self.standard_deviations_national[name][key] = (cf.reset_index()[name] + country.reset_index()['residual']).std()
            self.standard_deviations_national_daily[name][key] = (cf_daily.reset_index()[name] + country_daily.reset_index()['residual']).std()
            self.standard_deviations_national_weekly[name][key] = (
                        cf_weekly.reset_index()[name] + country_weekly.reset_index()['residual']).std()
            self.standard_deviations_national_monthly[name][key] = (
                        cf_monthly.reset_index()[name] + country_monthly.reset_index()['residual']).std()
            self.standard_deviations_national_seasonally[name][key] = (
                        cf_seasonally.reset_index()[name] + country_seasonally.reset_index()['residual']).std()

    def get_european_sd(self, name,time_range,year):
        # Add name of country as key
        self.standard_deviations_europe[name]={}
        self.standard_deviations_europe_daily[name]={}
        self.standard_deviations_europe_weekly[name]={}
        self.standard_deviations_europe_monthly[name]={}
        self.standard_deviations_europe_seasonally[name]={}

        # resample national residual load on daily, weekly, monthly and quaterly level
        europe_sd_daily=self.residual_load_europe.set_index('timesteps')['residual'].resample('D').sum()
        europe_sd_weekly = self.residual_load_europe.set_index('timesteps')['residual'].resample('W').sum()
        europe_sd_monthly = self.residual_load_europe.set_index('timesteps')['residual'].resample('M').sum()
        europe_sd_seasonally = self.residual_load_europe.set_index('timesteps')['residual'].resample('Q').sum()

        # This was used in a previous version. Not needed atm. TODO: remove if not needed in the future
        self.sd_baseline_europe={'hourly': self.residual_load_europe.reset_index()['residual'].std(),'daily': europe_sd_daily.reset_index()['residual'].std(), 'weekly':europe_sd_weekly.reset_index()['residual'].std(),'monthly':europe_sd_monthly.reset_index()['residual'].std(),
                                 'seasonally':europe_sd_seasonally.reset_index()['residual'].std()}
        print(self.sd_baseline_europe)

        # loop through generation technologies
        for key in self.capacity_factors[year-1].keys():
            # get capacity factor of specific tech during the timerange of interest and bring to right formate
            cf = self.capacity_factors[year-1][key][['time', name]]
            cf = cf[cf['time'].isin(time_range)]
            cf['time'] = cf['time'].astype('datetime64[ns]')

            # resample capacity factors on daily, weekly, monthly and quaterly level
            cf_daily=cf.set_index('time').resample('D').mean()
            cf_weekly=cf.set_index('time').resample('W').mean()
            cf_monthly=cf.set_index('time').resample('M').mean()
            cf_seasonally=cf.set_index('time').resample('Q').mean()

            # How big is the capacity that is (hypothetically) added to get new residual load. Quite unnessecary.
            capacity=1
            # add capacity factor time series to residual load time series and take sd
            self.standard_deviations_europe[name][key] = (capacity*cf.reset_index()[name] +self.residual_load_europe.reset_index()['residual']).std()
            self.standard_deviations_europe_daily[name][key] = (capacity*cf_daily.reset_index()[name] + europe_sd_daily.reset_index()['residual']).std()
            self.standard_deviations_europe_weekly[name][key] = (
                        capacity*cf_weekly.reset_index()[name] + europe_sd_weekly.reset_index()['residual']).std()
            self.standard_deviations_europe_monthly[name][key] = (
                        capacity*cf_monthly.reset_index()[name] + europe_sd_monthly.reset_index()['residual']).std()
            self.standard_deviations_europe_seasonally[name][key] = (
                        capacity*cf_seasonally.reset_index()[name] + europe_sd_seasonally.reset_index()['residual']).std()



    def get_national_score(self):
       #dictionary of national residual loads' sd. TODO: rename to sd_dict
        sd_list = {'hourly':self.standard_deviations_national, 'daily':self.standard_deviations_national_daily,
                   'weekly': self.standard_deviations_national_weekly, 'monthly':self.standard_deviations_national_monthly,
                   'seasonally':self.standard_deviations_national_seasonally}

        self.national_score = {}

        #iterate through dict to get score for all time horizons
        for key in sd_list:
            standard_deviations_df=pd.DataFrame.from_dict(sd_list[key])

            #add time horizon (hourly, daily, weekly...) to dict
            self.national_score_dict[key]={}

            for country in standard_deviations_df:
                #add country to dict
                self.national_score_dict[key][country]={}
                if country not in self.national_score.keys():
                    self.national_score[country]={}

                #get smallest and largest sd throughout all countries and VRE techs
                sd_max=standard_deviations_df[country].max()
                sd_min=standard_deviations_df[country].min()
                for i in standard_deviations_df[country].index:

                    sd=standard_deviations_df[country][i]

                    if sd_max!=sd_min and not math.isnan(sd):

                        #add scores of multiple time horizons. Goes to "except" if self.national_score[country][i] is not defined yet -> first iteration
                        try:
                            self.national_score[country][i]+=self.score_weight[key]*(1-(sd-sd_min)/(sd_max-sd_min))
                            self.national_score_dict[key][country][i]=(1-(sd-sd_min)/(sd_max-sd_min))
                        except:
                            self.national_score[country][i] = self.score_weight[key]*(1 - (sd - sd_min) / (sd_max - sd_min))
                            self.national_score_dict[key][country][i] =(1 - (sd - sd_min) / (sd_max - sd_min))

                    # if sd is nan the or sd_min=sd_max the score is 0. Both should not happen if the time range is larger than a quarter of a year
                    else:
                        try:
                            self.national_score[country][i]+=0
                            self.national_score_dict[key][country][i]=0

                        except:
                            self.national_score[country][i] = 0
                            self.national_score_dict[key][country][i]=0

                    # if a country has no shore, wind_offshore always receives a score of 0
                    if country in self.shoreless_countries and i=='wind_offshore':
                        self.national_score[country][i] = 0
                        self.national_score_dict[key][country][i] = 0







    def get_european_score(self):
        #dictionary of national residual loads' sd. TODO: rename to sd_dict
        sd_list = {'hourly': self.standard_deviations_europe, 'daily': self.standard_deviations_europe_daily,
                   'weekly': self.standard_deviations_europe_weekly,
                   'monthly': self.standard_deviations_europe_monthly,
                   'seasonally': self.standard_deviations_europe_seasonally}
        self.european_score={}
        # iterate through dict to get score for all time horizons
        for key in sd_list:
            standard_deviations_df = pd.DataFrame.from_dict(sd_list[key])
            # add time horizon (hourly, daily, weekly...) to dict
            self.european_score_dict[key] = {}

            #sd_max = np.nanmax(standard_deviations_df.to_numpy())
            #sd_min = np.nanmin(standard_deviations_df.to_numpy())

            for country in standard_deviations_df:
                # add country to dict
                self.european_score_dict[key][country] = {}
                if country not in self.european_score.keys():
                    self.european_score[country]={}


                for i in standard_deviations_df[country].index:
                    # get smallest and largest sd throughout all countries and VRE techs
                    sd_max = np.nanmax(standard_deviations_df.loc[i].to_numpy())
                    sd_min = np.nanmin(standard_deviations_df.loc[i].to_numpy())

                    sd=standard_deviations_df[country][i]
                    if sd_max!=sd_min and not math.isnan(sd):
                        # add scores of multiple time horizons. Goes to "except" if self.national_score[country][i] is not defined yet -> first iteration
                        try:
                            self.european_score[country][i]+=self.score_weight[key]*(1-(sd-sd_min)/(sd_max-sd_min))
                            self.european_score_dict[key][country][i]=(1-(sd-sd_min)/(sd_max-sd_min))
                        except:
                            self.european_score[country][i] = self.score_weight[key]*(1 - (sd - sd_min) / (sd_max - sd_min))
                            self.european_score_dict[key][country][i] = (1 - (sd - sd_min) / (sd_max - sd_min))

                    # if sd is nan the or sd_min=sd_max the score is 0. Both should not happen if the time range is larger than a quarter of a year
                    else:
                        print(key)
                        try:
                            self.european_score[country][i]+=0
                            self.european_score_dict[key][country][i]=0
                        except:
                            self.european_score[country][i] = 0
                            self.european_score_dict[key][country][i]=0

                    # if a country has no shore, wind_offshore always receives a score of 0
                    if country in self.shoreless_countries and i=='wind_offshore':
                        self.european_score[country][i] = 0
                        self.european_score_dict[key][country][i] = 0




    def adjust_costs(self, year):
        all_locations = open('build/model/national/locations.yaml')
        all_locations = yaml.load(all_locations, Loader=yaml.FullLoader)


        for country in all_locations['locations'].keys():

            self.incentive_dict[country]={}
            for tech in self.national_score[country].keys():

                # insert updated om_prod costs to backend. wind_onshore is separate, since it consists of wind_onshore_competing and wind_onshore_monopoly
                if tech=='wind_onshore':
                    self.energy_model.backend.update_param('cost_om_prod',
                                                           {('monetary', country + '::' + tech+'_competing'): self.cost_calculator(
                                                               country, tech)})
                    self.energy_model.backend.update_param('cost_om_prod',
                                                        {('monetary', country+'::'+tech+'_monopoly'): self.cost_calculator(country, tech)})
                else:
                    self.energy_model.backend.update_param('cost_om_prod',{('monetary', country + '::' + tech): self.cost_calculator(
                                                               country, tech)})

        pd.DataFrame.from_dict(self.incentive_dict).to_csv(os.path.join(self.output_path,'incentives_step_{}'.format(year)))

    def cost_calculator(self, country, tech):
        # x is composite score of national and european score
        x = (self.european_score[country][tech]+self.national_score[country][tech])

        #linearly: -10 to 10
        x=2*x-10

        #logistic funciton: 0-10
        #x=10/(1+math.exp(-1.65*(x-5)))

        incentive= self.max_incentive[tech]*(5/sum(self.score_weight.values()))*(x/10)
        #incentive= 0.003*(5/sum(self.score_weight.values()))*(x/10)

        #if incentive is nan, return original om_prod -> should not happen
        if math.isnan(x) or math.isnan(self.VRE_om_prod[tech]+x):
            print(tech,country)
            self.incentive_dict[country][tech]= np.nan
            return self.VRE_om_prod[tech]
        #if x is not nan, return om_prod - incentive payment
        else:
            self.incentive_dict[country][tech]=incentive
            return (float(self.VRE_om_prod[tech] - incentive))

    # In current version this function is not used, since YAML file is created in Generate Pre-Built NC folder
#    def create_yaml_plan(self,fossil_share,year,energy_prod_model):
#        print('create_yaml_plan thinks we are in year:', year)
#        example_model = open('build/model/national/example-model-template.yaml')
#        example_model = yaml.load(example_model, Loader=yaml.FullLoader)
#        example_model['group_constraints'] = {}
#        example_model['run']['solver']='gurobi'
#        example_model['run']['solver_io']='python'
#        example_model['run']['solver_options']={'Threads':int(sys.argv[4])}
#        start_date=sys.argv[2]
#        end_date=sys.argv[3]
#        example_model['model']['subset_time']=['{}-'.format(self.ts_year)+start_date,'{}-'.format(self.ts_year)+end_date]
#        for i in fossil_share.index:
#            if year==1:
#                example_model['group_constraints'][i + '_autarky'] = {'demand_share_min': {'electricity': 0.0},
#                                                              'locs': [i]}

            #if i in ['DEU','BEL','ESP','CHE']:

            #    if self.nuclear_scaling_factor<=1 and self.nuclear_scaling_factor>=0:
            #        example_model['group_constraints'][i + '_nuclear'] = {
            #            'demand_share_equals': {'electricity': self.nuclear_scaling_factor*float(energy_prod_model['nuclear'][i])}, 'locs': [i],
            #            'techs': ['nuclear']}
            #    else:
            #        example_model['group_constraints'][i + '_nuclear'] = {
            #            'demand_share_equals': {
            #                'electricity': float(0)},
            #            'locs': [i],
            #            'techs': ['nuclear']}
            #else:
            #    example_model['group_constraints'][i + '_nuclear'] = {
            #        'demand_share_equals': {'electricity': float(energy_prod_model['nuclear'][i])}, 'locs': [i],
            #        'techs': ['nuclear']}

            #example_model['group_constraints'][i + '_fossil'] = {
            #    'demand_share_equals': {'electricity': float(fossil_share[i])}, 'locs': [i], 'techs': ['coal', 'ccgt']}

        #for i in self.renewables_share.index:
        #    example_model['group_constraints'][
        #        self.renewables_share['country'][i] + '_' + self.renewables_share['tech'][i]] = {
        #            'energy_cap_min': float(0),
        #            'locs': [str(self.renewables_share['country'][i])], 'techs': [str(self.renewables_share['tech'][i])]}


        #renewable_techs = open('build/model/renewable-techs.yaml')
        #renewable_techs = yaml.load(renewable_techs, Loader=yaml.FullLoader)
        #for tech in ['wind_offshore', 'wind_onshore', 'open_field_pv', 'roof_mounted_pv']:
    #        try:
    #            self.VRE_om_prod[tech] = renewable_techs['techs'][tech]['costs']['monetary']['om_prod']
#
#            except:
#                self.VRE_om_prod[tech] = renewable_techs['tech_groups'][tech]['costs']['monetary']['om_prod']


#        with open('build/model/national/example-model-plan-year{}.yaml'.format(year),
#                  'w') as outfile:
#            yaml.dump(example_model, outfile)  # , default_flow_style=False)

    def get_LCOE(self):
        technologies=["open_field_pv","wind_onshore_monopoly","wind_offshore","wind_onshore_competing","roof_mounted_pv"]
        LCOE=pd.read_csv(os.path.join(self.output_path, "adjusted_costs/model_csv_year_1/results_systemwide_levelised_cost.csv"))
        LCOE=LCOE.set_index('techs')
        print(LCOE)
        incentive_dict={}
        for tech in technologies:
            try:
                if tech =='wind_onshore_competing' or tech=='wind_onshore_monopoly':#
                    incentive_dict['wind_onshore'] = self.lcoe_percentage * 0.5*(LCOE['systemwide_levelised_cost']['wind_onshore_competing']+LCOE['systemwide_levelised_cost']['wind_onshore_monopoly'])
                else:
                    incentive_dict[tech]=self.lcoe_percentage*LCOE['systemwide_levelised_cost'][tech]
            except:
                incentive_dict[tech]=self.lcoe_percentage*0.003
        print(incentive_dict)
        return incentive_dict


    def energy_autarky(self,year, fossil_share,energy_prod_model):

        if year==2:
            #get LCOE from first modelling step to calculate incentive payments
            self.max_incentive=self.get_LCOE()

        for i in fossil_share.index:
            try:
                # defines level of autarky countries need to have. Must be changed to run levels with other autarky levels
                self.energy_model.backend.update_param('group_demand_share_min',{('electricity','{}_autarky'.format(i)):0.0})
            except:
                print('not in Backend')

            # Adjust nuclear share if for Germany, Belgium, Spain and Switzerland  -  Phaseout 2030 -> after 2nd modelling step. TODO: Maybe discuss if nuclear is supposed to be handeled this way
            if i in ['BEL']:
                if self.nuclear_scaling_factor_2025<=1 and self.nuclear_scaling_factor_2025>=0:
                    self.energy_model.backend.update_param('group_demand_share_equals',{('electricity','{}_nuclear'.format(i)):self.nuclear_scaling_factor_2025*float(energy_prod_model['nuclear'][i])})

                else:
                    self.energy_model.backend.update_param('group_demand_share_equals',{('electricity','{}_nuclear'.format(i)): float(0)})

            elif i in ['DEU']:

                if self.nuclear_scaling_factor_2030<=1 and self.nuclear_scaling_factor_2030>=0:
                    self.energy_model.backend.update_param('group_demand_share_equals',{('electricity','{}_nuclear'.format(i)):self.nuclear_scaling_factor_2030*float(energy_prod_model['nuclear'][i])})
                else:
                    self.energy_model.backend.update_param('group_demand_share_equals',{('electricity','{}_nuclear'.format(i)): float(0)})

            elif i in ['ESP','CHE']:

                if self.nuclear_scaling_factor_2035<=1 and self.nuclear_scaling_factor_2035>=0:
                    self.energy_model.backend.update_param('group_demand_share_equals',{('electricity','{}_nuclear'.format(i)):self.nuclear_scaling_factor_2035*float(energy_prod_model['nuclear'][i])})
                else:
                    self.energy_model.backend.update_param('group_demand_share_equals',{('electricity','{}_nuclear'.format(i)): float(0)})

            else:
                #for all other countries initial nuclear share will be used
                self.energy_model.backend.update_param('group_demand_share_equals',
                                                       {('electricity', '{}_nuclear'.format(i)): float(energy_prod_model['nuclear'][i])})

            #Update fossil fuel share
            self.energy_model.backend.update_param('group_demand_share_equals',
                                                  {('electricity', '{}_fossil'.format(i)): float(fossil_share[i])})

        #use energy capacity of wind and solar PV as minimum for next modelling step
        for i in self.renewables_share.index:
            self.energy_model.backend.update_param('group_energy_cap_min',
                                                   {(self.renewables_share['country'][i] + '_' + self.renewables_share['tech'][i]): float(self.renewables_share['share'][i])})

       #adjust technology costs only if we are not in the baseline run
        if self.baseline_run==False:


            grouped = self.residual_load_country[['locs', 'timesteps', 'residual']].groupby('locs')
            time_range = self.time_steps['timesteps'].to_list()

            #name is the country name, group is the residual load dataframe of this country
            for name, group in grouped:

                self.get_national_sd(name, group, time_range,year)
                self.get_european_sd(name, time_range,year)

            self.get_national_score()
            self.get_european_score()

            #safe standard deviations to csv
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

        # Rerun model if it is not the first modelling step
        if year>1:
            #self.energy_model = calliope.read_netcdf('build/model/model_{}.nc'.format(self.ts_year))
            #self.energy_model.run()
            self.energy_autarky(year, fossil_share, energy_prod_model)
            #self.energy_model.run(force_rerun=True)
            dict_national_score=pd.DataFrame.from_dict(self.national_score_dict)
            dict_national_score.to_csv(os.path.join(self.output_path,'national_score_year_{}'.format(year)))

            dict_european_score=pd.DataFrame.from_dict(self.european_score_dict)
            dict_european_score.to_csv(os.path.join(self.output_path,'european_score_year_{}'.format(year)))

            #rerun model
            model_rerun=self.energy_model.backend.rerun()
            self.model_dict['year {}'.format(year)] = model_rerun

        # if it is the first modeling step and we are in the baseline run (no incentives). Energy system with zero fossil fuel share is modelled in one step
        elif self.baseline_run==True:
            self.energy_model = calliope.read_netcdf('build/model/paper_1h.nc')
            #run model from netcdf to access the backend
            self.energy_model.run(force_rerun=True)

            #adjust backend
            self.energy_autarky(year, fossil_share, energy_prod_model)

            #rerun model with the correct backend
            model_rerun=self.energy_model.backend.rerun()
            self.model_dict['year {}'.format(year)] = model_rerun

        # if we model the incentive model we don't need to do any adjustment to the netcdf model in the first step (since we already insert correct values in the building of the netcdf)
        else:
            print('RUNNING')
            self.energy_model=calliope.read_netcdf('build/model/model_4h_00_autarky_lean_code.nc')
            self.energy_model.run(force_rerun=True)
            self.model_dict['year {}'.format(year)] = self.energy_model
        #self.energy_model.to_netcdf('build/model/model_{}.nc'.format(year))

        #print(self.model_dict)


    def save_model(self,year):
        if self.baseline_run==False:
            self.model_dict['year {}'.format(year)].to_csv(os.path.join(self.output_path,'adjusted_costs/model_csv_year_{}'.format(year)))
        else:
            self.model_dict['year {}'.format(year)].to_csv(os.path.join(self.output_path,'baseline/model_csv_year_{}'.format(year)))


    def __init__(self):
        self.max_incentive={} #max incentive in Cents/kWh

        self.lcoe_percentage=0.3

        self.capacity_factors={}
        self.model_dict={'plan':{}}
        self.ranking={}

        self.national_score_dict={}
        self.european_score_dict={}

        self.standard_deviations_national={}
        self.standard_deviations_national_daily={}
        self.standard_deviations_national_weekly = {}
        self.standard_deviations_national_monthly = {}
        self.standard_deviations_national_seasonally = {}

        self.standard_deviations_europe_daily={}
        self.standard_deviations_europe_weekly={}
        self.standard_deviations_europe_monthly={}
        self.standard_deviations_europe_seasonally={}

        self.sd_baseline_europe={}
        self.sd_baseline_national={}

        self.national_score={}
        self.national_score_daily={}
        self.national_score_weekly = {}
        self.national_score_monthly = {}
        self.national_score_seasonally = {}

        self.score_weight = {'hourly': 1, 'daily': 1,
                   'weekly': 1,
                   'monthly': 1,
                   'seasonally': 1}


        self.shoreless_countries=[]

        self.standard_deviations_europe = {}
        self.VRE_om_prod = {}
        self.national_score={}
        self.european_score={}
        self.baseline_run=False
        self.euro_calliope_specifications=euro_calliope_specifications()
        self.output_path=""
        self.ts_year=2016


        self.nuclear_scaling_factor_2025 = 0
        self.nuclear_scaling_factor_2030 = 0
        self.nuclear_scaling_factor_2035 = 0

        self.incentive_dict={}
        #self.renewables_share=self.get_wind_pv_shares(config, year)
