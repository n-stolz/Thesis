import os.path
import logging
from initialization import configuration
from initialization import model_specifications

from model_pipeline import pipeline
import shutil
from random import seed
from random import choice
import pandas as pd
import sys
import datetime
import time





def run_models():
    year_sequence = {'adjusted_costs:': {}, 'baseline': {}}
    #seed(123)
    today = datetime.datetime.now()
    date_time = today.strftime("%m-%d-%Y, %H:%M")

    # TODO agree on (shared?) repository for
    if os.path.isdir('/home/niklas/European Incentive Model'):
        #output_path = ('/home/niklas/Operation_Mode/output_{}'.format(date_time))
        scenario_path=('/home/niklas/Operation_Mode/test_scenario')
    else:
        #output_path = ('/cluster/scratch/nstolz/six_scenarios_sd_discrete/output_25per_incentive_00_autarky')
        scenario_path=('/cluster/work/cpesm/shared/incentive-scheming/Data/'+sys.argv[3]+'_{}'.format(int(sys.argv[1])))

    scenario_list=os.listdir(scenario_path)
    print(scenario_list)


    model = pipeline()
    for baseline in [False,True]:




        model.baseline_run=baseline
        model.model_path=os.path.join(scenario_path)
        model.output_path = os.path.join(model.model_path,'Planning_mode_all_years')

        if not os.path.isdir(model.output_path):
            os.mkdir(model.output_path)
        if baseline==True:
            os.mkdir(os.path.join(model.output_path,'baseline'))
        else:
            os.mkdir(os.path.join(model.output_path,'adjusted_costs'))



        if baseline == True:
            specs.years = 1
        else:
            specs.years=years

        year_list=[2010,2011,2012,2013,2014,2015,2016,2017,2018]
        #year_list.remove(int(sys.argv[5])-1)
        year_list.remove(int(sys.argv[1]))
        #year_list.remove((int(sys.argv[5])+1))
        for year in year_list:

            print('run_models thinks we are in year:',year)
            if baseline==False:
                path=os.path.join(model.output_path,'adjusted_costs/model_csv_year_{}'.format(year))
            else:
                path=os.path.join(model.output_path,'baseline/model_csv_year_{}'.format(year))

            #if os.path.exists(path):
            if False:
                print('was already computed')
            else:

                if baseline==True:
                    model.ts_year=year
                    year_sequence['baseline']['step {}'.format(year)]=model.ts_year
                else:
                    #demand_year=get_random_year()
                    model.ts_year=year
                    year_sequence['adjusted_costs:']['step {}'.format(year)] = model.ts_year

                logging.info('running model run no: %s; demand and cf timeseries of year %s', year,model.ts_year)



                #create the operation YAML file
                model.create_yaml_operate(year, config.energy_prod_model)



                model.run_planning_model(year)

                model.save_model(year)
    pd.DataFrame.from_dict(year_sequence).to_csv(
        os.path.join(model.output_path, 'demand_year_sequence.csv'))



# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    config=configuration()
    specs=model_specifications()
    years=int(sys.argv[1])




    run_models()


# See PyCharm help at https://www.jetbrains.com/help/pycharm/
