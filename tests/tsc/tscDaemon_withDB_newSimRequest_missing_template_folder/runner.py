import os
import tscdefs
from tapas_sumo_coupling import database

updateCmd = "UPDATE simulation_parameters SET param_value='nonExistentDir' WHERE sim_key='1969y_07m_21d_03h_56m_12s_345ms' AND param_key='SUMO_TEMPLATE_FOLDER';"
               
os.chdir("data")
database.start(tscdefs.testServer, tscdefs.get_python_tool("tsc_main.py") + ['--daemon', '--daemon-run-time', '10'], [open("initialState.sql"), [updateCmd]], [], [])