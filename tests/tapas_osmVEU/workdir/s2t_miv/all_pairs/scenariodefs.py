import tscdefs

buildProcess = []
runProcess = [
    "<data>",
    tscdefs.get_python_tool("s2t_miv.py") + ' --real-trips vehroutes_oneshot_meso.rou.xml --representatives miv_all_pairs_passenger24.trips.rou.alt.xml -n scenario_workdir/mitte_net/net.net.xml'
]
toRemove = []
toDeploy = []
