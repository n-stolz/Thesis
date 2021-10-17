import pandas as pd
import yaml


class configuration:
    def get_energy_production(self):
        ## Returns average fossil fuel & nuclear share 2015-2020. Initial Condition for net zero szenarios
        energy_prod = pd.read_csv('Data/electricity-production-by-source.csv')
        locations = open('build/model/national/locations.yaml')
        locations = yaml.load(locations, Loader=yaml.FullLoader)
        country_ids = []
        for item, doc in locations['locations'].items():
            country_ids.append(item)
        energy_prod = energy_prod[energy_prod['Code'].isin(country_ids)]
        energy_prod = energy_prod[energy_prod['Year'] >= 2015]
        energy_prod = energy_prod.groupby(['Code']).sum()
        energy_prod = energy_prod.drop(['Year'], axis=1)
        energy_prod['total'] = energy_prod.sum(axis=1)
        techs = ['coal', 'gas', 'nuclear', 'hydro', 'other renewables', 'solar', 'oil', 'wind']

        for tech in techs:
            energy_prod[tech] = energy_prod['Electricity from {} (TWh)'.format(tech)] / energy_prod['total']
        energy_prod_model = energy_prod[['coal', 'gas', 'nuclear', 'total']].copy()
        energy_prod_model = energy_prod_model.rename(columns={'nuclear': 'nuclear', 'gas': 'ccgt'}, inplace=False)
        return energy_prod_model

    def get_wind_pv_tech(self):
        #returns all wind and pv technology names
        renewable_techs = open('build/model/renewable-techs.yaml')
        renewable_techs = yaml.load(renewable_techs, Loader=yaml.FullLoader)
        generation_techs = []

        for key in renewable_techs['techs']:
            generation_techs.append(key)

        # wind_pv_tech=[tech for tech in generation_techs if ('pv' in generation_techs or 'wind' in generation_techs)]
        pv_tech = list(filter(lambda k: 'pv' in k, generation_techs))
        wind_tech = list(filter(lambda k: 'wind' in k, generation_techs))

        wind_pv_tech = pv_tech + wind_tech
        return wind_pv_tech

    def get_wind_pv_loc_techs(self):
        locations = open('build/model/national/locations.yaml')
        locations = yaml.load(locations, Loader=yaml.FullLoader)
        wind_pv_loc_techs = []
        for country in locations['locations']:
            for tech in locations['locations'][country]['techs']:
                if tech in self.wind_pv_tech:
                    wind_pv_loc_techs.append(country + "::" + tech)
        return wind_pv_loc_techs



    def __init__(self):
        self.energy_prod_model=self.get_energy_production()
        self.wind_pv_tech=self.get_wind_pv_tech()
        self.wind_pv_loc_techs=self.get_wind_pv_loc_techs()
        self.supply_techs = ['open_field_pv', 'roof_mounted_pv', 'wind_onshore_monopoly', 'wind_onshore_competing',
                             'wind_offshore', 'load_shedding', 'hydro_run_of_river', 'coal', 'ccgt', 'nuclear']
        self.supply_plus_techs = ['biofuel', 'hydro_reservoir']
        self.storage_techs = ['battery', 'pumped_hydro', 'hydrogen']

class model_specifications:
    def __init__(self):
        self.years=6