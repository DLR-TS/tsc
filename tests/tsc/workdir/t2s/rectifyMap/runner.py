import os
import subprocess
import tscdefs

tripFile = '2013y_03m_07d_16h_43m_41s_859ms_limit1000.csv'
net = 'scenario_workdir/mitte_net/net.net.xml'
iteration_dir = 'scenario_workdir/mitte_net/iteration000'

os.chdir("data")
subprocess.call(tscdefs.get_python_tool("t2s.py",None) + ['--net-file', net, '--iteration-dir', iteration_dir, '--tapas-trips', tripFile, '--map-and-exit'])