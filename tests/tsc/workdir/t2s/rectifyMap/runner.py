import os
import stddefs

tscRoot = os.environ.get("TSC_HOME", os.path.join(os.environ["SIP_HOME"]))
tripFile = '2013y_03m_07d_16h_43m_41s_859ms_limit1000.csv'
net = 'scenario_workdir/mitte_net/net.net.xml'

iteration_dir = 'scenario_workdir/mitte_net/iteration000'

buildProcess = []
runProcess   = ["<data>",
                os.path.join(tscRoot, "t2s.py")
                + " --net-file " + net
                + " --iteration-dir " + iteration_dir
                + " --tapas-trips " + tripFile
                + " --map-and-exit "
               ]
toRemove = []

toDeploy = ['data/scenario_workdir']
