#!/usr/bin/env python

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

# @file    get_motorway_access.py
# @author  Jakob Erdmann
# @author  Michael Behrisch
# @date    2013-12-15

# create motorway access points for special locations

from __future__ import print_function
import sys
from optparse import OptionParser

import get_trips


def parse_args():
    USAGE = "Usage: " + sys.argv[0] + " <options>"
    optParser = OptionParser()
    optParser.add_option("-s", "--server", default="perseus", help="postgres server name")
    optParser.add_option("-o", "--output", default="scenario_pre/berlin_2010/location_priorities.xml", help="output file")

    options, args = optParser.parse_args()
    if len(args) != 0:
        sys.exit(USAGE)
    return options


def get_locations(server, table):
    conn = get_trips.get_conn(server)
    for suffix in ("start", "end"):
        command = """SELECT DISTINCT taz_id_%s, lon_%s, lat_%s FROM core.%s
                     WHERE taz_id_%s < -1000000""" % (suffix, suffix, suffix, table, suffix)
        cursor = conn.cursor()
        cursor.execute(command)
        for row in cursor:
            yield (row[0], suffix[0]) + row[1:]
    conn.close()


def save_locations(output, server="perseus", table='berlin_grundlast_2010_ref'):
    with open(output, "w") as out:
        print("<additional>", file=out)
        for loc in sorted(get_locations(server, table)):
            print('    <poi id="%s_%s" lon="%s" lat="%s" type="-1"/>' % loc, file=out)
        print("</additional>", file=out)


if __name__ == "__main__":
    options = parse_args()
    save_locations(options.output, options.server)
