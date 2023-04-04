import os
import tscdefs
from tapas_sumo_coupling import database
import subprocess

database.run_instructions(tscdefs.testServer, [open("data/initialState.sql")])
os.chdir("data/scenario_workdir/mitte_net")
subprocess.call(tscdefs.get_python_tool("get_trips.py") + ['--simkey', '2015y_05m_29d_09h_01m_11s_943ms', '--triptable', 'test_trips'])