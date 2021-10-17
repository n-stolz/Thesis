import pandas as pd
import numpy as np
import yaml
from initialization import configuration

class euro_calliope_specifications:
    def get_capacity_factors(self):
        cf_open_pv = pd.read_csv('build/model/national/capacityfactors-open-field-pv.csv')
        cf_roof_pv = pd.read_csv('build/model/national/capacityfactors-rooftop-pv.csv')
        cf_offshore_wind = pd.read_csv(
            'build/model/national/capacityfactors-wind-offshore.csv')
        cf_onshore_wind = pd.read_csv(
            'build/model/national/capacityfactors-wind-onshore.csv')
        capacity_factors = {'open_field_pv': cf_open_pv, 'roof_mounted_pv': cf_roof_pv,
                            'wind_offshore': cf_offshore_wind, 'wind_onshore': cf_onshore_wind}
        return capacity_factors

    def get_loc_techs(self):
        loc_techs = []
        for country in self.locations['locations']:
            for tech in self.locations['locations'][country]['techs']:
                loc_techs.append(country + "::" + tech)
        loc_techs = [x for x in loc_techs if "demand_elec" not in x]
        loc_techs_df = pd.DataFrame(loc_techs, columns=['loc_tech'])
        loc_techs_df['category'] = np.nan
        config=configuration()
        for i in loc_techs_df['loc_tech'].index:

            if loc_techs_df['loc_tech'][i][5:] in config.supply_techs:
                loc_techs_df['category'][i] = 'supply'
            elif loc_techs_df['loc_tech'][i][5:] in config.supply_plus_techs:
                loc_techs_df['category'][i] = 'supply_plus'
            elif loc_techs_df['loc_tech'][i][5:] in config.storage_techs:
                loc_techs_df['category'][i] = 'storage'
            # print(loc_techs_df)
        return loc_techs, loc_techs_df

    def get_locations(self):
        locations = open('build/model/national/locations.yaml')
        locations = yaml.load(locations, Loader=yaml.FullLoader)
        return locations

    def __init__(self):
        self.locations=self.get_locations()
        self.capacity_factors=self.get_capacity_factors()
        self.loc_techs, self.loc_techs_df=self.get_loc_techs()
        fossil_share=pd.DataFrame()