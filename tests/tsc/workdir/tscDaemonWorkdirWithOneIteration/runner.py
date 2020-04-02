import os
import subprocess
import tscdefs

os.chdir("data")
subprocess.call(tscdefs.get_python_tool("tsc_main.py", None) + ['--fake-tripfile', '2013y_03m_07d_16h_43m_41s_859ms_limit1000.csv', '--limit', '2', '--iteration', '1'])