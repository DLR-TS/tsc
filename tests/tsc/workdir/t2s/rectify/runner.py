import os
import subprocess
import tscdefs

tripFile = '2013y_11m_08d_14h_44m_44s_356ms_limit100000_negative_departures.csv'
net = 'scenario_workdir/mitte_net/net.net.xml.gz'
iteration_dir = 'scenario_workdir/mitte_net/iteration000'

os.chdir("data")
subprocess.call(tscdefs.get_python_tool("t2s.py",None) + ['--net-file', net, '--iteration-dir', iteration_dir, '--tapas-trips', tripFile, '--rectify-only'])