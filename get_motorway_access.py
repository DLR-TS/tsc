#!/usr/bin/env python

# Copyright (C) 2013-2022 German Aerospace Center (DLR) and others.
# This program and the accompanying materials are made available under the
# terms of the Eclipse Public License 2.0 which is available at
# https://www.eclipse.org/legal/epl-2.0/
# This Source Code may also be made available under the following Secondary
# Licenses when the conditions for such availability set forth in the Eclipse
# Public License 2.0 are satisfied: GNU General Public License, version 2
# or later which is available at
# https://www.gnu.org/licenses/old-licenses/gpl-2.0-standalone.html
# SPDX-License-Identifier: EPL-2.0 OR GPL-2.0-or-later

# @file    get_motorway_access.py
# @author  Jakob Erdmann
# @author  Michael Behrisch
# @date    2013-12-15

# create motorway access points for special locations

from __future__ import print_function
import os
import sys

if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")
from sumolib.options import ArgumentParser

import db_manipulator


def parse_args():
    argParser = ArgumentParser()
    db_manipulator.add_db_arguments(argParser)
    argParser.add_argument("-o", "--output", default="osm_scenario_pre/mitte_net/location_priorities.xml", help="output file")
    options = argParser.parse_args()
    return options


def get_locations(server, table):
    conn = db_manipulator.get_conn(server)
    for suffix in ("start", "end"):
        command = """SELECT DISTINCT taz_id_%s, lon_%s, lat_%s FROM core.%s
                     WHERE taz_id_%s < -1000000""" % (suffix, suffix, suffix, table, suffix)
        cursor = conn.cursor()
        cursor.execute(command)
        for row in cursor:
            yield (row[0], suffix[0]) + row[1:]
    conn.close()


def save_locations(output, server, table='berlin_grundlast_2010_ref'):
    with open(output, "w") as out:
        print("<additional>", file=out)
        for loc in sorted(get_locations(server, table)):
            print('    <poi id="%s_%s" lon="%s" lat="%s" type="-1"/>' % loc, file=out)
        print("</additional>", file=out)


if __name__ == "__main__":
    options = parse_args()
    save_locations(options.output, options)
