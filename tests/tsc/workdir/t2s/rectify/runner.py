import os
import stddefs

tscRoot = os.environ.get("TSC_HOME", os.path.join(os.environ["SIP_HOME"]))
tripFile = '2013y_11m_08d_14h_44m_44s_356ms_limit100000_negative_departures.csv'
net = 'scenario_workdir/mitte_net/net.net.xml'

iteration_dir = 'scenario_workdir/mitte_net/iteration000'

buildProcess = []
runProcess   = ["<data>",
                os.path.join(tscRoot, "t2s.py")
                + " --net-file " + net
                + " --iteration-dir " + iteration_dir
                + " --tapas-trips " + tripFile
                + " --rectify-only"
               ]
toRemove = []

toDeploy = ['data/scenario_workdir']
