import tscdefs
import db_manipulator

buildProcess = []
runProcess   = ["<data>",
                lambda: db_manipulator.start(tscdefs.testServer,
                tscdefs.get_python_tool("tsc_main.py")
                + ' --daemon '
                + ' --daemon-run-time 10',
                [open("initialState.sql"), ["DELETE FROM simulation_parameters;"]], [], [])
               ]
toRemove = []
toDeploy = []
