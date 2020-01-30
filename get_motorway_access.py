#!/usr/bin/env python
"""
@file    get_motorway_access.py
@author  Jakob.Erdmann@dlr.de
@author  Michael.Behrisch@dlr.de
@date    2013-12-15
@version $Id: get_trips.py 5484 2017-01-10 17:04:39Z behr_mi $

create motorway access points for special locations

# Copyright (C) 2010-2020 German Aerospace Center (DLR) and others.
# This program and the accompanying materials
# are made available under the terms of the Eclipse Public License v2.0
# which accompanies this distribution, and is available at
# http://www.eclipse.org/legal/epl-v20.html
# SPDX-License-Identifier: EPL-2.0
"""
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
