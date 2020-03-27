import tscdefs

buildProcess = []
runProcess   = ["<data/>",
                tscdefs.get_python_tool("tsc_main.py", None)
                + ' --fake-tripfile twoPersonsOnly.csv -l 2 --iteration 0:3 --sim-param DB_TABLE_ADDITIONAL_TRAFFIC:"",DELETE_INTERMEDIATE_RESULTS:true'
               ]
toRemove = []
toDeploy = []
