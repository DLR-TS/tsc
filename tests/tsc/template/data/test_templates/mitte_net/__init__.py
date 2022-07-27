"""
@file    __init__.py
@author  Michael.Behrisch@dlr.de
@date    2015-06-10
@version $Id: __init__.py 4620 2015-06-27 14:06:36Z behr_mi $

custom script collection for berlin_2010

Copyright (C) 2015-2015 DLR/TS, Germany
All rights reserved
"""
import subprocess
import assign
import postprocess
from sumolib.miscutils import benchmark

assign_trips = assign.run_default

@benchmark
def post(options, params, conn, routefile):
    procs = [postprocess.run_pedestrian_sumo(options, routefile),
             postprocess.run_emission_sumo(options, params, conn, routefile)]
    err = None
    for p in procs:
        if p is not None:
            retcode = p[1].wait()
            if retcode:
                err = subprocess.CalledProcessError(retcode, p[0])
    if err:
        raise err
