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

# @file    s2t_pt.py
# @author  Michael Behrisch
# @date    2021-10-06

# parse duarouter all pair ozutput for public transport and upload the results to the database

from __future__ import print_function, division
import os
import sys
import collections
import numpy as np

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

from sumolib import output
from sumolib.miscutils import Statistics, benchmark, uMin, uMax
from sumolib.net import readNet
from sumolib.options import ArgumentParser

from common import csv_sequence_generator, parseTaz
from constants import TH, THX, SX, SP, BACKGROUND_TRAFFIC_SUFFIX
import db_manipulator


def parse_person(p):
    walkLength = [0, 0]
    walkDuration = [0, 0]
    rideLength = 0
    rideEnd = float(p.depart)
    idx = 0
    initWait = 0
    transfers = 0
    transferTime = 0
    ended = None
    for stage in p.getChildList():
        if stage.name == "walk":
            ended = float(stage.ended)
            walkLength[idx] += float(stage.routeLength)
            walkDuration[idx] = ended - rideEnd
        elif stage.name == "ride":
            if idx == 0:
                idx = 1
                initWait = float(stage.depart) - float(p.depart) - walkDuration[0]
            else:
                transfers += 1
                transferTime += float(stage.depart) - rideEnd
            rideEnd = ended = float(stage.ended)
            rideLength += float(stage.routeLength) + walkLength[1]
            walkLength[1] = 0  # reset from intermediate walks
    duration = (ended if p.arrival is None else float(p.arrival)) - float(p.depart)
    if idx == 0:
        return (duration, 0, 0, 0, 0, 0, 0, 0, 0), (walkLength[0], 0, 0, 0, 0, 0, 0, 0, 0)
    else:
        dur = (duration - sum(walkDuration) - initWait, walkDuration[0], initWait, walkDuration[1], transferTime)
        length = (rideLength, walkLength[0], 0, walkLength[1], transfers)
        return (0, 0, 0, 0) + dur, (0, 0, 0, 0) + length


@benchmark
def _parse_person_info_taz(routes, start, end):
    if os.path.isfile(routes):
        for p in output.parse(routes, 'person'):
            if not p.id.endswith(BACKGROUND_TRAFFIC_SUFFIX):
                if p.arrival is None:
                    print("Ignoring incomplete trip for person '%s'!" % p.id)
                else:
                    yield parseTaz(p) + parse_person(p)


@benchmark
def _get_all_pair_stats(rou_file, net):
    """Parses a duarouter .rou.xml output for persons"""
    sumoTime = Statistics("SUMO durations")
    sumoDist = Statistics("SUMO distances")
    for p in output.parse(rou_file, 'person'):
        duration, dist = parse_person(p)
        sumoTime.add(np.array(duration), p.id)
        sumoDist.add(np.array(dist), p.id)
        if sumoDist.count() % 10000 == 0:
            print("parsed %s taz representatives" % sumoDist.count())
        yield parseTaz(p) + (duration, dist)
    print(sumoTime)
    print(sumoDist)


def _createValueTuple(od, end, real=0, sumoTime=None, sumoDist=None):
    base = od + ("", end, real)
    if sumoTime is None:
        return base + (0, "{}", -1, "{}", -1)
    timeMean, timeStd = sumoTime.meanAndStdDev()
    distMean, distStd = sumoDist.meanAndStdDev()
    return base + (sumoTime.count() - real,
                   "{%s}" % (str(timeMean)[1:-1]), sum(timeStd) / len(timeStd),
                   "{%s}" % (str(distMean)[1:-1]), sum(distStd) / len(distStd))


@benchmark
def upload_all_pairs(conn, tables, start, end, real_routes, rep_routes, net, taz_list, startIdx=0):
    stats = list(_parse_person_info_taz(real_routes, start, end))
    print("Parsed taz results for %s persons from " % (len(stats), real_routes))
    stats.extend(_get_all_pair_stats(rep_routes, net))
    stats.sort()
    min_samples = 5
    last = None
    values = []
    sumoTime = Statistics("SUMO durations")
    sumoDist = Statistics("SUMO distances")
    real = 0
    remain = set([(o, d) for o in taz_list for d in taz_list])
    for source, dest, faked, duration, dist in stats:
        if (source, dest) != last:
            if last is not None:
                values.append(_createValueTuple(last, end, real, sumoTime, sumoDist))
                remain.discard(last)
                sumoTime = Statistics("SUMO durations")
                sumoDist = Statistics("SUMO distances")
                real = 0
            last = (source, dest)
        if not faked or sumoTime.count() < min_samples:
            if not faked:
                real += 1
            sumoTime.add(duration)
            sumoDist.add(dist)
    if last is not None:
        values.append(_createValueTuple(last, vType, end, real, sumoTime, sumoDist))
        remain.discard(last)
    if remain:
        print("inserting dummy data for %s unconnected O-D relations" % len(remain))
        for o, d in remain:
            values.append(_createValueTuple((o, d), vType, end))
    cursor = conn.cursor()
    # insert values
    odValues = []
    entryValues = []
    for idx, v in enumerate(values):
        odValues.append(str(v[:4] + (startIdx + idx,)))
        entryValues.append(str(v[4:] + (startIdx + idx, "{car}")))
    odQuery = """INSERT INTO temp.%s (taz_id_start, taz_id_end, sumo_type, interval_end, entry_id)
VALUES %s""" % (tables[0], ','.join(odValues))
    cursor.execute(odQuery)
    insertQuery = """INSERT INTO temp.%s (realtrip_count, representative_count,
 travel_time_sec, travel_time_stddev, distance_real, distance_stddev, entry_id, used_modes)
VALUES %s""" % (tables[1], ','.join(entryValues))
    cursor.execute(insertQuery)
    conn.commit()
    return startIdx + len(values)