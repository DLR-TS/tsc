import os
import tscdefs
import database

updateCmd = """DELETE FROM simulation_parameters;"""

os.chdir("data")
database.start(tscdefs.testServer, tscdefs.get_python_tool("tsc_main.py") + ['--daemon', '--daemon-run-time', '10'], [open("initialState.sql"), [updateCmd]], [], [])