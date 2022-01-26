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

# @file    s2t_miv.py
# @author  Jakob Erdmann
# @author  Michael Behrisch
# @date    2013-12-15

# parse sumo trip log from MIV trips and upload the results to the database

from __future__ import print_function, division
import os
import sys
import collections

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

import sumolib
from sumolib import output
from sumolib.miscutils import Statistics, benchmark, uMin, uMax
from sumolib.net import readNet
from sumolib.options import ArgumentParser

from common import csv_sequence_generator, parseTaz
from constants import TH, THX, SX, SP, BACKGROUND_TRAFFIC_SUFFIX
import db_manipulator
import s2t_pt


@benchmark
def aggregate_weights(weights_in, timeline, out_file=None):
    if out_file is None:
        out_file = weights_in[:-4] + '_aggregated.xml'
    elif not os.path.isdir(os.path.dirname(out_file)):
        os.makedirs(os.path.dirname(out_file))
    with open(out_file, 'w') as weights_out:
        weights_out.write('<meandata_aggregated>\n')
        idx = 0
        samples = collections.defaultdict(float)
        travel_time_ratios = collections.defaultdict(float)

        def write_interval(begin, end):
            if idx > 0:
                weights_out.write('    </interval>\n')
            weights_out.write(
                '    <interval begin="%s" end="%s">\n' % (begin, end))
            for e in sorted(samples.keys()):
                weights_out.write(
                    '        <edge id="%s" traveltime="%s"/>\n' % (e, samples[e] / travel_time_ratios[e]))

        begin = 24 * 3600
        for interval in output.parse(weights_in, ['interval']):
            if interval.edge is not None:
                for edge in interval.edge:
                    if edge.traveltime is not None:
                        s = float(edge.sampledSeconds)
                        samples[edge.id] += s
                        travel_time_ratios[edge.id] += s / \
                            float(edge.traveltime)
            end = (timeline[idx] + 24) * 3600
            if float(interval.end) == end:
                write_interval(begin, end)
                idx += 1
                if idx == len(timeline):
                    break
                begin = end
                samples.clear()
                travel_time_ratios.clear()
        if idx < len(timeline):
            write_interval(begin, (timeline[idx] + 24) * 3600)
        weights_out.write('    </interval>\n</meandata_aggregated>\n')
    return out_file


@benchmark
def _parse_vehicle_info(routes):
    sumoTime = Statistics("SUMO durations")
    sumoDist = Statistics("SUMO distances")
    stats = []
    for v in output.parse(routes, ('vehicle', 'person')):
        if not v.id.endswith(BACKGROUND_TRAFFIC_SUFFIX) and v.depart != "triggered":
            duration = float(v.arrival) - float(v.depart)
            length = float(v.routeLength) if v.routeLength else 0
            sumoTime.add(duration, v.id)
            sumoDist.add(length, v.id)
            dataTuple = tuple(v.id.split('_'))
            if v.name == "vehicle":
                dataTuple += ((0, 0, duration), (0, 0, length))
            else:
                dataTuple += s2t_pt.parse_person(v)
            stats.append(dataTuple)
    print("Parsed results for %s vehicles and persons" % len(stats))
    print(sumoTime)
    print(sumoDist)
    return stats


@benchmark
def _parse_vehicle_info_taz(routes, start, end, vType):
    stats = []
    if os.path.isfile(routes):
        for v in output.parse(routes, 'vehicle'):
            if not v.id.endswith(BACKGROUND_TRAFFIC_SUFFIX) and v.depart != "triggered":
                depart = float(v.depart) % (24 * 3600)
                # vType is something like "passenger" and v.type "passenger_PHEMlight/PC_G_EU3"
                if depart >= start and depart < end and v.type is not None and v.type.startswith(vType):
                    stats.append(parseTaz(v) + (0, float(v.arrival) - float(v.depart), float(v.routeLength)))
    print("Parsed taz results for %s vehicles" % len(stats))
    return stats


@benchmark
def upload_trip_results(conn, key, params, routes, limit=None):
    tripstats = _parse_vehicle_info(routes)
    table = '%s_%s' % (params[SP.trip_output], key)
    if conn is None:
        print("Warning! No database connection, writing trip info to file %s.csv." % table)
        print('\n'.join(map(str, tripstats[:limit])), file=open(table + ".csv", "w"))
        return
    schema_table, table, exists = db_manipulator.check_schema_table(conn, 'temp', table)
    cursor = conn.cursor()
    if exists:
        cursor.execute("DROP TABLE " + schema_table)
    createQuery = """
CREATE TABLE %s
(
  p_id integer NOT NULL,
  hh_id integer NOT NULL,
  start_time_min integer NOT NULL,
  clone_id integer NOT NULL DEFAULT 0,
  travel_time_sec double precision[],
  distance_real double precision[],
  CONSTRAINT %s_pkey PRIMARY KEY (p_id, hh_id, start_time_min, clone_id)
)
""" % (schema_table, table)
    cursor.execute(createQuery)
    if tripstats:
        values = [str(tuple([str(e).replace("(", "{").replace(")", "}")  for e in t])) for t in tripstats[:limit]]
        insertQuery = "INSERT INTO %s (p_id, hh_id, start_time_min, clone_id, travel_time_sec, distance_real) VALUES "
        cursor.execute(insertQuery % schema_table + ','.join(values))
        conn.commit()


@benchmark
def _get_all_pair_stats(rou_file, net):
    """Parses a duarouter .rou.alt.xml output for travel times and calculates the route length.
    The file is supposed to contain only vehicles of a single vType"""
    sumoTime = Statistics("SUMO durations")
    sumoDist = Statistics("SUMO distances")
    for vehicle in sumolib.xml.parse_fast_structured(rou_file, 'vehicle', 'id', {'route': ('cost', 'edges', 'routeLength'), 'param': ('key', 'value')}):
        duration = float(vehicle.route[0].cost)
        distance = float(vehicle.route[0].routeLength)
        sumoTime.add(duration, vehicle.id)
        sumoDist.add(distance, vehicle.id)
        if sumoDist.count() % 100000 == 0:
            print("parsed %s taz representatives" % sumoDist.count())
        fromTaz, toTaz = parseTaz(vehicle)
        yield fromTaz, toTaz, 1, duration, distance
    print(sumoTime)
    print(sumoDist)


def _createValueTuple(od, vType, end, real, sumoTime, sumoDist):
    base = od + (vType, end, real)
    timeMean, timeStd = sumoTime.meanAndStdDev()
    distMean, distStd = sumoDist.meanAndStdDev()
    return base + (sumoTime.count() - real, "{0,0,%s}" % timeMean, timeStd,
                   "{0,0,%s}" % distMean, distStd)


@benchmark
def upload_all_pairs(conn, tables, start, end, vType, real_routes, rep_routes, net, taz_list, startIdx=0):
    stats = _parse_vehicle_info_taz(real_routes, start, end, vType)
    stats.extend(_get_all_pair_stats(rep_routes, net))
    stats.sort()
    min_samples = 5
    last = None
    values = []
    sumoTime = Statistics("SUMO durations")
    sumoDist = Statistics("SUMO distances")
    real = 0
    for source, dest, faked, duration, dist in stats:
        if (source, dest) != last:
            if last is not None:
                values.append(_createValueTuple(last, vType, end, real, sumoTime, sumoDist))
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
    cursor = conn.cursor()
    # insert values
    odValues = []
    entryValues = []
    for idx, v in enumerate(values):
        odValues.append(str(v[:4] + (startIdx + idx,)))
        entryValues.append(str(v[4:] + (startIdx + idx, "{car}")))
    odQuery = """INSERT INTO %s (taz_id_start, taz_id_end, sumo_type, interval_end, entry_id)
                 VALUES %s""" % (tables[0], ','.join(odValues))
    cursor.execute(odQuery)
#    odQuery = "INSERT INTO %s (taz_id_start, taz_id_end, sumo_type, interval_end, entry_id) VALUES ?" % tables[0]
#    db_manipulator.execute(conn, odQuery, odValues)
    insertQuery = """INSERT INTO %s (realtrip_count, representative_count,
                     travel_time_sec, travel_time_stddev, distance_real, distance_stddev, entry_id, used_modes)
                     VALUES %s""" % (tables[1], ','.join(entryValues))
    cursor.execute(insertQuery)
#    insertQuery = "INSERT INTO %s (realtrip_count, representative_count, travel_time_sec, travel_time_stddev, distance_real, distance_stddev, entry_id, used_modes) VALUES ?" % tables[1]
#    db_manipulator.execute(conn, insertQuery, entryValues)
    conn.commit()
    return startIdx + len(values)


def create_all_pairs(conn, key, params):
    cursor = conn.cursor()
    schema_table, table, exists = db_manipulator.check_schema_table(conn, 'temp', '%s_%s' % (params[SP.od_output], key))
    if exists:
        cursor.execute("DROP TABLE " + schema_table)
    createQuery = """
CREATE TABLE %s
(
  taz_id_start integer NOT NULL,
  taz_id_end integer NOT NULL,
  sumo_type text NOT NULL DEFAULT '',
  is_restricted boolean NOT NULL DEFAULT FALSE,
  interval_end double precision NOT NULL,
  entry_id serial,
  trip_source traffic_source,
  CONSTRAINT %s_pkey PRIMARY KEY (taz_id_start, taz_id_end, sumo_type, is_restricted, interval_end)
)
""" % (schema_table, table)
    cursor.execute(createQuery)

    entry_schema_table, table, exists = db_manipulator.check_schema_table(conn, 'temp', '%s_%s' % (params[SP.od_entry], key))
    if exists:
        cursor.execute("DROP TABLE " + schema_table)
    createQuery = """
CREATE TABLE %s
(
  entry_id integer NOT NULL,
  travel_time_sec double precision[],
  distance_real double precision[],
  travel_time_stddev double precision,
  distance_stddev double precision,
  realtrip_count integer,
  representative_count integer,
  used_modes mode_type[],
  CONSTRAINT %s_pkey PRIMARY KEY (entry_id, used_modes)
)
""" % (entry_schema_table, table)
    cursor.execute(createQuery)
    conn.commit()
    return schema_table, entry_schema_table


@benchmark
def main():
    argParser = ArgumentParser()
    db_manipulator.add_db_arguments(argParser)
    argParser.add_argument("-n", "--net-file",
                           help="specifying the net file of the scenario to use")
    argParser.add_argument("-k", "--simkey", default="test",
                           help="simulation key to use")
    argParser.add_argument("-l", "--limit", type=int,
                           help="maximum number of trips to retrieve")
    argParser.add_argument("--representatives", default="",
                           help="set the route alternatives file to read representative travel times from")
    argParser.add_argument("--real-trips", default="",
                           help="set the route file to read travel times for real trips from")
    argParser.add_argument("-a", "--all-pairs",
                           default=False, action="store_true",
                           help="Only write the all pairs table")
    options, args = argParser.parse_known_args()
    if len(args) == 2:
        aggregate_weights(args[0], [float(x) for x in args[1].split(",")])
        return
    conn = db_manipulator.get_conn(options)
    if os.path.isfile(options.real_trips) and not options.all_pairs:
        upload_trip_results(conn, options.simkey, SP.OPTIONAL, options.real_trips, options.limit)
    if os.path.isfile(options.representatives):
        tables = create_all_pairs(conn, options.simkey, SP.OPTIONAL)
        upload_all_pairs(conn, tables, 0, 86400, "passenger", options.real_trips,
                         options.representatives, readNet(options.net_file), [])
    if conn:
        conn.close()

if __name__ == "__main__":
    main()
