import os
import tscdefs
import db_manipulator

os.chdir("data")
db_manipulator.start(tscdefs.testServer, tscdefs.get_python_tool("tsc_main.py") + ['--daemon', '--daemon-run-time', '10'], [open("initialState.sql")], [], [["SELECT sim_key, iteration, status, msg_type FROM core.global_sumo_status ORDER BY status_time;"]])