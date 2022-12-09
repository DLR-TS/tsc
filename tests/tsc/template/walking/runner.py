import os
import datetime
import tscdefs
import db_manipulator

updateCmd = "INSERT INTO public.global_sumo_status VALUES('2015y_01m_19d_15h_55m_15s_386ms', 0, '%s', 'disabled', 'error');" % datetime.datetime.now().isoformat()

os.chdir("data")
params = ['--fake-tripfile', 'twoPersonsOnly_walking.csv', '--modes', '0', '-l', '2', '--limit', '50000',
          '--sim-param', 'SUMO_TEMPLATE_FOLDER:mitte_net,SUMO_DESTINATION_FOLDER:mitte_net,DB_TABLE_ADDITIONAL_TRAFFIC:']
db_manipulator.start(tscdefs.testServer,
                     tscdefs.get_python_tool("tsc_main.py") + params,
                     [open("initialState.sql"), [updateCmd]], [], [])
