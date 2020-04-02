import os
import subprocess
import tscdefs

os.chdir("data")
subprocess.call(tscdefs.get_python_tool("tsc_main.py", None) + ['--fake-tripfile', 'twoPersonsOnly.csv', '--limit', '2', '--iteration', '0:3', '--sim-param', 'DB_TABLE_ADDITIONAL_TRAFFIC:""'])