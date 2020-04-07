import os
import tscdefs
import subprocess
import db_manipulator

updateCmd = """UPDATE simulation_parameters SET param_value='mitte_net' 
               WHERE param_key='SUMO_DESTINATION_FOLDER' OR param_key='SUMO_TEMPLATE_FOLDER';"""

pre_path = os.path.join(tscdefs.tscData, "data")
templates_path = os.path.join("data", "data_templates")

subprocess.call(tscdefs.get_python_tool("install_osm_scenario_templates.py") + ['-s', 'mitte_net', '-p', pre_path, '-t', templates_path])

os.chdir("data")
db_manipulator.start(tscdefs.testServer, tscdefs.get_python_tool("tsc_main.py") + ['--fake-tripfile', 'twoPersonsOnly.csv', '-l', '2', '--limit', '5000'], [open('initialState.sql'), [updateCmd]], [], [])