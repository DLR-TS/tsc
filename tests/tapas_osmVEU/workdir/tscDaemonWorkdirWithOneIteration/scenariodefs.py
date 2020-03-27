import tscdefs

buildProcess = []
runProcess   = ["<data/>",
                tscdefs.get_python_tool("tsc_main.py", None)
                + ' --fake-tripfile 2013y_03m_07d_16h_43m_41s_859ms_limit1000.csv -l 2 --iteration 1'
               ]
toRemove = []
toDeploy = []
