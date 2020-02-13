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

# @file    edgemapper.py
# @author  Jakob Erdmann
# @author  Michael Behrisch
# @date    2013-12-15

# map utm coordinates onto a network

from __future__ import print_function
import os
import sys
from collections import defaultdict

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:   
    sys.exit("please declare environment variable 'SUMO_HOME'")

import sumolib
from sumolib.miscutils import Statistics

class EdgeMapper:

    def __init__(self, net, taz_file, generate_taz_file, location_prios):
        self.net = net
        self.result_cache = {}  # geo-locations are reused frequently
        self.errors = Statistics("Mapping deviations")
        self.noTazEdge = 0
        self.taz = defaultdict(set)
        self.generate_taz_file = generate_taz_file
        self.location_prios = location_prios
        if os.path.exists(taz_file):
            for t in sumolib.output.parse_fast(taz_file, "taz", ["id", "edges"]):
                self.taz[t.id] = set(t.edges.split())

    def map_to_edge(self, xycoord, taz=None, vClass=None, min_radius=50, max_radius=1000, tazExcess=2., uid=None, log=None):
        key = (xycoord, vClass)
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
                    if self.generate_taz_file and dist <= minDist + min_radius:
                        self.taz[taz].add(edge.getID())
            radius *= 2

        if minInTazEdge is not None and minInTazDist < max(min_radius, tazExcess * minDist):
            minDist = minInTazDist
            minEdge = minInTazEdge
        if minPrioEdge is not None:
            minDist = minPrioDist
            minEdge = minPrioEdge
        self.result_cache[key] = minEdge
        if minEdge is not None:
            if taz and (taz not in self.taz or minEdge not in self.taz[taz]):
                if minInTazEdge is not None and log is not None:
                    log("Mapping %s to %s (dist: %.2f) which is not in taz %s, best match in taz is %s (dist: %.2f)" % (xycoord, minEdge, minDist, taz, minInTazEdge, minInTazDist))
                self.noTazEdge += 1
            self.errors.add(minDist, "xycoord=%s, edge=%s, uid=%s" % (xycoord, minEdge, uid))
        return minEdge
