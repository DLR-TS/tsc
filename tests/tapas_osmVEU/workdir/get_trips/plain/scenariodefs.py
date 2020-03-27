import tscdefs
import db_manipulator

buildProcess = []
runProcess = [
    lambda: db_manipulator.run_instructions(tscdefs.testServer, [open("data/initialState.sql")]),
    "<data/scenario_workdir/mitte_net>",
    tscdefs.get_python_tool("get_trips.py") + ' --simkey 2015y_05m_29d_09h_01m_11s_943ms --triptable test_trips'
]
toRemove = []

toDeploy = [
]
