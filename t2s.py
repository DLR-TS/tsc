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

# @file    t2s.py
# @author  Jakob Erdmann
# @author  Michael Behrisch
# @date    2013-12-15

# convert tapas trips to sumo vehicle trips

from __future__ import print_function, division
import os
import sys
import math
import csv
import random
import shutil
import subprocess
import collections
import glob

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path += [tools, os.path.join(tools, 'assign')]
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

import sumolib
from sumolib.miscutils import working_dir, benchmark, uMin, uMax, euclidean
from sumolib.options import ArgumentParser

import assign
from constants import TH, THX, SX, SVC, MODE, CAR_MODES, TAPAS_DAY_OVERLAP_MINUTES, BACKGROUND_TRAFFIC_SUFFIX
from edgemapper import EdgeMapper
from common import csv_sequence_generator, abspath_in_dir, build_uid

class MappingError(Exception):
    pass


def fillOptions(argParser):
    argParser.add_argument("--net-file", help="specifying the net file of the scenario to use")
    argParser.add_argument("--vtype-file", help="specifying the vehicle type file of the scenario to use")
    argParser.add_argument("--taz-file", help="specifying the district file of the scenario to use")
    argParser.add_argument("--iteration-dir",
                           help="directory holding all files and directories of this SUMO-Tapas iteration")
    argParser.add_argument("--trips-dir", help="directory holding all trip output files")
    argParser.add_argument("--tapas-trips", help="trip file with information received from tapas (csv)")
    argParser.add_argument("-R", "--no-rectify", action="store_false", dest="rectify", default=True,
                           help="skip rectifying trips")
    argParser.add_argument("--rectify-only", action="store_true", dest="rectify_only", default=False,
                           help="skip everything, just rectify the trips ")
    argParser.add_argument("-M", "--no-map", action="store_false", dest="domap", default=True,
                           help="skip mapping trips")
    argParser.add_argument("-T", "--no-tripdefs", action="store_false", dest="dotripdefs", default=True,
                           help="skip generating trips")
    argParser.add_argument("--map-and-exit", action="store_true", dest="map_and_exit", default=False,
                           help="skip everything after having mapped the trips ")
    argParser.add_argument("--ignore-gaps", action="store_true", dest="ignore_gaps", default=False,
                           help="keep trips after a geographic gap in the trip sequence")
    argParser.add_argument("--max-radius", type=float, default=2000.,
                           help="maximum radius when mapping trips")
    argParser.add_argument("--weights", help="weight file for routing")
    argParser.add_argument("-s", "--scale", type=float, default=1.0, help="scale value")
    argParser.add_argument("--routing-algorithm", default='CHWrapper',
                           help="algorithm to use when calling DUAROUTER")
    argParser.add_argument("-l", "--last-step", type=int, dest="last_step", default=50,
                           help="number of duaiterate iterations")
    argParser.add_argument("-A", "--assignment",
                           choices=("oneshot", "gawron", "oneshot+gawron", "marouter", "marouter+gawron", "marouter+oneshot", "bulk"),
                           default="oneshot", help="run with the given assignment algorithm")
    argParser.add_argument("--seed", type=int, default=23432, help="random seed")
    argParser.add_argument("--time-diffusion", type=int, default=900, help="time diffusion window")
    argParser.add_argument("--spatial-diffusion", type=float, default=50.,
                           help="(minimum) standard deviation for spatial diffusion")
    argParser.add_argument("--max-spatial-diffusion", type=float,
                           default=100., help="maximum standard deviation for spatial diffusion when using bounds")
    argParser.add_argument("--spatial-diffusion-bounds", default="500,5000",
                           help="lower and upper cutoff for spatial diffusion")
    argParser.add_argument("--generate-taz-file",
                           help="build a district file based on proximity to the trip locations")
    argParser.add_argument("--bidi-taz-file", default="",
                           help="generate trips that use the given taz file for bidirectional departure and arrival")
    argParser.add_argument("--location-priority-file", default="",
                           help="map given locations to edges of the given priority (or better)")
    argParser.add_argument("--default-vtype",
                           help="default vehicle type if none is given in the input")
    argParser.add_argument("--bike-type", default="ped_bike", help="treat bicycles as pedestrians with the given type")
    argParser.add_argument("--shift-departure-hours", type=int, default=24, dest="shiftdeparthours",
                           help="shift departure times by the given number of hours (to handle trips that depart before midnight)")
    argParser.add_argument("-m", "--modes", default=','.join(CAR_MODES),
                           help="the traffic modes to retrieve as a list of integers (default '%default')")
    argParser.add_argument('--phemlight-path', metavar="PATH", default=os.path.join(os.environ.get("TSC_DATA", os.path.dirname(os.path.dirname(__file__))), "PHEMlight"),
                           help="Determines where to load PHEMlight \ndefinitions from.")
    argParser.add_argument("--subnet-file", help="specifying the subnet to use to rerun a subnet assignment")


def getSumoTripfileName(trips_dir, tapas_trips):
    base = os.path.basename(tapas_trips)[:-4]
    return abspath_in_dir(trips_dir, 'miv_%s.trips.xml' % base)


def checkOptions(options):
    if not hasattr(options, "net"):
        assert options.net_file is not None, "scenario net file is not given"
        options.net_file = os.path.abspath(options.net_file)
        assert os.path.isfile(options.net_file), "the given net file %s does not exist" % (options.net_file)
        if options.subnet_file is None:
            if options.domap or options.rectify:
                options.net = sumolib.net.readNet(options.net_file, withFoes=False, withConnections=False)

    if options.vtype_file is None:
        options.vtype_file = abspath_in_dir(
            os.path.dirname(options.net_file), "vtypes.xml")
    else:
        options.vtype_file = os.path.abspath(options.vtype_file)
    if options.taz_file is None:
        options.taz_file = abspath_in_dir(
            os.path.dirname(options.net_file), "districts.taz.xml")
    else:
        options.taz_file = os.path.abspath(options.taz_file)
    if options.bidi_taz_file:
        options.bidi_taz_file = os.path.abspath(options.bidi_taz_file)

    if options.subnet_file is None:
        assert options.tapas_trips is not None, "tripfile is not given"
        options.tapas_trips = os.path.abspath(options.tapas_trips)
        assert os.path.isfile(options.tapas_trips), "the given tripfile %s does not exist" % (options.tapas_trips)
        base = os.path.basename(options.tapas_trips)[:-4]
        if options.trips_dir is None:
            assert options.iteration_dir is not None, "iteration or trips directory need to be given"
            assert os.path.isdir(options.iteration_dir), "the given iteration directory %s is not accessible" % options.iteration_dir
            options.trips_dir = os.path.join(options.iteration_dir, 'trips')
        options.rectified = abspath_in_dir(options.trips_dir, 'rectified_%s.csv' % base)
        options.rectified_log = abspath_in_dir(options.trips_dir, 't2s_rectify_%s.log' % base)

        options.mapped_trips = abspath_in_dir(options.trips_dir, 'mapped_%s.csv' % base)
        options.mapped_log = abspath_in_dir(options.trips_dir, 't2s_map_%s.log' % base)
        options.trips_for_dua = getSumoTripfileName(options.trips_dir, options.tapas_trips)
    else:
        assert options.iteration_dir is not None, "iteration directory needs to be given"
        assert os.path.isdir(options.iteration_dir), "the given iteration directory %s is not accessible" % options.iteration_dir

    if not hasattr(options, "script_module"):
        options.script_module = None

    if not hasattr(options, "background_trips"):
        options.background_trips = ""

    if options.max_spatial_diffusion > 0:
        assert options.spatial_diffusion > 0, "initial standard deviation needed for spatial diffusion"
        if type(options.spatial_diffusion_bounds) is str:
            options.spatial_diffusion_bounds = [int(e) for e in options.spatial_diffusion_bounds.split(",")]

def get_logger(file):
    def log(msg):
        print(msg)
        print(msg, file=file)
    return log


###############################################################################
@benchmark
def rectify_input(options):
    # convert depart-time to seconds
    #   add random seconds from [-options.diffuse/2, options.diffuse/2] to reduce traffic bursts
    #   (right now the most important trip for each person is aligned to 5min slot
    #    and some of these slots are very crowded)
    # gaps
    # NaN
    # ordering assumptions
    #   every "person" appears only once. A person is defined by (person_id, household_id)
    #   trips for each person are sorted by departure
    # report overlapping times
    # filter trips wich start on the next day
    # filter trips by mode (optional)
    # diffuse geoCoordinates with a gausian (mu = 0, sigma = spatialDiffuse meters)
    # since tapas inputs tends to show strong spatial clustering (call it
    # parking related diffusion)
    diffusion_map = {}
    modes = options.modes.split(",")
    if options.max_spatial_diffusion > 0:
        loc_count = collections.defaultdict(int)
        for row in csv.DictReader(open(options.tapas_trips)):
            if row[TH.mode] in modes:
                loc_count[(row[TH.source_long], row[TH.source_lat])] += 1
                loc_count[(row[TH.dest_long], row[TH.dest_lat])] += 1
        for coord, count in loc_count.items():
            if count >= options.spatial_diffusion_bounds[0]:
                scale = float(count - options.spatial_diffusion_bounds[0]) / (options.spatial_diffusion_bounds[1] - options.spatial_diffusion_bounds[0])
                diffusion = scale * (options.max_spatial_diffusion - options.spatial_diffusion) + options.spatial_diffusion
                if diffusion < options.max_spatial_diffusion:
                    diffusion_map[coord] = diffusion
    if os.path.exists(options.location_priority_file):
        for loc in sumolib.xml.parse(options.location_priority_file, "poi"):
            diffusion_map[(loc.lon, loc.lat)] = 0
    with open(options.rectified_log, 'w') as logfile:
        log = get_logger(logfile)
        writer = csv.DictWriter(
            open(options.rectified, 'w'),
            THX.fieldnames,
            extrasaction='ignore', lineterminator='\n')
        writer.writeheader()

        persons = 0
        rows = 0
        gaps = 0
        gap_sum = 0
        max_gap = 0
        max_gap_uid = None
        max_depart = 0
        max_depart_uid = None
        inconsistent = 0
        skipped_wrong_mode = 0
        skipped_wrong_depart = 0

        # asserts that each person appears only in one consecutive sequence of
        # # entries
        gen = csv_sequence_generator(
            options.tapas_trips, (TH.person_id, TH.household_id), assertUniqe=True)
        for (pid, hid), trip_sequence in gen:
            persons += 1
            previous_row = None
            previous_dest = None
            previous_end = None
            previous_depart = None
            spatial_offset = None
            # smooth bursts due to low resolution
            smoothing_offset = int(random.random() * (options.time_diffusion+1)) - options.time_diffusion // 2
            for row in trip_sequence:
                rows += 1
                uid = build_uid(row)
                source_coord = (row[TH.source_long], row[TH.source_lat])
                source = options.net.convertLonLat2XY(*source_coord)
                if spatial_offset is None:
                    if source_coord in diffusion_map:
                        spatial_offset = [random.gauss(0, diffusion_map[source_coord]) for i in range(2)]
                    elif options.max_spatial_diffusion <= 0 and options.spatial_diffusion > 0:
                        spatial_offset = [random.gauss(0, options.spatial_diffusion) for i in range(2)]
                dest_coord = (row[TH.dest_long], row[TH.dest_lat])
                dest = options.net.convertLonLat2XY(*dest_coord)
                depart_minute = int(row[TH.depart_minute])
                depart = depart_minute * 60 + smoothing_offset
                duration = float(row[TH.duration])
                activity_duration = int(row[TH.activity_duration_minutes]) * 60

                if depart_minute - 24 * 60 >= TAPAS_DAY_OVERLAP_MINUTES or depart_minute <= -TAPAS_DAY_OVERLAP_MINUTES:
                    log("Warning: dropping trip %s because it starts on the wrong day (minute %s)" % (
                        uid, depart_minute))
                    skipped_wrong_depart += 1
                    if depart_minute > max_depart:
                        max_depart = depart_minute
                        max_depart_uid = uid
                    continue

                row[THX.depart_second] = depart
                if math.isnan(duration):
                    log('Warning: NaN value in duration of trip %s' % uid)
                    duration = 1
                    row[TH.duration] = duration

                if previous_end is not None and depart < previous_end:
                    if (previous_end - depart >= 60):
                        # input data only has minute resolution anyway and may
                        # suffer from rounding
                        inconsistent += 1
                        log("Warning: inconsistent depart time for trip %s (%s seconds)" %
                            (uid, previous_end - depart))
                    depart = previous_end

                previous_end = int(depart + duration + activity_duration)

                if previous_depart is not None and depart < previous_depart:
                    raise MappingError(
                        'Unordered trips for person %s at departure %s' % (pid, depart_minute))
                previous_depart = depart

                # close gaps in trip sequence
                if previous_dest and previous_dest != source and not options.ignore_gaps:
                    gaps += 1
                    gap = euclidean(previous_dest, source)
                    gap_sum += gap
                    max_gap = max(max_gap, gap)
                    max_gap_uid = uid
                    # to many to list them all
                    # print('Warning: gap in edge sequence at trip %s (length %s)' % (uid, gap))
                    # XXX add teleport-trip for closing the gap
                    # row[TH.source_long] = previous_row[TH.dest_long]
                    # row[TH.source_lat] = previous_row[TH.dest_lat]
                    continue
                previous_row = row
                previous_dest = dest

                if spatial_offset is not None:
                    row[TH.source_long], row[TH.source_lat] = options.net.convertXY2LonLat(
                        source[0] + spatial_offset[0], source[1] + spatial_offset[1])
                    if dest_coord in diffusion_map:
                        spatial_offset = [random.gauss(0, diffusion_map[dest_coord]) for i in range(2)]
                    else:
                        spatial_offset = [random.gauss(0, options.spatial_diffusion) for i in range(2)]
                    row[TH.dest_long], row[TH.dest_lat] = options.net.convertXY2LonLat(
                        dest[0] + spatial_offset[0], dest[1] + spatial_offset[1])

                if row[TH.mode] in modes:
                    writer.writerow(row)
                else:
                    skipped_wrong_mode += 1

        log('Read %s persons with a total of %s trips from input file "%s".' %
            (persons, rows, options.tapas_trips))
        if skipped_wrong_mode > 0:
            log('Dropped %s trips because they have the wrong mode' %
                skipped_wrong_mode)
        log('%s trips have inconsistent depart times.' % inconsistent)
        if gaps > 0:
            log('Dropped %s trips because of gaps, avg: %s, maximum: %s (for trip %s).' %
                (gaps, gap_sum / gaps, max_gap, max_gap_uid))
        if skipped_wrong_depart > 0:
            log('Dropped %d trips because they start on the wrong day (maximum: %s for trip %s).' %
                (skipped_wrong_depart, max_depart, max_depart_uid))


###############################################################################
# map geocoordinates to network edges
@benchmark
def map_to_edges(options):
    location_prios = {}
    if os.path.exists(options.location_priority_file):
        for loc in sumolib.xml.parse(options.location_priority_file, "poi"):
            xy = options.net.convertLonLat2XY(round(float(loc.lon), 5), round(float(loc.lat), 5))
            location_prios[xy] = int(loc.type)
    emapper = EdgeMapper(options.net, options.taz_file, options.generate_taz_file, location_prios)

    vTypes = {}
    if os.path.exists(options.vtype_file):
        for t in sumolib.output.parse(options.vtype_file, "vType"):
            if t.vClass is not None:
                vTypes[t.id] = t.vClass

    writer = csv.DictWriter(
        open(options.mapped_trips, 'w'),
        THX.fieldnames,
        extrasaction='ignore')
    writer.writeheader()

    persons = 0
    rows = 0
    unmapped = 0

    with open(options.mapped_log, 'w') as logfile:
        log = get_logger(logfile)
        for (pid, hid), trip_sequence in csv_sequence_generator(options.rectified, (TH.person_id, TH.household_id)):
            persons += 1
            for row in trip_sequence:
                if row[TH.mode] in CAR_MODES:
                    vClass = vTypes.get(row[TH.vtype], SVC.passenger)
                else:
                    vClass = SVC.pedestrian
                rows += 1
                taz_id_start = row[TH.taz_id_start]
                taz_id_end = row[TH.taz_id_end]
                source = options.net.convertLonLat2XY(
                    round(float(row[TH.source_long]), 5), round(float(row[TH.source_lat]), 5))
                dest = options.net.convertLonLat2XY(
                    round(float(row[TH.dest_long]), 5), round(float(row[TH.dest_lat]), 5))
                if taz_id_start.startswith("-") and source not in location_prios:
                    source_edge = taz_id_start[1:]
                else:
                    source_edge = emapper.map_to_edge(
                        source, taz_id_start, vClass,
                        max_radius=options.max_radius, uid=(pid, hid), log=log)
                if taz_id_end.startswith("-") and dest not in location_prios:
                    dest_edge = taz_id_end[1:]
                else:
                    dest_edge = emapper.map_to_edge(
                        dest, taz_id_end, vClass,
                        max_radius=options.max_radius, uid=(pid, hid), log=log)
                if source_edge is None:
                    unmapped += 1
                    if unmapped < 10:
                        log('Warning: could not find an edge for departure of %s from (%s, %s), depart_minute=%s (skipping trip)' % (
                            (pid, hid), row[TH.source_lat], row[TH.source_long], row[TH.depart_minute]))
                elif dest_edge is None:
                    unmapped += 1
                    if unmapped < 10:
                        log('Warning: could not find an edge for arrival of %s at (%s, %s), depart_minute=%s (skipping trip)' % (
                            (pid, hid), row[TH.dest_lat], row[TH.dest_long], row[TH.depart_minute]))
                else:
                    row[THX.source_edge] = source_edge
                    row[THX.dest_edge] = dest_edge
                    row[THX.departpos] = 0
                    row[THX.arrivalpos] = 0
                    writer.writerow(row)

        log('read %d TAPAS trips for %s persons (%s unmappable)' % (
            rows, persons, unmapped))
        if rows == unmapped and unmapped > 0:
            raise MappingError('No trips left after mapping.')
        log(emapper.errors)  # error when mapping to junction coords
        log("%s mappings did not find an edge in the correct taz" % emapper.noTazEdge)

        if options.generate_taz_file is not None:
            with open(options.generate_taz_file, 'w') as f:
                f.write('<tazs>\n')
                for taz, edges in emapper.taz.items():
                    f.write('    <taz id="%s" edges="%s"/>\n' % (taz, ' '.join(edges)))
                f.write('</tazs>\n')
            log("generated taz file with %s zones" % len(emapper.taz))


###############################################################################
# create trips as input for duarouter or sumo (route car and taxi trips)
@benchmark
def create_sumo_tripdefs(options, scale, suffix, vtype_map):
    trip_lines = []
    trips_read = 0
    for row in csv.DictReader(open(options.mapped_trips)):
        mode = row[TH.mode]
        trips_read += 1
        num_clones = 0
        if scale > 1.:
            num_clones = int(scale - 1)
            # do randomized rounding
            if random.random() < scale - int(scale):
                num_clones += 1
        elif random.random() > scale:
            continue
        param = ""
        if row[TH.taz_id_start]:
            param += '<param key="taz_id_start" value="%s"/>' % row[TH.taz_id_start]
        if row[TH.taz_id_end]:
            param += '<param key="taz_id_end" value="%s"/>' % row[TH.taz_id_end]
        if not options.bidi_taz_file:
            fro = ' from="%s"' % row[THX.source_edge]
            to = ' to="%s"' % row[THX.dest_edge]
        else:
            fro = ' fromTaz="%s"' % row[THX.source_edge]
            to = ' toTaz="%s"' % row[THX.dest_edge]

        vtype = row[TH.vtype]
        if vtype == '' and options.default_vtype is not None:
            vtype = options.default_vtype
        vtype = vtype_map.get(build_uid(row), vtype)
        depart = int(row[THX.depart_second]) + options.shiftdeparthours * 3600
        person_type = ""
        usable_modes = []
        if mode in (MODE.bicycle, MODE.bicycle_public):
            if options.bike_type:
                person_type = ' type="%s"' % options.bike_type
            else:
                usable_modes.append("bicycle")
        if mode in (MODE.car, MODE.car_public):
            usable_modes.append("car")
        if mode in (MODE.public, MODE.car_public, MODE.bicycle_public):
            usable_modes.append("public")
        if mode in (MODE.sharing):
            usable_modes.append("taxi")
        mode_string = (' modes="%s"' % " ".join(usable_modes)) if usable_modes else ""
        if mode in CAR_MODES:
            entry = '    <trip id="%s" depart="%s"%s%s type="%s">%s</trip>\n' % (
                build_uid(row, suffix), depart, fro, to, vtype, param)
        else:
            entry = '    <person id="%s" depart="%s"%s><personTrip %s%s%s/>%s</person>\n' % (
                build_uid(row, suffix), depart, person_type, fro, to, mode_string, param)
        trip_lines.append((int(depart), entry))
        for idx in range(num_clones):
            # smooth bursts due to low resolution
            smoothing_offset = int(random.random() * (options.time_diffusion+1)) - options.time_diffusion // 2
            depart = int(row[TH.depart_minute]) * 60 + smoothing_offset + 24 * 3600
            if mode in CAR_MODES:
                entry = '    <trip id="%s" depart="%s"%s%s type="%s">%s</trip>\n' % (
                    build_uid(row, idx + 1), depart, fro, to, vtype, param)
            else:
                entry = '    <person id="%s" depart="%s"><personTrip %s%s%s/>%s</person>\n' % (
                    build_uid(row, idx + 1), depart, fro, to, mode_string, param)
            trip_lines.append((int(depart), entry))

    # we sort the tripdefs by departure. this way the output can be used as a reference
    # simulation input
    trip_lines.sort()
    if len(trip_lines)>0:
        first_depart = trip_lines[0][0]
        last_depart = trip_lines[-1][0]
    else:
        first_depart = 0
        last_depart = 0

    with open(options.trips_for_dua, 'w') as tripfile_passenger:
        tripfile_passenger.write(
            '<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n')

        for depart, line in trip_lines:
            tripfile_passenger.write(line)
        tripfile_passenger.write("</routes>\n")

    print('read trip definitions for %s vehicles' % trips_read)
    print('created trip definitions for %s vehicles starting between %s and %s' %
          (len(trip_lines), first_depart, last_depart))
    return first_depart, last_depart


@benchmark
def main(options):
    checkOptions(options)
    random.seed(options.seed)  # make runs reproducible

    if options.subnet_file:
        assign.run_subnet(options, 24*3600, 48*3600, glob.glob(os.path.join(options.iteration_dir, "oneshot", "*meso.rou.xml"))[0],
                          glob.glob(os.path.join(options.iteration_dir, "oneshot", "aggregated*.xml"))[0], options.subnet_file)
        return

    if options.rectify:
        rectify_input(options)
        if options.rectify_only:
            return
    else:
        if os.path.isfile(options.rectified):
            print("using previous version of %s" % options.rectified)
        else:
            print("using %s as rectified input" % options.tapas_trips)
            shutil.copyfile(options.tapas_trips, options.rectified)

    if options.domap:
        map_to_edges(options)
        if options.map_and_exit:
            return
    else:
        if os.path.isfile(options.mapped_trips):
            print("using previous version of %s" % options.mapped_trips)
        else:
            if options.iteration_dir is not None:
                print("Cannot continue with assignment because %s is missing" %
                        options.mapped_trips)
                return

    # IV-Routing
    first_depart = uMax
    last_depart = uMin
    if options.dotripdefs:
        suffix = BACKGROUND_TRAFFIC_SUFFIX if options.iteration_dir is None else "0"
        first_depart, last_depart = create_sumo_tripdefs(options, options.scale, suffix, {})
    else:
        if os.path.isfile(options.trips_for_dua):
            for trip in sumolib.output.parse_fast(options.trips_for_dua, 'trip', ['depart']):
                first_depart = min(first_depart, float(trip.depart))
                last_depart = max(last_depart, float(trip.depart))
            print("using previous version of %s, vehicles starting between %s and %s" % (
                options.trips_for_dua, first_depart, last_depart))

        else:
            print("Cannot continue with assignment because %s is missing" %
                    options.trips_for_dua)
            return

    if options.iteration_dir is None:
        print("No iteration dir given, skipping assignment")
        return options.trips_for_dua, None
    if options.assignment == "bulk":
        return assign.run_bulk(options, first_depart, last_depart, options.trips_for_dua, options.weights)
    if options.script_module is None:
        return assign.run_default(options, first_depart, last_depart, options.trips_for_dua, options.weights)
    return options.script_module.assign_trips(options, first_depart, last_depart, options.trips_for_dua, options.weights)


if __name__ == "__main__":
    argParser = ArgumentParser()
    fillOptions(argParser)
    options = argParser.parse_args(args=sys.argv[1:])
    main(options)
