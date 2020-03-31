import os
import tscdefs

buildProcess = []
runProcess = ["<data>",
              tscdefs.get_python_tool("install_osm_scenario_templates.py")
               + ' --clean -v -p ' + os.path.join(tscdefs.tscData, "osm_scenario_pre")
              ]
toRemove = []
toDeploy = ['data']
