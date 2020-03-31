import tscdefs
import db_manipulator

buildProcess = []
updateCmd = ["UPDATE public.simulation_parameters SET sim_key='2015y_01m_19d_15h_55m_15s_386ms';",
             "UPDATE public.simulation_parameters SET param_value='berlin_trips' WHERE param_key='DB_TABLE_TRIPS';",
             "UPDATE public.simulation_parameters SET param_value='1' WHERE param_key='SUMO_MAX_ITERATION';",
             "UPDATE core.global_sumo_status SET sim_key='2015y_01m_19d_15h_55m_15s_386ms';"]
runProcess   = ["<data>",
                lambda: db_manipulator.start(tscdefs.testServer,
                tscdefs.get_python_tool("tsc_main.py")
                + ' --limit 5000',
                [open("initialState.sql"), updateCmd], [], [])
               ]
toRemove = []
toDeploy = []
