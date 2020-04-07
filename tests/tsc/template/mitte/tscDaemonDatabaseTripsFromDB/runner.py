import os
import tscdefs
import db_manipulator

updateCmd = """UPDATE simulation_parameters SET param_value='mitte_net'
               WHERE param_key='SUMO_DESTINATION_FOLDER' OR param_key='SUMO_TEMPLATE_FOLDER';"""
               
os.chdir("data")
db_manipulator.start(tscdefs.testServer, tscdefs.get_python_tool("tsc_main.py") + ['-l', '2', '--limit', '50000'], [open("initialState.sql"), [updateCmd]], [], [])