import os
import subprocess
import tscdefs

tripFile = 'twoPersonsOnly_sharing.csv'
net = os.path.join('scenario_workdir','mitte_net', 'net.net.xml')
iteration_dir = os.path.join('scenario_workdir','mitte_net', 'iteration000')

os.chdir("data")
subprocess.call(tscdefs.get_python_tool("t2s.py",None) + ['--net-file', net, '--modes', '6', '--iteration-dir', iteration_dir, '--tapas-trips', tripFile])