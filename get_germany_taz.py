#!/usr/bin/env python
"""
@file    get_germany_taz.py
@author  Jakob.Erdmann@dlr.de
@author  Michael.Behrisch@dlr.de
@date    2013-12-15
@version $Id: get_trips.py 5484 2017-01-10 17:04:39Z behr_mi $

pull taz for germany from the VF tapas server

Copyright (C) 2013-2015 DLR/TS, Germany
All rights reserved
"""
from __future__ import print_function
import sys
import ast
from optparse import OptionParser

import get_trips


def parse_args():
    USAGE = "Usage: " + sys.argv[0] + " <options>"
    optParser = OptionParser()
    optParser.add_option("-s", "--server", default="herakles", help="postgres server name")
    optParser.add_option("-o", "--output", default="d-modell.poly.xml", help="output file")

    options, args = optParser.parse_args()
    if len(args) != 0:
        sys.exit(USAGE)
    return options


def get_polys(server="herakles", table='quesadillas.zonierung_d_modell', net=None):
    conn = get_trips.get_conn(server)
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
#    assert get_trips.table_exists(conn, options.taztable), "No taz table (%s) found" % options.taztable
    with open(options.output, "w") as out:
        for tazid, shapes in get_polys(options.server):
            for idx, shape in enumerate(shapes):
                print('    <poly id="%s:%s" shape="%s"/>' % (tazid, idx, " ".join(["%s,%s" % e for e in shape])), file=out)


if __name__ == "__main__":
    main()
