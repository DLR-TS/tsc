import os
import tscdefs
from tapas_sumo_coupling import database
import subprocess

database.run_instructions(tscdefs.testServer, [open("data/initialState.sql")])
os.chdir("data/scenario_workdir/mitte_net")
subprocess.call(tscdefs.get_python_tool("get_trips.py") + ['--simkey', '2014y_01m_19d_15h_55m_15s_386ms'])