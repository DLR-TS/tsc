"""
@file    __init__.py
@author  Michael.Behrisch@dlr.de
@date    2015-06-10
@version $Id: analysis.py 2493 2013-04-02 10:32:37Z behr_mi $

custom script collection for mitte_2010

Copyright (C) 2015-2017 DLR/TS, Germany
All rights reserved
"""
import os

import assign
import postprocess
from sumolib.miscutils import benchmark

def assign_trips(options, first_depart, last_depart, routes, weights):
    routes, weights = assign.run_oneshot(options, first_depart, last_depart, routes, weights)
    return assign.run_subnet(options, first_depart, last_depart, routes, weights, os.path.join(os.path.dirname(__file__), 'mitte.net.xml'))

@benchmark
def post(options, params, conn, routefile):
    postprocess.run_trajectory_sumo(options, os.path.join(os.path.dirname(options.net_file), 'mitte.net.xml'), routefile)
