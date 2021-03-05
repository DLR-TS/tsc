"""
@file    __init__.py
@author  Michael.Behrisch@dlr.de
@date    2015-06-10
@version $Id: analysis.py 2493 2013-04-02 10:32:37Z behr_mi $

custom script collection for move_urban

Copyright (C) 2015-2017 DLR/TS, Germany
All rights reserved
"""
import os

import assign

def assign_trips(options, first_depart, last_depart, routes, weights):
    routes, weights = assign.run_oneshot(options, first_depart, last_depart, routes, weights)
    return assign.run_subnet(options, first_depart, last_depart, routes, weights, os.path.join(os.path.dirname(__file__), 'spandau.net.xml'))
