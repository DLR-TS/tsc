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

# @file    get_trips.py
# @author  Jakob Erdmann
# @author  Michael Behrisch
# @date    2013-12-15

# pull trips from the VF tapas server

from __future__ import print_function, division
import os
import sys
import collections
import random
import math
from optparse import OptionParser

import psycopg2 as pgdb

from constants import TH, MODE, THX, SP, CAR_MODES

ALL_PAIRS = 'all_pairs'


def parse_args():
    USAGE = "Usage: " + sys.argv[0] + " <options>"
    optParser = OptionParser()
    optParser.add_option("-a", "--all-pairs", dest="all_pairs",
                         default=False, action="store_true",
                         help="Generate trips for all pairs of traffic zones")
    optParser.add_option("-d", "--departure", type=int, default=3600 * 16,
                         help="When used with --all-pairs, set departure second to <INT>")
    optParser.add_option("-k", "--simkey", help="simulation key to retrieve")
    optParser.add_option("-l", "--limit", type=int,
                         help="maximum number of trips to retrieve")
    optParser.add_option("--seed", type=int, default=23432, help="random seed")
    optParser.add_option("-s", "--server", default="test", help="postgres server name")
    optParser.add_option("--representatives", default='berlin_location_representatives',
                         help="set the table to read representatives from")
    optParser.add_option("--triptable", default='berlin_trips',
                         help="set the table to receive trips from")
    optParser.add_option("--taztable", default='berlin_taz',
                         help="set the table to read districts from")
    optParser.add_option("-m", "--modes", default=','.join(CAR_MODES),
                         help="the traffic modes to retrieve as a list of integers (default '%default')")

    options, args = optParser.parse_args()
    if len(args) != 0:
        sys.exit(USAGE)
    options.limit_sql = "" if options.limit is None else "LIMIT %s" % options.limit
    return options


# TODO create a config file with the credentials
def get_conn(server, db_credentials):
    if server is None:
        return None
    db = db_credentials[server]
    return pgdb.connect(host=db['db_host'], port=db['db_port'], user=db['db_user'], password=db['db_password'], database=db['database'])


def get_active_sim_keys(server, overrides):
    sys.stdout.flush()
    conn = get_conn(server)
    # get any open combination of sim_key and iteration
    cursor_open = conn.cursor()
    command = """SELECT sim_key, param_value::float::integer AS iteration FROM public.simulation_parameters
                 WHERE param_key = '%s' ORDER BY sim_key, iteration""" % SP.max_iteration
    cursor_open.execute(command)
    max_iterations = dict(cursor_open.fetchall())

    command = """SELECT sim_key, param_value::float::integer AS iteration FROM public.simulation_parameters
                 WHERE param_key = '%s' ORDER BY sim_key, iteration""" % SP.iteration
    cursor_open.execute(command)

    for sim_key, iteration in cursor_open.fetchall():
        command_dirs = """SELECT param_key, param_value FROM public.simulation_parameters
                          WHERE sim_key = '%s' AND param_key IN ('%s')
            """ % (sim_key, "','".join(SP.KEYS + SP.OPTIONAL.keys()))
        cursor_open.execute(command_dirs)
        sim_params = dict(SP.OPTIONAL)
        sim_params.update(dict(cursor_open.fetchall()))
        sim_params.update(overrides)
        if iteration >= max_iterations[sim_key] and sim_params.get(SP.status) is not None:
            continue

        assert table_exists(
            conn, sim_params[SP.od_slice_table]), "Matrix timeline table does not exist"
        command_timeline = """SELECT "matrixMap_distribution" FROM core.%s WHERE "matrixMap_name" = '%s'""" % (
            sim_params[SP.od_slice_table], sim_params[SP.od_slice_key])
        cursor_open.execute(command_timeline)
        sim_params[SP.od_slices] = cursor_open.fetchone()[0]
        missing_params = set(SP.KEYS + SP.OPTIONAL.keys()).difference(set(sim_params.keys()))
        assert len(missing_params) == 0, "parameters missing: %s" % missing_params

        # check whether the iteration is or was already running
        if sim_params.get(SP.status):
            assert table_exists(
                conn, sim_params[SP.status]), "Status table does not exist"
            command_status = "SELECT msg_type FROM core.%s WHERE sim_key = '%s' AND iteration = %s ORDER BY status_time DESC LIMIT 1" % (
                sim_params[SP.status], sim_key, iteration)
            cursor_open.execute(command_status)
            status = cursor_open.fetchall()
            if status and status[0][0] == "pending":
                yield sim_key, iteration, sim_params
        else:
            yield sim_key, iteration, sim_params
    conn.close()


def fetch_chunks(cursor, arraysize=100000):
    cursor.arraysize = arraysize
    rows = cursor.fetchmany()
    while rows:
        print("fetched %s rows" % len(rows))
        for row in rows:
            yield row
        rows = cursor.fetchmany()


def fetch_and_write(conn, command, tripfile, columns, mode="w"):
    cursor = conn.cursor()
    cursor.execute(command)
    num_rows = 0
    with open(tripfile, mode) as f:
        print(",".join(columns), file=f)
        for row in fetch_chunks(cursor):
            num_rows += 1
            print(','.join(map(str, row)), file=f)
    print("wrote %s rows to %s" % (num_rows, tripfile))


def table_exists(conn, table):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT TRUE FROM pg_class WHERE relname = '%s' AND relkind='r'" % table)
    return len(cursor.fetchall()) > 0


def write_trips(conn, sim_key, limit, tripfile, params):
    trip_table = "%s_%s" % (params[SP.trip_table_prefix], sim_key)
    taz_table = params[SP.taz_table]
    modes = params[SP.modes].replace(";", ",")

    assert table_exists(conn, trip_table), "No trip table (%s) found" % trip_table
    fieldnames = TH.KEEP_COLUMNS
    columns = list(fieldnames)  # make a copy
    columns[fieldnames.index(TH.taz_id_start)] = "taz1.taz_num_id AS %s" % TH.taz_id_start
    columns[fieldnames.index(TH.taz_id_end)] = "taz2.taz_num_id AS %s" % TH.taz_id_end
    if modes == ','.join(CAR_MODES):
        columns[fieldnames.index(TH.vtype)] = "cars.vtype_id AS %s" % TH.vtype
        command = """SELECT %s FROM public.%s trips, core.%s taz1, core.%s taz2, core.%s cars
                 WHERE trips.%s = taz1.taz_id AND trips.%s = taz2.taz_id AND mode in (%s) AND
                       cars.car_key = '%s' AND cars.car_id = trips.car_type
                 ORDER BY p_id, hh_id, start_time_min
                 %s""" % (','.join(columns), trip_table, taz_table, taz_table, params[SP.car_table],
                          TH.taz_id_start, TH.taz_id_end, modes, params[SP.car_fleet_key], limit)
    else:
        # TODO fix vehicle type
        columns[fieldnames.index(TH.vtype)] = "'passenger' AS %s" % TH.vtype
        command = """SELECT %s FROM public.%s trips, core.%s taz1, core.%s taz2
                     WHERE trips.%s = taz1.taz_id AND trips.%s = taz2.taz_id AND mode in (%s)
                     ORDER BY p_id, hh_id, start_time_min
                     %s""" % (','.join(columns), trip_table, taz_table, taz_table,
                              TH.taz_id_start, TH.taz_id_end, modes, limit)
    fetch_and_write(conn, command, tripfile, fieldnames)
    return command


def write_background_trips(conn, trip_table, limit, tripfile, params):
    assert table_exists(conn, trip_table), "No trip table (%s) found" % trip_table
    fieldnames = TH.KEEP_COLUMNS
    columns = list(fieldnames)  # make a copy
    columns[fieldnames.index(TH.vtype)] = "cars.vtype_id AS %s" % TH.vtype
    command = """SELECT %s FROM core.%s trips, core.%s cars
                 WHERE cars.car_key = '%s' AND cars.car_id = trips.car_type
                 ORDER BY p_id, hh_id, start_time_min
                 %s""" % (','.join(columns), trip_table, params[SP.car_table], params[SP.car_fleet_key], limit)
    fetch_and_write(conn, command, tripfile, fieldnames)
    return command


def write_all_pairs(conn, vType, depart, limit, tripfile, params, seed):
    random.seed(seed)
    fieldnames = TH.KEEP_COLUMNS + [THX.depart_second]
    template = list(fieldnames)
    template[fieldnames.index(TH.depart_minute)] = str(depart / 60)
    template[fieldnames.index(TH.mode)] = MODE.car
    template[fieldnames.index(TH.duration)] = '0'
    template[fieldnames.index(TH.activity_duration_minutes)] = '0'
    template[fieldnames.index(TH.car_type)] = '-1'
    template[fieldnames.index(TH.is_restricted)] = '0'
    template[fieldnames.index(TH.vtype)] = vType
    template[fieldnames.index(THX.depart_second)] = str(depart)
    num_samples = 5
    trips = []
    reps = collections.defaultdict(list)
    cursor = conn.cursor()
    command = """SELECT taz_num_id, id, X(representative_coordinate), Y(representative_coordinate)
                 FROM core.%s r, core.%s t WHERE r.taz_id = t.taz_id ORDER BY taz_num_id, id""" % (
                 params[SP.representatives], params[SP.taz_table])
    cursor.execute(command)
    for row in cursor:
        reps[row[0]].append(row[1:])
    keys = sorted(reps.keys())
    if limit:
        max_rows = int(limit.split()[1])
        max_taz = int(math.sqrt(max_rows))
    else:
        max_rows = 1e400
        max_taz = None
    num_rows = 0
    with open(tripfile, 'w') as f:
        print(",".join(fieldnames), file=f)
        for start in keys:
            start_reps = reps[start]
            for end in keys:
                end_reps = reps[end]
                l = [s + e for s in start_reps for e in end_reps]
                random.shuffle(l)
                for trip in l[:num_samples]:
                    num_rows += 1
                    columns = list(template)
                    columns[fieldnames.index(TH.person_id)] = str(trip[0])
                    columns[fieldnames.index(TH.household_id)] = str(trip[3])
                    columns[fieldnames.index(TH.source_long)] = str(trip[1])
                    columns[fieldnames.index(TH.source_lat)] = str(trip[2])
                    columns[fieldnames.index(TH.dest_long)] = str(trip[4])
                    columns[fieldnames.index(TH.dest_lat)] = str(trip[5])
                    columns[fieldnames.index(TH.taz_id_start)] = str(start)
                    columns[fieldnames.index(TH.taz_id_end)] = str(end)
                    print(','.join(columns), file=f)
                    if num_rows >= max_rows:
                        print("wrote %s rows to %s" % (num_rows, tripfile))
                        return keys[:max_taz]
    print("wrote %s rows to %s" % (num_rows, tripfile))
    return keys[:max_taz]


def tripfile_name(key, limit=None, target_dir='iteration/trips'):
    l = '' if limit is None else '_limit%s' % limit
    dir_name = target_dir
    if not os.path.isdir(dir_name):
        os.makedirs(dir_name)
    trips_path = os.path.join(dir_name, '%s%s.csv' % (key, l))
    return trips_path


def main():
    options = parse_args()
    conn = get_conn(options.server)
    if options.all_pairs:
        params = {SP.representatives: options.representatives,
                  SP.taz_table: options.taztable,
                  SP.trip_table_prefix: options.triptable,
                  SP.modes: options.modes}
        write_all_pairs(conn, 'passenger', options.departure, options.limit_sql,
                        tripfile_name(ALL_PAIRS, options.limit), params, options.seed)
    else:
        if options.simkey is not None:
            sim_keys = dict([(k, p) for k, _, p in get_active_sim_keys(options.server, {SP.status: None})])
            if options.simkey in sim_keys:
                write_trips(conn, options.simkey, options.limit_sql,
                            tripfile_name(options.simkey, options.limit), sim_keys[options.simkey])
            else:
                print("Error: simkey '%s' not found. Available:\n%s" % (
                      options.simkey, sim_keys.keys()))
        else:
            # get all
            for sim_key, _, params in get_active_sim_keys(options.server):
                write_trips(conn, sim_key, options.limit_sql,
                            tripfile_name(sim_key, options.limit), params)
    conn.close()


if __name__ == "__main__":
    main()
