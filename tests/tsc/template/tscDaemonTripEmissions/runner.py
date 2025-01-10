import os
import datetime
import tscdefs
from tapas_sumo_coupling import database

updateCmd = "INSERT INTO public.global_sumo_status VALUES('2015y_01m_19d_15h_55m_15s_386ms', 0, '%s', 'disabled', 'error');" % datetime.datetime.now().isoformat()

os.chdir("data")
database.start(tscdefs.testServer,
                     tscdefs.get_python_tool("tsc_main.py") + ['--fake-tripfile', 'twoPersonsOnly.csv', '-l', '2', '--limit', '50000', '--trip-emissions', 'tripinfos.xml',
                                                               '--sim-param', 'SUMO_TEMPLATE_FOLDER:mitte_net,SUMO_DESTINATION_FOLDER:mitte_net,DB_TABLE_ADDITIONAL_TRAFFIC:'],
                     [open("initialState.sql"), [updateCmd]], [], [])
