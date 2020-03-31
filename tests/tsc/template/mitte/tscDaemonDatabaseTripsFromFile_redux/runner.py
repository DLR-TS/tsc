import os
import tscdefs
import db_manipulator

buildProcess = [os.path.join(tscdefs.tscRoot, "install_osm_scenario_templates.py")
                + " -s mitte_redux -p " + os.path.join(tscdefs.tscData, "osm_scenario_pre")
                + " -t " + os.path.join("data", "osm_scenario_templates")
               ]

updateCmd = """UPDATE simulation_parameters SET param_value='mitte_redux'
               WHERE param_key='SUMO_DESTINATION_FOLDER' OR param_key='SUMO_TEMPLATE_FOLDER';"""

runProcess   = ["<data>",
                lambda: db_manipulator.start(tscdefs.testServer,
                tscdefs.get_python_tool("tsc_main.py")
                + ' --fake-tripfile twoPersonsOnly.csv -l 2 --limit 5000',
                [open("initialState.sql"), [updateCmd]], [], [])
               ]
toRemove = []
toDeploy = []
