import os.path
import logging
from initialization import configuration
from initialization import model_specifications
#from global_variables import global_variables
from euro_calliope_specifications import euro_calliope_specifications
from model_pipeline import pipeline
import shutil
from random import seed
from random import choice
import pandas as pd
import sys
import datetime

def get_random_year():
    years = [2016]
    selection = choice(years)
    years.remove(selection)
    #ONLY FOR DEBUGGING!
    #selection=2016
    return selection

def copy_year_to_model(demand_year):
    print('Demand and CF time series from: ', demand_year)

    for file_name in ['capacityfactors-hydro-reservoir-inflow.csv','capacityfactors-hydro-ror.csv','capacityfactors-open-field-pv.csv',
                      'capacityfactors-rooftop-pv.csv','capacityfactors-wind-offshore.csv','capacityfactors-wind-onshore.csv',
                      'electricity-demand.csv']:
        original = os.path.join("build/model/model_{}/national".format(str(demand_year)),file_name)
        target = os.path.join("build/model/national",file_name)

        shutil.copyfile(original, target)
    demand_ts_2016=pd.read_csv('build/model/model_2016/national/electricity-demand.csv')
    demand_ts=pd.read_csv('build/model/national/electricity-demand.csv')
    for (columnName, columnData) in demand_ts.iteritems():
        if columnName != "utc_timestamp":
            print(columnName)
            demand_ts[columnName] = demand_ts[columnName] * (
                        demand_ts_2016[columnName].mean() / demand_ts[columnName].mean())
            demand_ts.to_csv('build/model/national/electricity-demand.csv',index=False)


def run_models():
    year_sequence = {'adjusted_costs:': {}, 'baseline': {}}
    #seed(123)
    today = datetime.datetime.now()
    date_time = today.strftime("%m-%d-%Y, %H:%M")
    if os.path.isdir('/home/niklas/European Incentive Model'):
        output_path = ('/home/niklas/European Incentive Model/output_{}'.format(date_time))
    else:
        output_path = ('/cluster/scratch/nstolz/paper_1h_30per')

    model = pipeline()
    for baseline in [False, True]:



        model.output_path=output_path
        model.baseline_run=baseline
        if baseline == True:
            specs.years = 1
        else:
            specs.years=years
        for year in range(1,specs.years+1):
                print('run_models thinks we are in year:',year)
                if baseline==True:
                    model.ts_year=2016
                    year_sequence['baseline']['step {}'.format(year)]=model.ts_year
                else:
                    #demand_year=get_random_year()
                    model.ts_year=2016
                    year_sequence['adjusted_costs:']['step {}'.format(year)] = model.ts_year
                #copy_year_to_model(model.ts_year)
                logging.info('running model run no: %s; demand and cf timeseries of year %s', year,model.ts_year)
                print(year)
                euro_calliope_specifications.fossil_share=config.energy_prod_model[['coal','ccgt']].sum(axis=1)-year*(1/specs.years)*config.energy_prod_model[['coal','ccgt']].sum(axis=1)
                model.nuclear_scaling_factor = 1-3*year*(1/specs.years)


                model.renewables_share = model.get_wind_pv_shares(config, year)
                if year>1:

                    #get residual loads on national and european level
                    model.time_steps=model.get_production_timeseries(year)

                if year==1:
                    model.create_yaml_plan(euro_calliope_specifications.fossil_share, year, config.energy_prod_model)



                model.run_planning_model(year,euro_calliope_specifications.fossil_share,config.energy_prod_model)

                model.save_model(year)
    pd.DataFrame.from_dict(year_sequence).to_csv(
        os.path.join(model.output_path, 'demand_year_sequence.csv'))



# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    config=configuration()
    specs=model_specifications()
    years=int(sys.argv[1])


    euro_calliope_specs=euro_calliope_specifications()

    run_models()


# See PyCharm help at https://www.jetbrains.com/help/pycharm/
