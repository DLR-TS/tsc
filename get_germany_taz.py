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

# @file    get_germany_taz.py
# @author  Jakob Erdmann
# @author  Michael Behrisch
# @date    2013-12-15

# pull taz for germany from the VF tapas server

from __future__ import print_function
import os
import sys
import ast

sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
import sumolib  # noqa

import db_manipulator  # noqa


def parse_args():
    argParser = sumolib.options.ArgumentParser()
    db_manipulator.add_db_arguments(argParser)
    argParser.add_argument("-o", "--output", default="d-modell.poly.xml", help="output file")
    return argParser.parse_args()


def get_polys(server_options, table='quesadillas.zonierung_d_modell', net=None):
    conn = db_manipulator.get_conn(server_options)
    if conn is None:
        print("Warning! No database, cannot retrieve suburbian TAZ.")
        return
    command = "SELECT vbz_6561, ST_ASTEXT(ST_TRANSFORM(the_geom, 4326)) FROM %s" % table
    cursor = conn.cursor()
    cursor.execute(command)
    for row in cursor:
        tazid = int(row[0])
        if row[1].startswith("MULTIPOLYGON"):
            multi = ast.literal_eval(row[1][12:].replace(" ", ","))
            if type(multi[0]) is float:
                multi = (multi,)
            shapes = []
            for s in multi:
                if type(s[0]) is tuple:
                    s = s[0]
                shape = []
                x = None
                for idx, coord in enumerate(s):
                    if x is None:
                        x = coord
                    else:
                        if net is not None:
                            x, coord = net.convertLonLat2XY(x, coord)
                        shape.append((x, coord))
                        x = None
                shapes.append(shape)
            yield tazid, shapes
        else:
            print("unknown shape", row)
    conn.close()

def main():
    options = parse_args()
    with open(options.output, "w") as out:
        for tazid, shapes in get_polys(options):
            for idx, shape in enumerate(shapes):
                print('    <poly id="%s:%s" shape="%s"/>' % (tazid, idx, " ".join(["%s,%s" % e for e in shape])), file=out)


if __name__ == "__main__":
    main()
