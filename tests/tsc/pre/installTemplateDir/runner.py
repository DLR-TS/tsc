import os
import sys

python = os.environ.get("PYTHON", "python")
sys.path.append(os.path.join(os.environ["SUMO_HOME"], 'tools'))
tscRoot = os.environ.get("TSC_HOME", os.path.join(os.environ["SIP_HOME"]))
sys.path.append(tscRoot)
tscData = os.environ.get("TSC_DATA", os.path.join(os.environ["SIP_HOME"]))

buildProcess = []
runProcess = ["<data>",
              '"' + python + '" "' + os.path.join(tscRoot, "install_osm_scenario_templates.py") + '"'
               ' --clean -v -p ' + os.path.join(tscData, "data")
              ]
toRemove = []
toDeploy = ['data']