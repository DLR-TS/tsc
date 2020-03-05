# Copyright (C) 2013-2020 German Aerospace Center (DLR) and others.
# This program and the accompanying materials are made available under the
# terms of the Eclipse Public License 2.0 which is available at
# https://www.eclipse.org/legal/epl-2.0/
# This Source Code may also be made available under the following Secondary
# Licenses when the conditions for such availability set forth in the Eclipse
# Public License 2.0 are satisfied: GNU General Public License, version 2
# or later which is available at
# https://www.gnu.org/licenses/old-licenses/gpl-2.0-standalone.html
# SPDX-License-Identifier: EPL-2.0 OR GPL-2.0-or-later

# @file    emissions.py
# @author  Jakob.Erdmann@dlr.de
# @author  Michael.Behrisch@dlr.de
# @date    2013-12-15

# functions needed for emission calculation

from __future__ import print_function, division
import os
import sys
import math
import csv
import subprocess
import time
from collections import defaultdict

import sumolib
from sumolib.miscutils import benchmark, uMax

from common import csv_sequence_generator, abspath_in_dir, build_uid
from constants import TH, THX, SX, TAPAS_EXTRA_TIME, SP
from get_trips import table_exists

SMALL_CARS = set([1, 2, 101])
MEDIUM_CARS = set([3, 4, 9, 10, 102])
LARGE_CARS = set([5, 6, 7, 8, 95, 103])
TRANSPORTER = set([11, 12, 104])

FUEL_TYPES = ["G", "D", "O", "O", "O"]

def get_emission_class(model, size, fuel, euro_norm):
    assert size in SMALL_CARS or size in MEDIUM_CARS or size in LARGE_CARS or size in TRANSPORTER, "Unknown size class"
    assert fuel < 2, "Unknown fuel type"
    assert euro_norm in range(0, 7), "Unknown Euro norm"
    if model == "HBEFA2 7":
        if size in TRANSPORTER:
            if FUEL_TYPES[fuel] == "G":
                return "HBEFA2/P_7_3"
            if FUEL_TYPES[fuel] == "D":
                return "HBEFA2/P_7_5"
        return "HBEFA2/P_7_7"
    elif model == "HBEFA2 14":
        if size in SMALL_CARS:
            if FUEL_TYPES[fuel] == "G":
                if euro_norm < 2:
                    return "HBEFA2/P_14_14"
                return "HBEFA2/P_14_9"
            if FUEL_TYPES[fuel] == "D":
                if euro_norm < 2:
                    return "HBEFA2/P_14_7"
                return "HBEFA2/P_14_8"
        if size in MEDIUM_CARS:
            if FUEL_TYPES[fuel] == "G":
                if euro_norm < 2:
                    return "HBEFA2/P_14_14"
                return "HBEFA2/P_14_9"
            if FUEL_TYPES[fuel] == "D":
                if euro_norm < 2:
                    return "HBEFA2/P_14_10"
                return "HBEFA2/P_14_8"
        if FUEL_TYPES[fuel] == "G":
            if euro_norm < 2:
                return "HBEFA2/P_14_14"
            return "HBEFA2/P_14_13"
        if FUEL_TYPES[fuel] == "D":
            if euro_norm < 2:
                return "HBEFA2/P_14_10"
            if euro_norm < 4:
                return "HBEFA2/P_14_4"
            return "HBEFA2/P_14_8"
    elif model == "HBEFA3":
        if size in SMALL_CARS or size in MEDIUM_CARS:
            return "HBEFA3/PC_%s_EU%s" % (FUEL_TYPES[fuel], euro_norm)
        return "HBEFA3/LDV_%s_EU%s" % (FUEL_TYPES[fuel], euro_norm)
    elif model == "PHEMlight":
        if size in SMALL_CARS or size in MEDIUM_CARS:
            return "PHEMlight/PC_%s_EU%s" % (FUEL_TYPES[fuel], euro_norm)
        return "PHEMlight/LCV_%s_EU%s_I" % (FUEL_TYPES[fuel], euro_norm)

def get_car_types(params, conn, model):
    car_types = {}
    cursor = conn.cursor()
    assert table_exists(conn, params[SP.car_table]), "Car table does not exist"
    command = "SELECT car_id, kba_no, engine_type, emmision_type FROM core.%s WHERE car_key = '%s'" % (
            params[SP.car_table], params[SP.car_fleet_key])
    cursor.execute(command)
    for row in cursor:
        car_types[row[0]] = get_emission_class(model, row[1], row[2], row[3])
    return car_types

def modify_vtypes(options, car_types, suffix=""):
    vtype = {}
    orig_types = {}
    unknown_types = set()
    emission_vtypes = defaultdict(set)
    for row in csv.DictReader(open(options.mapped_trips)):
        sumo_type = row[TH.vtype]
        ct = int(row[TH.car_type])
        emission_class = car_types.get(ct)
        if emission_class is None:
            if ct not in unknown_types:
                print("Unknown car_type %s in %s" % (ct, row))
                unknown_types.add(ct)
            vtype[build_uid(row)] = sumo_type
        else:
            vtype[build_uid(row)] = "%s_%s%s" % (sumo_type, emission_class, suffix)
        emission_vtypes[sumo_type].add(emission_class)
    for vt in sumolib.output.parse(options.vtype_file, "vType"):
        orig_types[vt.id] = vt

    vtypes_file = abspath_in_dir(os.path.dirname(options.mapped_trips), 'emission_types.xml')
    with open(vtypes_file, 'w') as f:
        f.write('<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n')
        for t, s in emission_vtypes.iteritems():
            vt = orig_types[t]
            for e_class in sorted(s):
                if e_class is None:
                    if vt.hasAttribute("emissionClass"):
                        del vt.emissionClass
                else:
                    vt.id = "%s_%s%s" % (t, e_class, suffix)
                    vt.setAttribute("emissionClass", e_class)
                f.write(vt.toXML("    "))
        f.write('</routes>\n')
    return vtype, vtypes_file
