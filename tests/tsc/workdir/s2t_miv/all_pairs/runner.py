import os
import subprocess
import tscdefs

os.chdir("data")
subprocess.call(tscdefs.get_python_tool("s2t_miv.py") + ['--real-trips', 'vehroutes_oneshot_meso.rou.xml', '--representatives', 'miv_all_pairs_passenger24.trips.rou.xml.gz', '-n', 'scenario_workdir/mitte_net/net.net.xml'])
