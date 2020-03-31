import tscdefs
import db_manipulator

buildProcess = []
runProcess = [
    lambda: db_manipulator.run_instructions(tscdefs.testServer, [open("data/initialState.sql")]),
    "<data/scenario_workdir/mitte_net>",
    tscdefs.get_python_tool("get_trips.py") + ' -a -l 90'
]
toRemove = []

toDeploy = [
]
