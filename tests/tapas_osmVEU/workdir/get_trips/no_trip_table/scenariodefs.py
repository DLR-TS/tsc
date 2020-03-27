import tscdefs
import db_manipulator

buildProcess = []
runProcess = [
    lambda: db_manipulator.run_instructions(tscdefs.testServer, [open("data/initialState.sql")]),
    "<data/scenario_workdir/mitte_net>",
    tscdefs.get_python_tool("get_trips.py") + ' --simkey 2014y_01m_19d_15h_55m_15s_386ms'
]
toRemove = []

toDeploy = [
]
