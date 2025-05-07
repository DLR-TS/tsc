# Copyright (C) 2013-2025 German Aerospace Center (DLR) and others.
# This program and the accompanying materials are made available under the
# terms of the Eclipse Public License 2.0 which is available at
# https://www.eclipse.org/legal/epl-2.0/
# This Source Code may also be made available under the following Secondary
# Licenses when the conditions for such availability set forth in the Eclipse
# Public License 2.0 are satisfied: GNU General Public License, version 2
# or later which is available at
# https://www.gnu.org/licenses/old-licenses/gpl-2.0-standalone.html
# SPDX-License-Identifier: EPL-2.0 OR GPL-2.0-or-later

# @file    edgemapper.py
# @author  Jakob Erdmann
# @author  Michael Behrisch
# @date    2013-12-15

# map utm coordinates onto a network

from __future__ import print_function
import os
import sys

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:   
    sys.exit("please declare environment variable 'SUMO_HOME'")

import sumolib

class EdgeMapper:

    def init(self, net, taz, location_prios):
        self.net = net
        self.result_cache = {}  # geo-locations are reused frequently
        self.taz = taz
        self.location_prios = location_prios

    def map_to_edge(self, xycoord, taz=None, vClass=None, min_radius=50, max_radius=1000, tazExcess=2.):
        key = (xycoord, taz, vClass)
        if key in self.result_cache:
            return self.result_cache[key]

        x, y = xycoord
        minDist = -1
        minEdge = None
        minInTazDist = -1
        minInTazEdge = None
        minPrioDist = -1
        minPrioEdge = None
        radius = min_radius
        checkTaz = taz in self.taz
        checkPrio = xycoord in self.location_prios
        while (minEdge is None or checkTaz or checkPrio) and radius <= max_radius:
            for edge, dist in self.net.getNeighboringEdges(x, y, radius, allowFallback=False):
                if vClass is None or edge.allows(vClass):
                    if minEdge is None or dist < minDist or (dist == minDist and minEdge < edge.getID()):
                        minDist = dist
                        minEdge = edge.getID()
                    if minInTazEdge is None or dist < minInTazDist or (dist == minInTazDist and minInTazEdge < edge.getID()):
                        if taz in self.taz and edge.getID() in self.taz[taz]:
                            minInTazDist = dist
                            minInTazEdge = edge.getID()
                            checkTaz = False
                    if xycoord in self.location_prios and edge.getPriority() >= self.location_prios[xycoord]:
                        if minPrioEdge is None or dist < minPrioDist or (dist == minPrioDist and minPrioEdge < edge.getID()):
                            minPrioDist = dist
                            minPrioEdge = edge.getID()
                            checkPrio = False
            radius *= 2

        if minInTazEdge is not None and minInTazDist < max(min_radius, tazExcess * minDist):
            minDist = minInTazDist
            minEdge = minInTazEdge
        if minPrioEdge is not None:
            minDist = minPrioDist
            minEdge = minPrioEdge
        result = (minDist, minEdge, minInTazEdge, minInTazDist)
        self.result_cache[key] = result
        return result


_instance = EdgeMapper()


def init(options, taz):
    net = sumolib.net.readNet(options.net_file, withFoes=False, withConnections=False) if options.net is None else options.net
    location_prios = {}
    if os.path.exists(options.location_priority_file):
        for loc in sumolib.xml.parse(options.location_priority_file, "poi"):
            xy = net.convertLonLat2XY(round(float(loc.lon), 5), round(float(loc.lat), 5))
            location_prios[xy] = int(loc.type)
    _instance.init(net, taz, location_prios)
    _instance.trip_filter = options.script_module.trip_filter if hasattr(options.script_module, "trip_filter") else None


def convertLonLat2XY(lon_str, lat_str):
    return _instance.net.convertLonLat2XY(round(float(lon_str), 5), round(float(lat_str), 5))


def trip_filter(row, source, dest):
    return _instance.trip_filter and not _instance.trip_filter(row, source, dest)


def get_location_prios():
    return _instance.location_prios


def map_to_edge(xycoord, taz=None, vClass=None, min_radius=50, max_radius=1000, tazExcess=2.):
    return _instance.map_to_edge(xycoord, taz, vClass, min_radius, max_radius, tazExcess)
