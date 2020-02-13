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

# @file    constants.py
# @author  Jakob Erdmann
# @author  Michael Behrisch
# @date    2013-12-15

#constants especially for database table handling

import os
TAPAS_DAY_OVERLAP_MINUTES = 60 * 4  # do not allow the day to reach further into the next or last day
TAPAS_EXTRA_TIME = 3600 * 3  # allow for some stragglers / late night activities
BACKGROUND_TRAFFIC_SUFFIX = 'b'


# (T)APAS (H)eader fields
class TH:
    person_id = 'p_id'
    household_id = 'hh_id'
    depart_minute = 'start_time_min'  # minute of the day starting at 0
    mode = 'mode'
    source_long = 'lon_start'
    source_lat = 'lat_start'
    dest_long = 'lon_end'
    dest_lat = 'lat_end'
    duration = 'travel_time_sec'
    distance = 'distance_real_m'
    taz_id_start = 'taz_id_start'
    taz_id_end = 'taz_id_end'
    block_id_start = 'block_id_start'
    block_id_end = 'block_id_end'
    activity_duration_minutes = 'activity_duration_min'
    car_type = 'car_type'  # (sic)
    is_restricted = 'is_restricted'
    vtype = 'sumo_type'
    KEEP_COLUMNS = [
        person_id,
        household_id,
        depart_minute,
        mode,
        source_long,
        source_lat,
        dest_long,
        dest_lat,
        duration,
        # distance,
        taz_id_start,
        taz_id_end,
        # block_id_start,
        # block_id_end,
        activity_duration_minutes,
        car_type,
        is_restricted,
        vtype
    ]


# (T)APAS (H)eader field extensions
class THX:
    source_edge = 'source_edge'
    dest_edge = 'dest_edge'
    departpos = 'departpos'
    arrivalpos = 'arrivalpos'
    depart_second = 'depart_second'  # second of the day starting at 0
    uid = 'uid'
    lines = 'lines'
    delta = 'delta'
    sumo_time_sec = 'sumo_time_sec'
    sumo_dist_m = 'sumo_dist_m'
    fieldnames = TH.KEEP_COLUMNS + \
        [source_edge, dest_edge, depart_second, departpos, arrivalpos]
    oepnv_fieldnames = [uid, source_edge, dest_edge, lines, TH.duration]

# sumo nod.xml tagNames
class SX:
    nodes = 'nodes'
    node = 'node'
    lane = 'lane'
    edge = 'edge'
    edges = 'edges'
    allow = 'allow'
    shape = 'shape'
    x = 'x'
    y = 'y'
    node_id = 'id'
    edge_id = 'id'
    vehicle_id = 'id'
    person_id = 'id'
    fromnode = 'from'
    tonode = 'to'
    vehicle = 'vehicle'
    route = 'route'
    edges = 'edges'
    personinfo = 'personinfo'
    walk = 'walk'
    ride = 'ride'
    stop = 'stop'
    arrival = 'arrival'
    tripinfo = 'tripinfo'
    duration = 'duration'

# sumo vehicles classes
class SVC:
    passenger = 'passenger'
    delivery = 'delivery'
    truck = 'truck'
    pedestrian = 'pedestrian'

# interpretation of tapas mode
class MODE:
    pedestrian = '0'
    bicycle = '1'
    car = '2'
    fellow = '3'
    taxi = '4'
    public = '5'
    other = '6'
    bicycle_public = '261'
    car_public = '517'
    dummy_walk = 'D'

CAR_MODES = (MODE.car, MODE.taxi)

# simulation parameters
class SP:
    template = 'SUMO_TEMPLATE_FOLDER'
    destination = 'SUMO_DESTINATION_FOLDER'
    modes = 'SUMO_MODES'
    trip_table_prefix = "DB_TABLE_TRIPS"
    trip_output = 'DB_TABLE_SUMO_TRIP_OUTPUT'
    od_output = 'DB_TABLE_SUMO_OD_OUTPUT'
    od_entry = 'DB_TABLE_SUMO_OD_ENTRY'
    iteration = "ITERATION"
    max_iteration = "MAX_SUMO_ITERATION"
    status = "DB_TABLE_SUMO_STATUS"
    taz_table = 'DB_TABLE_TAZ'
    representatives = "DB_TABLE_REPRESENTATIVES"
    sample = 'DB_HH_SAMPLE_SIZE'
    del_temp = 'DELETE_TEMP'
    del_intermediate = 'DELETE_INTERMEDIATE_RESULTS'
    net_param = 'SUMO_NET_PARAMETER'
    car_table = 'DB_TABLE_CARS'
    car_fleet_key = 'DB_CAR_FLEET_KEY'
    add_traffic_table = 'DB_TABLE_ADDITIONAL_TRAFFIC'
    od_slice_table = 'DB_TABLE_MATRIXMAPS'
    od_slice_key = 'DB_NAME_MATRIX_TT_MIT_BASE'
    od_slices = 'SLICE'
    KEYS = [template, destination, modes, trip_table_prefix, od_output,
            iteration, max_iteration, status, taz_table, representatives,
            od_slice_table, od_slice_key]
    OPTIONAL = {template: "berlin_2010", destination: "berlin_2010",
                modes: ";".join(CAR_MODES),
                trip_table_prefix: "berlin_trips",
                trip_output: "sumo_trip",
                od_output: "sumo_od", od_entry: "sumo_od_entry",
                status: "global_sumo_status",
                taz_table: "berlin_taz_1223",
                representatives: "berlin_location_representatives",
                sample: "1.0",
                del_temp: "false", del_intermediate: "false",
                net_param: "{}",
                car_table: "berlin_cars", car_fleet_key: "MID2008_Y2010_BERLIN",
                add_traffic_table: "berlin_grundlast_ref2010_d",
                od_slices: [24]}

# logging message types for the database
class MSG_TYPE:
    info = 'message'
    warning = 'warning'
    error = 'error'
    fatal = 'fatal'
    finished = 'finished'
    started = 'started'
