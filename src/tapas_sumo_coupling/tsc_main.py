#!/usr/bin/env python

# Copyright (C) 2014-2022 German Aerospace Center (DLR) and others.
# This program and the accompanying materials are made available under the
# terms of the Eclipse Public License 2.0 which is available at
# https://www.eclipse.org/legal/epl-2.0/
# This Source Code may also be made available under the following Secondary
# Licenses when the conditions for such availability set forth in the Eclipse
# Public License 2.0 are satisfied: GNU General Public License, version 2
# or later which is available at
# https://www.gnu.org/licenses/old-licenses/gpl-2.0-standalone.html
# SPDX-License-Identifier: EPL-2.0 OR GPL-2.0-or-later

# @file    tsc_main.py
# @author  Marek Heinrich
# @author  Michael Behrisch
# @date    2014-12-15

# This script runs permanently in the background and triggers sumo runs (t2s, s2t)

# The following things must be done before this script can run:
#  - python install_scenario_templates.py 

# for legacy operation call:
#     python tsc_main.py --server achilles
#      --sim-key 2014y_08m_18d_15h_12m_21s_540ms --iteration 0

from __future__ import print_function, division
import os
import sys
import shutil
import glob
import json
import datetime
import time
import multiprocessing
import subprocess
import importlib
from psycopg2 import ProgrammingError

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path += [tools, os.path.join(tools, 'assign')]
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

import sumolib
from sumolib.options import ArgumentParser

from tapas_sumo_coupling import common, constants, database, get_motorway_access, get_trips, t2s, s2t_miv, s2t_pt
from tapas_sumo_coupling.constants import SP, CAR_MODES, MODE

DEFAULT_SIMKEY = "berlin_2010"

def getOptions(args, argParser):
    t2s.fillOptions(argParser)
    database.add_db_arguments(argParser)
    argParser.add_argument("--workdir-folder", default='scenario_workdir',
                           help="specifying the workdir directory of the scenarios to use")
    argParser.add_argument("--template-folder", default='scenario_templates',
                           help="specifying the template directory of the scenarios to use")
    argParser.add_argument("-t", "--fake-tripfile",
                           help="use this trip file as input instead of database (use only for debug and testing)")
    argParser.add_argument("--limit", type=int, help="maximum number of trips to retrieve")
    argParser.add_argument("--parallel", type=int, default=1,
                           help="maximum number of parallel simulations to run")
    argParser.add_argument("--clean", action="store_true", default=False,
                           help="cleanup working dir and status table and exit")
    argParser.add_argument("--daemon", action="store_true", default=False, help="run as daemon")
    argParser.add_argument("--daemon-run-time", type=int, default=-1,
                           help="limit the up time of the daemon in seconds - e.g. for debugging ")
    argParser.add_argument('--iteration', help="iterations of faked simulation requests (ranges and ints are possible)")
    argParser.add_argument('--log', default="tsc.log", help="name of the overall log file")
    argParser.add_argument("--sim-key", help="sim_key to use when running only a single simulation")
    argParser.add_argument("--sim-param", default="",
                           help="additional parameters for simulation requests (overwrite database values)")
    argParser.add_argument('--net-param', default="{}",
                           help="network restrictions of simulation requests (do not use in daemon mode).")
    argParser.add_argument("--vtype-matrix", action="store_true", default=False,
                           help="save OD matrix disaggregated by vehicle type instead of class")

    options = argParser.parse_args(args=args)
    if not options.fake_tripfile and not options.host:
        sys.exit("You need either a database connection or a fake tripfile!")
    options.limit = " LIMIT %s" % options.limit if options.limit else ""
    return options


def get_simulation_requests(options):
    overrides = dict([item.split(":") for item in options.sim_param.split(",") if item])
    if options.modes is not None:
        overrides["SUMO_MODES"] = options.modes
    if options.fake_tripfile or options.sim_key:
        if options.sim_key is None:
            options.sim_key = DEFAULT_SIMKEY
            initial_sim_params = dict(SP.OPTIONAL)
        else:
            conn = database.get_conn(options)
            initial_sim_params = get_trips.get_sim_params(conn, options.sim_key, overrides)
            conn.close()
            if initial_sim_params is None:
                print("Warning! No simulation parameters for sim key", options.sim_key)
                return []
        if options.iteration is None:
            destination_path = os.path.join(options.workdir_folder,
                                            overrides.get(SP.destination, SP.OPTIONAL[SP.destination]))
            if os.path.isdir(destination_path):
                files_folders = common.listdir_skip_hidden(destination_path)
                existing_iterations = [int(ff[9:]) for ff in files_folders if ff[:9] == 'iteration']
                iterations = [max([-1] + existing_iterations) + 1]
            else:
                iterations = [0]
        else:
            if ":" in options.iteration:
                its = options.iteration.split(":")
                iterations = range(int(its[0]), int(its[1]))
            else:
                iterations = [int(options.iteration)]
        simulation_request_list = []
        for i in iterations:
            sim_params = dict(initial_sim_params)
            sim_params.update({SP.net_param: options.net_param,
                               SP.iteration: str(i),
                               SP.max_iteration: str(max(iterations)+1)})
            sim_params.update(overrides)
            simulation_request_list.append((options.sim_key, i, sim_params))
        return simulation_request_list
    return get_trips.get_active_sim_keys(options, overrides)


def build_restricted_network(restrictions, destination_path, netfile):
    typefile = os.path.join(destination_path, "restrictions.typ.xml")
    with open(typefile, 'w') as types:
        types.write("""<?xml version="1.0" encoding="UTF-8"?>
<types xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/types_file.xsd">
""")
        for list_file, res in restrictions.items():
            if "allowed" in res:
                allowed = ' allow="%s"' % (" ".join(res["allowed"]))
            types.write('    <type id="%s"%s>\n' % (list_file, allowed))
            for vClass, speed in res.get("maxSpeed", {}).items():
                types.write(
                    '        <restriction vClass="%s" speed="%s"/>\n' % (vClass, speed))
            types.write('    </type>\n')
        types.write('</types>\n')

    edgefile = os.path.join(destination_path, "restricted_edges.edg.xml")
    with open(edgefile, 'w') as edges:
        edges.write("""<?xml version="1.0" encoding="UTF-8"?>
<edges xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/edgediff_file.xsd">
""")
        for list_file in restrictions.keys():
            if ".taz.xml" in list_file:
                f, tazId = list_file.split("@")
                for taz in sumolib.output.parse_fast(os.path.join(os.path.dirname(netfile), f), 'taz', ['id', 'edges']):
                    if taz.id == tazId:
                        for edge in taz.edges.split():
                            edges.write('    <edge id="%s" type="%s"/>\n' %
                                        (edge, list_file))
            else:
                for line in open(os.path.join(os.path.dirname(netfile), list_file)):
                    line = line.strip()
                    if line.startswith("edge:"):
                        line = line[5:]
                    if line.startswith("lane:"):
                        line = line[5:-2]
                    edges.write('    <edge id="%s" type="%s"/>\n' %
                                (line, list_file))
        edges.write('</edges>\n')

    subprocess.call([sumolib.checkBinary("netconvert"), "-s", netfile, "-t", types.name, "--aggregate-warnings", "1",
                     "-e", edges.name, "-o", os.path.join(destination_path, os.path.basename(netfile))])


def create_new_destination_folder(options, sim_key, iteration, params):
    """create files and folders, only if necessary,
       set options values even if nothing needs to be copied"""

    template = params[SP.template]
    destination = params[SP.destination]

    # make sure you are where you think you should be
    if not os.path.exists(options.workdir_folder):
        os.makedirs(options.workdir_folder)
    assert os.path.isdir(options.workdir_folder), 'workdir "%s" does not exist' % options.workdir_folder

    destination_path = os.path.join(options.workdir_folder, destination)
    if iteration == 0:
        # check if a template for the requested sim could be found
        template_path = os.path.join(options.template_folder, template)

        assert os.path.isdir(template_path), "no data for %s in %s" % (sim_key, template_path)

        # where to put the copy of the template
        if not os.path.isdir(destination_path):
            print("creating scenario %s from scratch in %s " % (sim_key, destination_path))
            os.mkdir(destination_path)
            # get things from template folder
            for ext in ("xml", "xml.gz", "csv", "csv.gz", "params"):
                for ff in glob.glob(os.path.join(template_path, '*.' + ext)):
                    shutil.copyfile(ff, os.path.join(destination_path, os.path.basename(ff)))
            netList = glob.glob(os.path.join(template_path, 'net.net.xml*'))
            net = netList[0] if netList else glob.glob(os.path.join(template_path, '*.net.xml*'))[0]
            netOut = os.path.join(destination_path, os.path.basename(net))
            netTemp = None
            for cfg in sorted(glob.glob(os.path.join(template_path, '*.netccfg'))):
                netTemp = netOut + os.path.basename(cfg)
                subprocess.call([sumolib.checkBinary("netconvert"), "-c", cfg, "-s", net, "-o", netTemp])
                net = netTemp
            restrictions = json.loads(params[SP.net_param])
            if restrictions:
                if isinstance(restrictions, dict):
                    build_restricted_network(restrictions, destination_path, net)
                else:
                    for origin, destination in restrictions:
                        os.rename(os.path.join(destination_path, origin), os.path.join(destination_path, destination))
            elif netTemp:
                os.rename(netTemp, netOut)
    return destination_path


def create_new_iteration_folder(options, iteration, destination_path):
    # make sure you are where you think you should be
    assert os.path.isdir(destination_path), 'destination_folder "%s" does not exist' % destination_path
    files_folders = common.listdir_skip_hidden(destination_path)

    iteration_path = os.path.join(destination_path, "iteration%03i" % iteration)
    if not os.path.exists(iteration_path):
        try:
            max_existing_iteration = max([int(ff[9:]) for ff in files_folders if ff[:9] == 'iteration'])
            assert iteration - 1 == max_existing_iteration,\
                   "iteration number from db (%s) is not the successor of the last existing iteration (%s)" % (
                   iteration, max_existing_iteration)
        except ValueError:
            assert iteration == 0, "no earlier iterations present but iteration %s was requested" % iteration
        os.mkdir(iteration_path)
    elif options.resume:
        print("Warning! Reusing iteration directory:", iteration_path)
    return iteration_path


def run_all_pairs(options, conn, sim_key, params, final_routes, final_weights):
    all_pair_tables = s2t_miv.create_all_pairs(conn, sim_key, params)
    modes = set()
    vTypes = set()
    for (m, t), _ in common.csv_sequence_generator(options.tapas_trips, ("mode", "sumo_type")):
        modes.add(str(m))
        vTypes.add(str(t))

    write_status('>> starting all pairs calculation', sim_key, params, conn)
    options.assignment = "bulk"
    options.trips_dir = os.path.join(options.iteration_dir, 'allpairs')
    options.weights = os.path.join(options.trips_dir, os.path.basename(final_weights))
    if not os.path.exists(options.weights) or not options.resume:
        s2t_miv.aggregate_weights(final_weights, params[SP.od_slices], options.weights)
    else:
        print("Reusing aggregated weights:", options.weights)
    options.rectify = False
    options.scale = 1.0
    options.time_diffusion = 0
    startIdx = 0
    vtMap = {}
    for vt in sumolib.xml.parse(options.vtype_file, "vType"):
        if vt.id in vTypes:
            if options.vtype_matrix:
                vtMap[vt.id] = vt.id
            elif vt.vClass not in vtMap:
                vtMap[vt.vClass] = vt.id
    if options.vtype_matrix:
        print("found the following vehicle types:", list(sorted(vTypes)))
    else:
        print("found the following vehicle classes:", list(vtMap.keys()))
    rou_file = None  # in case we have no representatives
    for mapType, vType in sorted(vtMap.items()):
        begin_second = 0
        for end_hour in params[SP.od_slices]:
            end_second = end_hour * 3600
            write_status('>>> starting all pairs for %s, slice ending at hour %s' % (
                mapType, end_hour), sim_key, params, conn)
            if params[SP.representatives]:
                options.tapas_trips = get_trips.tripfile_name("%s_%s%02i" % (
                    get_trips.ALL_PAIRS, mapType, end_hour), target_dir=options.trips_dir)
                trips_file = None
                if not os.path.exists(options.tapas_trips) or not options.resume:
                    trips_file = options.tapas_trips
                get_trips.write_all_pairs(conn, vType, begin_second, options.limit, trips_file, params, options.seed,
                                          bbox=options.representatives_bbox)
                write_status('>>> starting all pairs t2s using tripfile %s' %
                            options.tapas_trips, sim_key, params, conn)
                conn.close()
                rou_file, _ = t2s.main(options)
                conn = database.get_conn(options, conn)
                write_status('<<< finished all pairs t2s, routes in %s' % rou_file, sim_key, params, conn)
                assert os.path.exists(rou_file), "all pairs route file %s could not be found" % rou_file
            write_status('>>> starting od result database upload', sim_key, params, conn)
            startIdx = s2t_miv.upload_all_pairs(conn, all_pair_tables, begin_second, end_second, vType,
                                                final_routes, rou_file, options.net, startIdx)
            write_status('<<< finished od result database upload', sim_key, params, conn)
            begin_second = end_second
    if not modes <= set(CAR_MODES):
        write_status('>>> starting all pairs for public transport', sim_key, params, conn)
        if params[SP.representatives]:
            options.tapas_trips = get_trips.tripfile_name("%s_public" % (get_trips.ALL_PAIRS), target_dir=options.trips_dir)
            get_trips.write_all_pairs(conn, "public", 31 * 3600, options.limit, options.tapas_trips, params,
                                      options.seed, MODE.public, bbox=options.representatives_bbox)
            write_status('>>> starting all pairs t2s using tripfile %s' % options.tapas_trips, sim_key, params, conn)
            conn.close()
            rou_file, _ = t2s.main(options)
            conn = database.get_conn(options, conn)
            write_status('<<< finished all pairs t2s, routes in %s' % rou_file, sim_key, params, conn)
            assert os.path.exists(rou_file), "all pairs route file %s could not be found" % rou_file
        write_status('>>> starting od result database upload', sim_key, params, conn)
        startIdx = s2t_pt.upload_all_pairs(conn, all_pair_tables, 31 * 3600, 32 * 3600,
                                           final_routes, rou_file, options.net, startIdx)
        write_status('<<< finished od result database upload', sim_key, params, conn)
    write_status('<< finished all pairs calculation', sim_key, params, conn)


def cleanup(save, iteration_dir, sim_key, iteration, params, conn):
    if params[SP.del_temp].lower() in ["1", "true", "yes"]:
        write_status('deleting temporary files of iteration %s' %
                     iteration, sim_key, params, conn)
        for f in save:
            shutil.move(f, iteration_dir)
        _, dirnames, _ = next(os.walk(iteration_dir))
        for d in dirnames:
            shutil.rmtree(os.path.join(iteration_dir, d))
    if params[SP.del_intermediate].lower() in ["1", "true", "yes"]:
        if iteration + 1 == int(params[SP.max_iteration]):
            write_status('deleting all intermediate iterations', sim_key, params, conn)
            basedir = os.path.dirname(iteration_dir)
            for i in range(iteration):
                shutil.rmtree(os.path.join(basedir, "iteration%03i" % i))


def write_status(message, sim_key, params, conn=None, msg_type=constants.MSG_TYPE.info):
    print('db_status_%s: %s %s %s' %
          (msg_type, sim_key, params[SP.iteration], message))
    if conn is not None and sim_key is not None:
        command = "INSERT INTO public.%s (sim_key, iteration, status_time, status, msg_type) VALUES (?, ?, ?, ?, ?);"
        database.execute(conn, command % params[SP.status],
                               (sim_key, params[SP.iteration], datetime.datetime.now(), str(message), msg_type))
        # make sure the time stamp is unique, otherwise the primary key is violated
        time.sleep(0.01)


def get_script_module(options, template):
    try:
        if os.path.dirname(options.template_folder) not in sys.path:
            sys.path.append(os.path.dirname(options.template_folder))
        module = importlib.import_module(os.path.basename(options.template_folder) + "." + template)
        for f in module.__dict__.keys():
            if f[:2] != "__":
                return module
        print("No scenario specific assignment or post processing functions in", template)
    except ImportError as m:
        print("No scenario specific assignment or post processing functions:", m)
    return None


def simulation_request(options, request):
    conn = None
    sim_key, iteration, params = request
    try:
        # connect to the database (prod-system)
        conn = database.get_conn(options)
        if conn is None:
            print("Warning! No database connection given, operating on files only.")

        write_status("> Begin", sim_key, params, conn, constants.MSG_TYPE.started)
        print(sorted(params.items()))

        # create the destination dir if it's not already existing (not the first iteration)
        scenario_basedir = create_new_destination_folder(options, sim_key, iteration, params)

        options.net_file = os.path.abspath(os.path.join(scenario_basedir, 'net.net.xml'))
        if not os.path.exists(options.net_file):
            options.net_file += ".gz"
        if options.taz_file is None and params.get('DB_TABLE_TAZ') == 'berlin_taz_1223':
            # just a hack to have a good taz file for the new scenarios
            options.taz_file = os.path.abspath(os.path.join(scenario_basedir, 'Berlin_1223.taz.xml.gz'))
        options.bidi_taz_file = os.path.abspath(os.path.join(scenario_basedir, 'bidi.taz.xml.gz'))
        options.tapas_trips = os.path.join(scenario_basedir, "background_traffic.csv")
        if iteration == 0 and params[SP.add_traffic_table] not in (None, '', 'none') and conn is not None:
#            options.modes = ','.join(CAR_MODES)
            if not os.path.exists(options.tapas_trips) or not options.resume:
                get_trips.write_background_trips(conn, params[SP.add_traffic_table],
                                                 options.limit, options.tapas_trips, params)
            options.location_priority_file = os.path.abspath(os.path.join(scenario_basedir, 'location_priorities.xml'))
            get_motorway_access.save_locations(options.location_priority_file, options, params[SP.add_traffic_table])
            options.trips_dir = scenario_basedir
            write_status('>> starting trip generation for background traffic using tripfile %s' %
                         options.tapas_trips, sim_key, params, conn)
            conn.close()
            options.background_trips, _ = t2s.main(options)
            options.location_priority_file = ""
        else:
            options.background_trips = t2s.getSumoTripfileName(scenario_basedir, options.tapas_trips)
        options.modes = params[SP.modes].replace(";", ",")

        # create a new iteration folder
        options.iteration_dir = create_new_iteration_folder(options, iteration, scenario_basedir)
        conn = database.get_conn(options, conn)
        write_status(">> iteration dir: %s " % options.iteration_dir, sim_key, params, conn)
        options.trips_dir = os.path.join(options.iteration_dir, 'trips')
        if not os.path.exists(options.trips_dir):
            os.makedirs(options.trips_dir)

        # get the trip files in place - either by faking or processing db data
        if options.fake_tripfile is not None:
            options.tapas_trips = options.fake_tripfile
        else:
            assert sim_key is not None, 'no sim_key for db given'
            options.tapas_trips = get_trips.tripfile_name(sim_key, target_dir=options.trips_dir)
            if not os.path.exists(options.tapas_trips) or not options.resume:
                get_trips.write_trips(conn, sim_key, options.limit, options.tapas_trips, params)
        print()
        write_status('>> starting t2s using tripfile %s' %
                     options.tapas_trips, sim_key, params, conn)
        if conn is not None:
            conn.close()

        # run t2s
        options.scale /= float(params[SP.sample])
        options.script_module = get_script_module(options, params[SP.template])
        if hasattr(options.script_module, "trip_filter") and not params[SP.trip_filter]:
            delattr(options.script_module, "trip_filter")
        final_routes, final_weights = t2s.main(options)
        conn = database.get_conn(options, conn)
        write_status('<< finished t2s, routes in %s' % final_routes, sim_key, params, conn)
        assert os.path.exists(final_routes), "route file %s could not be found" % final_routes
        assert os.path.exists(final_weights), "weight dump file %s could not be found" % final_weights

        # run post processing
        if iteration == int(params[SP.max_iteration]) - 1 and hasattr(options.script_module, "post"):
            print()
            write_status('>> starting postprocessing', sim_key, params, conn)
            options.script_module.post(options, params, conn, final_routes)
            write_status('<< finished postprocessing', sim_key, params, conn)

        if conn is not None:
            print()
            conn = database.get_conn(options, conn)
            # upload trip results to db
            _, _, exists = database.check_schema_table(conn, 'temp', '%s_%s' % (params[SP.trip_output], sim_key))
            if not exists or not options.resume:
                write_status('>> starting trip result database upload', sim_key, params, conn)
                s2t_miv.upload_trip_results(conn, sim_key, params, final_routes, options.trip_emissions)
                write_status('<< finished trip result database upload', sim_key, params, conn)
                print()
            # run all pair calculations
            conn = database.get_conn(options, conn)
            run_all_pairs(options, conn, sim_key, params, final_routes, final_weights)

        conn = database.get_conn(options, conn)
        cleanup([final_routes, final_weights], options.iteration_dir,
                 sim_key, iteration, params, conn)

        write_status("< End", sim_key, params, conn, constants.MSG_TYPE.finished)
    except (AssertionError, IOError, subprocess.CalledProcessError, t2s.MappingError) as message:
        write_status(message, sim_key, params, conn, constants.MSG_TYPE.error)
    except ProgrammingError as message:
        conn.rollback()
        write_status(message, sim_key, params, conn, constants.MSG_TYPE.error)

    # exit gracefully
    if conn is not None:
        conn.close()


def main(args=None):
    # get the options
    argParser = ArgumentParser()
    options = getOptions(args, argParser)
    if options.log:
        log = open(options.log, "w")
        sys.stdout = sumolib.TeeFile(sys.stdout, log)
        sys.stderr = sumolib.TeeFile(sys.stderr, log)

    if options.clean:
        shutil.rmtree(options.workdir_folder, True)
        conn = database.get_conn(options)
        if conn is None:
            print("Warning! No database connection given, deleting files only.")
        else:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM public.%s;" % (SP.OPTIONAL[SP.status]))
            conn.commit()
            conn.close()
        return

    processes = {}
    now = datetime.datetime.now()
    if options.daemon_run_time > 0:
        daemon_end_time = now + datetime.timedelta(seconds=options.daemon_run_time)
    else:
        daemon_end_time = datetime.datetime.max
    while now < daemon_end_time:
        # clean up finished processes
        for key in list(processes.keys()):
            if not processes[key].is_alive():
                del processes[key]
        # check for a new simulation request
        for request in get_simulation_requests(options):
            if request[0] in processes:  # this should happen in tests only
                processes[request[0]].join()
                del processes[request[0]]
            if len(processes) >= options.parallel:
                break
            processes[request[0]] = multiprocessing.Process(
                target=simulation_request, args=(options, request))
            processes[request[0]].start()
        if not options.daemon:
            break
        time.sleep(2)
        prev = now
        now = datetime.datetime.now()
        if prev.hour != now.hour:
            print("still listening", now)

    for p in processes.values():
        p.join()


if __name__ == "__main__":
    main(sys.argv[1:])
