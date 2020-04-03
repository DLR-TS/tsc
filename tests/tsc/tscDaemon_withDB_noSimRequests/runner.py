import os
import tscdefs
import db_manipulator

updateCmd = """DELETE FROM simulation_parameters;"""

os.chdir("data")
db_manipulator.start(tscdefs.testServer, tscdefs.get_python_tool("tsc_main.py") + ['--daemon', '--daemon-run-time', '10'], [open("initialState.sql"), [updateCmd]], [], [])