import os
import subprocess
import tscdefs

os.chdir("data")
subprocess.call(tscdefs.get_python_tool("tsc_main.py", None) + ['--fake-tripfile', 'twoPersonsOnly.csv', '--limit', '2', '--iteration', '0', '--sim-param', 'DB_TABLE_ADDITIONAL_TRAFFIC:""', '--sim-param', 'SUMO_TEMPLATE_FOLDER:mitte_net,SUMO_DESTINATION_FOLDER:mitte_net,DB_TABLE_ADDITIONAL_TRAFFIC:"",MAX_SUMO_ITERATION:4', '--net-param', '{"RBS_OD_ORT_1412.taz.xml@0101":{"allowed":["passenger"]}}'])
