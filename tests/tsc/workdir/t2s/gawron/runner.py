import os
import stddefs

tscRoot = os.environ.get("TSC_HOME", os.path.join(os.environ["SIP_HOME"]))
tripFile = 'twoPersonsOnly.csv'
net = os.path.join('scenario_workdir','mitte_net', 'net.net.xml')

iteration_dir = os.path.join('scenario_workdir','mitte_net', 'iteration000')

buildProcess = []
runProcess   = ["<data>",
                os.path.join(tscRoot, "t2s.py")
                + " --net-file " + net
                + " --iteration-dir " + iteration_dir
                + " --tapas-trips " + tripFile
                + " --assignment gawron -l 2 "
               ]
toRemove = []

toDeploy = ['data/scenario_workdir']
