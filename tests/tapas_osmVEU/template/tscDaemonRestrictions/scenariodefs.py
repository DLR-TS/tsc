import tscdefs

buildProcess = []
runProcess   = ["<data/>",
                tscdefs.get_python_tool("tsc_main.py", None)
                + ' --fake-tripfile twoPersonsOnly.csv -l 2 --sim-param DB_TABLE_ADDITIONAL_TRAFFIC:""'
                + ' --iteration 0 --sim-param MAX_SUMO_ITERATION:4'
                + ' --net-param {\\"RBS_OD_ORT_1412.taz.xml@0101\\":{\\"allowed\\":[\\"passenger\\"]}}'
               ]
toRemove = []
toDeploy = []
