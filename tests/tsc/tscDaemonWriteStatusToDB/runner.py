import os
import tscdefs
from tapas_sumo_coupling import database

os.chdir("data")
database.start(tscdefs.testServer, tscdefs.get_python_tool("tsc_main.py") + ['--daemon', '--daemon-run-time', '10'],
                     [open("initialState.sql")], [], [["SELECT sim_key, iteration, status, msg_type FROM public.global_sumo_status ORDER BY status_time;"]])
