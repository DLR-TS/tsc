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

# @file    postprocess.py
# @author  Jakob.Erdmann@dlr.de
# @author  Michael.Behrisch@dlr.de
# @date    2013-12-15

# collected post processing steps (trajectories, emissions, persons, ...)

from __future__ import print_function, division
import os
import sys
import math
import csv
import subprocess
import time
from collections import defaultdict

sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
import sumolib
from sumolib.miscutils import benchmark, uMax

from common import csv_sequence_generator, abspath_in_dir, build_uid
from constants import TH, THX, SX, TAPAS_EXTRA_TIME, CAR_MODES, SP
import db_manipulator
import emissions


def call(cmd):
    proc = subprocess.Popen(cmd)
    # wait a little to have less garbled initial outputs from parallel runs
    time.sleep(1)
    sys.stdout.flush()
    return cmd, proc


def parse_routes(routefile):
    result = {}
    for vehicle in sumolib.output.parse(routefile, "vehicle"):
        result[vehicle.id] = (vehicle.route[0], vehicle.type)
    print('parsed %s routes from %s' % (len(result), routefile))
    return result


def sorted_trip_sequence(tripfile):
    # sort by daytrip start
    persons = []
    for pid, trip_sequence in csv_sequence_generator(tripfile, TH.person_id):
        first_row = trip_sequence[0]
        depart = int(first_row[TH.depart_minute])
        persons.append((depart, pid, trip_sequence))
    persons.sort()  # sorts by first tuple member
    return [p[1:] for p in persons]


###############################################################################
# build personfile using previously routed trips
@benchmark
def create_personfile(mapped_trips, input_routes, output_routes):
    persons = 0
    trips = 0
    sim_start = uMax
    # only a guess since we don't know how long a trip really takes
    sim_end = 0
    sim_end_blame = None  # which person takes the longest (guess)

    routes = parse_routes(input_routes)

    with open(output_routes, 'w') as personfile:
        personfile.write("<!-- generated from %s -->\n" % mapped_trips)
        personfile.write(
            '<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n')

        routes_xml_lines = []

        for pid, trip_sequence in sorted_trip_sequence(mapped_trips):
            persons += 1
            first_row = trip_sequence[0]
            depart = int(first_row[THX.depart_second])
            sim_start = min(sim_start, depart)
            arrival_guess = depart
            previous_dest_edge = None
            previous_arrival = None  # time in seconds as guessed by TAPAS

            person_lines = ['    <person id="%s" depart="%s">' %
                            (pid[0], depart)]
            vehicle_lines = []

            for row in trip_sequence:
                trips += 1
                mode = row[TH.mode]
                uid = build_uid(row)
                source_edge = row[THX.source_edge]
                dest_edge = row[THX.dest_edge]
                arrival_guess += float(row[TH.duration])

                # check for gaps (paranoia since rectify should have handled
                # this)
                if previous_dest_edge and previous_dest_edge != source_edge:
                    print('Error: gap in edge sequence at trip %s' % uid)
                    continue

                # before every trip we may need to stop to honour that trips
                # depart time. For the initial trip this is done automatically
                # by SUMO (according to depart attribute)
                if previous_arrival:  # not the initial trip
                    # patch inconsistent time
                    #                    stopping_time = max(0, float(row[THX.depart_second]) - previous_arrival)
                    # use fixed activity duration (maybe max with next depart
                    # would also be nice?)
                    stopping_time = float(row[TH.activity_duration_minutes]) * 60
                    # fixed starting time
                    # person_lines.append('        <stop until="%s" lane="%s_0"/>'
                    #       % (row[THX.depart_second], source_edge))

                    # fixed duration
                    person_lines.append('        <walk from="%s" to="%s"/>' % (redges[-1], source_edge))
                    person_lines.append('        <stop duration="%s" lane="%s_0" endPos="%s" friendlyPos="true"/>'
                                        % (stopping_time, source_edge, previous_arrival_pos))

                previous_dest_edge = dest_edge
                previous_arrival = float(row[THX.depart_second]) + float(row[TH.duration])
                previous_arrival_pos = row[THX.arrivalpos]

                if mode in CAR_MODES:
                    route, vtype = routes[uid]
                    redges = route.edges.split()
                    person_lines.append('        <walk from="%s" to="%s"/>' % (source_edge, redges[0]))
                    person_lines.append('        <ride from="%s" to="%s" lines="%s"/>' % (redges[0], redges[-1], uid))

                    vehicle_lines.append('    <vehicle id="%s" depart="triggered" type="%s" departPos="%s" arrivalPos="%s">' %
                                         (uid, vtype, row[THX.departpos], row[THX.arrivalpos]))
                    vehicle_lines.append('        %s' % route.toXML())
                    vehicle_lines.append('    </vehicle>\n')

            person_lines.append('    </person>\n')

            routed_item = '\n'.join(
                person_lines) + '\n'.join(vehicle_lines) + '\n'
            routes_xml_lines.append((depart, routed_item))

            if arrival_guess > sim_end:
                sim_end = arrival_guess
                sim_end_blame = pid

        for ll in sorted(routes_xml_lines):
            personfile.write(ll[1])

        personfile.write("</routes>\n")

        print('imported %d TAPAS persons' % persons)
        print('imported %d TAPAS trips temporarily stored in %s' %
              (trips, input_routes))

        sim_start = math.floor(sim_start)
        print('Simulation start: %s' % sim_start)
        print('Simulation end guessed from TAPAS durations: %s (blame person %s)' % (
            sim_end, sim_end_blame))
        return sim_start, sim_end

###############################################################################


def run_pedestrian_sumo(options, routefile):
    personfile = abspath_in_dir(options.iteration_dir, 'persons.xml')
    sumocfg = abspath_in_dir(options.iteration_dir, 'persons.sumocfg')
    sim_start, sim_end = create_personfile(options.mapped_trips, routefile, personfile)
    with open(sumocfg, 'w') as f:
        f.write(
            #<no-duration-log value="true"/>
            """<configuration>
        <net-file value="%s"/>
        <route-files value="%s"/>
        <additional-files value="%s"/>

        <tripinfo-output value="person_tripinfo.xml"/>

        <no-step-log value="true"/>
        <log-file value="persons.sumo.log"/>

        <begin value="%s"/>
        <end value="%s"/>

        <phemlight-path value="%s"/>
</configuration>""" % (options.net_file, personfile,
                       options.vtype_file, sim_start, sim_end + TAPAS_EXTRA_TIME,
                       options.phemlight_path)
        )
    return call([sumolib.checkBinary("sumo"), "-c", sumocfg])

###############################################################################

def run_trajectory_sumo(options, net_file, route_file):
    sumocfg = abspath_in_dir(options.iteration_dir, 'trajectories.sumocfg')
    with open(sumocfg, 'w') as f:
        f.write(
            """<configuration>
        <net-file value="%s"/>
        <route-files value="%s"/>
        <additional-files value="%s"/>

        <fcd-output value="trajectories.xml"/>

        <no-step-log value="true"/>
        <log-file value="trajectories.sumo.log"/>
        <phemlight-path value="%s"/>
</configuration>""" % (net_file, route_file, options.vtype_file, options.phemlight_path)
        )
    return call([sumolib.checkBinary("sumo"), "-c", sumocfg])

###############################################################################

def run_emission_sumo(options, params, conn, routefile, emission_model="HBEFA3", meso=True):
    if conn is None:
        return None
    car_types = emissions.get_car_types(params, conn, emission_model)
    vtype, vtypes_file = emissions.modify_vtypes(options, car_types)
    mod_routes_file = abspath_in_dir(options.iteration_dir, 'emission_routes.xml')
    with open(mod_routes_file, 'w') as f:
        f.write('<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n')
        for vehicle in sumolib.output.parse(routefile, "vehicle"):
            if vehicle.id in vtype: # this will skip the clones
                vehicle.type = vtype[vehicle.id]
                f.write(vehicle.toXML("    "))
        f.write('</routes>\n')

    sumocfg = abspath_in_dir(options.iteration_dir, 'emissions.sumocfg')
    with open(sumocfg, 'w') as f:
        f.write(
            """<configuration>
        <net-file value="%s"/>
        <route-files value="%s"/>
        <additional-files value="%s"/>

        <no-step-log value="true"/>
        <log-file value="emissions.sumo.log"/>

        <mesosim value="%s"/>
        <meso-recheck value="10"/>
        <meso-multi-queue value="true"/>
        <meso-junction-control.limited value="true"/>
</configuration>""" % ( options.net_file, mod_routes_file,
                        vtypes_file, meso
                        )
        )
    return call([sumolib.checkBinary("sumo"), "-c", sumocfg])


if __name__ == "__main__":
    argParser = sumolib.options.ArgumentParser()
    db_manipulator.add_db_arguments(argParser)
    argParser.add_argument("routes")
    options = argParser.parse_args()
    options.iteration_dir = "."
    conn = db_manipulator.get_conn(options)
    run_emission_sumo(options, SP.OPTIONAL, conn, options.routes)
    conn.close()
