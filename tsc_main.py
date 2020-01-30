#!/usr/bin/env python
"""
@file    tsc_main.py
@author  Marek.Heinrich@dlr.de
@author  Michael.Behrisch@dlr.de
@date    2014-12-15
@version $Id: tsc_main.py 7914 2019-08-22 13:17:57Z behr_mi $

This script runs permanently in the background and triggers sumo runs (t2s, s2t)

The following things must be done before this script can run:
 - python install_scenario_templates.py 

for legacy operation call:
    python tsc_main.py --server achilles
     --sim-key 2014y_08m_18d_15h_12m_21s_540ms --iteration 0

# Copyright (C) 2010-2020 German Aerospace Center (DLR) and others.
# This program and the accompanying materials
# are made available under the terms of the Eclipse Public License v2.0
# which accompanies this distribution, and is available at
# http://www.eclipse.org/legal/epl-v20.html
# SPDX-License-Identifier: EPL-2.0
"""

from __future__ import print_function
import os
import sys
import shutil
import optparse
import glob
import json
import datetime
import time
import multiprocessing
import subprocess
from psycopg2 import ProgrammingError

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path += [tools, os.path.join(tools, 'assign')]
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

import sumolib

import common
import constants
import get_trips
import t2s
import s2t_miv
from constants import SP
import get_motorway_access

DEFAULT_SIMKEY = "berlin_2010"

def getOptions(args, optParser):
    t2s.fillOptions(optParser)
    optParser.add_option("--server", help="specify the database server to sync with (e.g. test)")
    optParser.add_option("--workdir-folder", default='scenario_workdir',
                         help="specifying the workdir directory of the scenarios to use")
    optParser.add_option("--template-folder", default='scenario_templates',
                         help="specifying the template directory of the scenarios to use")
    optParser.add_option("-t", "--fake-tripfile",
                         help="use this trip file as input instead of database (use only for debug and testing)")
    optParser.add_option("--limit", type=int, help="maximum number of trips to retrieve")
    optParser.add_option("--parallel", type=int, default=1,
                         help="maximum number of parallel simulations to run")
    optParser.add_option("--clean", action="store_true", default=False,
                         help="cleanup working dir and status table and exit")
    optParser.add_option("--daemon", action="store_true", default=False, help="run as daemon")
    optParser.add_option("--daemon-run-time", type=int, default=-1,
                         help="limit the up time of the daemon in seconds - e.g. for debugging ")
    optParser.add_option('--iteration', help="iterations of faked simulation requests (ranges and ints are possible)")
    optParser.add_option("--sim-key",
                         help="sim_key of faked simulation requests.\nUse only for testing")
    optParser.add_option("--sim-param", default="",
                         help="additional parameters of faked simulation requests [default: %default].\nUse only for testing")
    optParser.add_option('--net-param', default="{}",
                         help="network restrictions of faked simulation requests.\nUse only for testing")

    options, remaining_args = optParser.parse_args(args=args)
    if len(args) == 0:
        optParser.print_help()
        sys.exit()
    options.limit = " LIMIT %s" % options.limit if options.limit else ""
    assert len(remaining_args) == 0, "there are unknown options %s " % " ".join(
        remaining_args)
    return options


def get_simulation_requests(options):
    overrides = dict([item.split(":") for item in options.sim_param.split(",") if item])
    if options.fake_tripfile or options.sim_key:
        if options.sim_key is None:
            options.sim_key = DEFAULT_SIMKEY
        if options.iteration is None:
            destination_path = os.path.join(options.workdir_folder, overrides.get(SP.destination, SP.OPTIONAL[SP.destination]))
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
            sim_params = dict(SP.OPTIONAL)
            sim_params.update({SP.net_param: options.net_param,
                               SP.iteration: str(i),
                               SP.max_iteration: str(max(iterations)+1)})
            sim_params.update(overrides)
            simulation_request_list.append((options.sim_key, i, sim_params))
        return simulation_request_list
    return get_trips.get_active_sim_keys(options.server, overrides)


def build_restricted_network(restrictions, destination_path, netfile):
    typefile = os.path.join(destination_path, "restrictions.typ.xml")
    with open(typefile, 'w') as types:
        types.write("""<?xml version="1.0" encoding="UTF-8"?>
<types xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/types_file.xsd">
""")
        for list_file, res in restrictions.iteritems():
            if "allowed" in res:
                allowed = ' allow="%s"' % (" ".join(res["allowed"]))
            types.write('    <type id="%s"%s>\n' % (list_file, allowed))
            for vClass, speed in res.get("maxSpeed", {}).iteritems():
                types.write(
                    '        <restriction vClass="%s" speed="%s"/>\n' % (vClass, speed))
            types.write('    </type>\n')
        types.write('</types>\n')

    edgefile = os.path.join(destination_path, "restricted_edges.edg.xml")
    with open(edgefile, 'w') as edges:
        edges.write("""<?xml version="1.0" encoding="UTF-8"?>
<edges xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/edgediff_file.xsd">
""")
        for list_file in restrictions.iterkeys():
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

    subprocess.call([sumolib.checkBinary("netconvert"), "-s", netfile, "-t", types.name,
                     "-e", edges.name, "-o", os.path.join(destination_path, os.path.basename(netfile))])


def create_new_destination_folder(options, sim_key, iteration, params):
    """create files and folders, only if necessary,
       set options values even if nothing needs to be copied"""

    template = params[SP.template]
    destination = params[SP.destination]

    # make sure you are where you think you should be
    if not os.path.exists(options.workdir_folder):
        os.makedirs(options.workdir_folder)
    assert os.path.isdir(
        options.workdir_folder), 'workdir "%s" does not exist' % options.workdir_folder

    destination_path = os.path.join(options.workdir_folder, destination)
    if iteration == 0:
        # check if a template for the requested sim could be found
        template_path = os.path.join(options.template_folder, template)

        assert os.path.isdir(template_path), "no data for %s in %s" % (
            sim_key, template_path)

        # where to put the copy of the template
        if not os.path.isdir(destination_path):
            print("create scenario %s from scratch in %s " %
                  (sim_key, destination_path))
            os.mkdir(destination_path)
            # get things from template folder
            for ext in ("xml", "csv", "params"):
                for ff in glob.glob(os.path.join(template_path, '*.' + ext)):
                    shutil.copyfile(ff, os.path.join(destination_path, os.path.basename(ff)))
            net = glob.glob(os.path.join(template_path, '*.net.xml'))[0]
            netOut = os.path.join(destination_path, os.path.basename(net))
            netTemp = None
            for cfg in sorted(glob.glob(os.path.join(template_path, '*.netccfg'))):
                netTemp = netOut + os.path.basename(cfg)
                subprocess.call([sumolib.checkBinary("netconvert"), "-c", cfg, "-s", net,
                                 "-o", netTemp])
                net = netTemp
            restrictions = json.loads(params[SP.net_param])
            if restrictions:
                build_restricted_network(restrictions, destination_path, net)
            elif netTemp:
                os.rename(netTemp, netOut)
    return destination_path


def create_new_iteration_folder(options, iteration, destination_path):
    # make sure you are where you think you should be
    assert os.path.isdir(
        destination_path), 'destination_folder "%s" does not exist' % destination_path
    files_folders = common.listdir_skip_hidden(destination_path)

    try:
        max_existing_iteration = max(
            [int(ff[9:]) for ff in files_folders if ff[:9] == 'iteration'])
        assert iteration - \
            1 == max_existing_iteration, "iteration number from db (%s) is not the successor of the last existing iteration (%s)" % (
                iteration, max_existing_iteration)
    except ValueError:
        assert iteration == 0, "no earlier iterations present but iteration %s was requested" % iteration
    iteration_path = os.path.join(
        destination_path, "iteration%03i" % iteration)
    assert not os.path.exists(
        iteration_path), 'folder exists: %s' % iteration_path
    os.mkdir(iteration_path)
    return iteration_path


def run_all_pairs(options, conn, sim_key, params, final_routes, final_weights):
    all_pair_table = s2t_miv.create_all_pairs(conn, sim_key, params)
    vTypes = set()
    for (t, ), _ in common.csv_sequence_generator(options.tapas_trips, "sumo_type"):
        vTypes.add(str(t))
    orig_tapas_trips = options.tapas_trips

    write_status('>> starting all pairs calculation', sim_key, params, conn)
    options.assignment = "bulk"
    options.bidi_taz_file = None
    options.weights = s2t_miv.aggregate_weights(
        final_weights, params[SP.od_slices])
    options.trips_dir = os.path.join(options.iteration_dir, 'allpairs')
    options.rectify = False
    options.scale = 1.0
    options.time_diffusion = 0
    startIdx = 0
    for vType in sorted(vTypes):
        begin_second = 0
        for end_hour in params[SP.od_slices]:
            end_second = end_hour * 3600
            write_status('>>> starting all pairs for %s, slice ending at hour %s' % (
                vType, end_hour), sim_key, params, conn)
            options.tapas_trips = get_trips.tripfile_name("%s_%s%02i" % (
                get_trips.ALL_PAIRS, vType, end_hour), target_dir=options.trips_dir)
            taz_list = get_trips.write_all_pairs(
                conn, vType, begin_second, options.limit, options.tapas_trips, params, options.seed)
            write_status('>>> starting all pairs t2s using tripfile %s' %
                         options.tapas_trips, sim_key, params, conn)
            alt_file, _ = t2s.main(options)
            write_status('<<< finished all pairs t2s, routes in %s' %
                         alt_file, sim_key, params, conn)
            assert os.path.exists(
                alt_file), "all pairs route file %s could not be found" % alt_file
            write_status(
                '>>> starting od result database upload', sim_key, params, conn)
            startIdx = s2t_miv.upload_all_pairs(conn, all_pair_table, begin_second, end_second, vType,
                                                final_routes, alt_file, options.net, taz_list, startIdx)
            write_status(
                '<<< finished od result database upload', sim_key, params, conn)
            begin_second = end_second
    write_status('<< finished all pairs calculation', sim_key, params, conn)


def cleanup(save, iteration_dir, sim_key, iteration, params, conn):
    if params[SP.del_temp].lower() in ["1", "true", "yes"]:
        write_status('deleting temporary files of iteration %s' %
                     iteration, sim_key, params, conn)
        for f in save:
            shutil.move(f, iteration_dir)
        _, dirnames, _ = os.walk(iteration_dir).next()
        for d in dirnames:
            shutil.rmtree(os.path.join(iteration_dir, d))
    if params[SP.del_intermediate].lower() in ["1", "true", "yes"]:
        if iteration + 1 == int(params[SP.max_iteration]):
            write_status(
                'deleting all intermediate iterations', sim_key, params, conn)
            basedir = os.path.dirname(iteration_dir)
            for i in xrange(iteration):
                shutil.rmtree(os.path.join(basedir, "iteration%03i" % i))


def write_status(message, sim_key, params, conn=None, msg_type=constants.MSG_TYPE.info):
    print('db_status_%s: %s %s %s' %
          (msg_type, sim_key, params[SP.iteration], message))
    if conn is not None and sim_key is not None:
        cursor = conn.cursor()
        command = """
        INSERT INTO core.%s
        (sim_key, iteration, status_time, status, msg_type)
        VALUES
        ('%s', %s, NOW(), %%s, %%s);
        """ % (params[SP.status], sim_key, params[SP.iteration])
        cursor.execute(command, (str(message), msg_type))
        conn.commit()
        # make sure the time stamp is unique, otherwise the primary key is
        # violated
        time.sleep(0.01)


def get_script_module(options, template):
    try:
        if options.template_folder not in sys.path:
            sys.path.append(options.template_folder)
        import scripts
        if hasattr(scripts, template):
            return getattr(scripts, template)
    except ImportError, m:
        # print("Import failed", m, sys.path)
        pass
    return None


def simulation_request(options, optParser, request):
    conn = None
    sim_key, iteration, params = request
    try:
        # connect to the database (prod-system)
        conn = get_trips.get_conn(options.server)
        if conn is None:
            print("Warning! No database connection given, operating on files only.")

        write_status("> Begin", sim_key, params, conn, constants.MSG_TYPE.started)
        print(sorted(params.items()))

        # create the destination dir if it's not already existing (not the first iteration)
        scenario_basedir = create_new_destination_folder(options, sim_key, iteration, params)

        options.net_file = os.path.abspath(os.path.join(scenario_basedir, 'net.net.xml'))
        options.bidi_taz_file = os.path.abspath(os.path.join(scenario_basedir, 'bidi.taz.xml'))
        options.tapas_trips = os.path.join(scenario_basedir, "background_traffic.csv")
        options.modes = params[SP.modes].replace(";", ",")
        if iteration == 0 and params[SP.add_traffic_table] and conn is not None:
            get_trips.write_background_trips(
                conn, params[SP.add_traffic_table], options.limit, options.tapas_trips, params)
            options.location_priority_file = os.path.abspath(os.path.join(scenario_basedir, 'location_priorities.xml'))
            get_motorway_access.save_locations(options.location_priority_file, options.server, params[SP.add_traffic_table])
            options.trips_dir = scenario_basedir
            write_status('>> starting trip generation for background traffic using tripfile %s' %
                         options.tapas_trips, sim_key, params, conn)
            options.background_trips, _ = t2s.main(options)
            options.location_priority_file = ""
        else:
            options.background_trips = t2s.getSumoTripfileName(scenario_basedir, options.tapas_trips)


        # create a new iteration folder
        options.iteration_dir = create_new_iteration_folder(
            options, iteration, scenario_basedir)
        write_status(">> created dir: %s " %
                     options.iteration_dir, sim_key, params, conn)
        options.trips_dir = os.path.join(options.iteration_dir, 'trips')
        if not os.path.exists(options.trips_dir):
            os.makedirs(options.trips_dir)

        # get the trip files in place - either by faking or processing db data
        if options.fake_tripfile is not None:
            options.tapas_trips = options.fake_tripfile
        else:
            assert sim_key is not None, 'no sim_key for db given'
            options.tapas_trips = get_trips.tripfile_name(
                sim_key, target_dir=options.trips_dir)
            get_trips.write_trips(
                conn, sim_key, options.limit, options.tapas_trips, params)
        print()
        write_status('>> starting t2s using tripfile %s' %
                     options.tapas_trips, sim_key, params, conn)

        # run t2s
        options.scale = 1.0 / float(params[SP.sample])
        options.script_module = get_script_module(options, params[SP.template])
        final_routes, final_weights = t2s.main(options)
        write_status('<< finished t2s, routes in %s' %
                     final_routes, sim_key, params, conn)
        assert os.path.exists(
            final_routes), "route file %s could not be found" % final_routes
        assert os.path.exists(
            final_weights), "weight dump file %s could not be found" % final_weights

        # run post processing
        if iteration == int(params[SP.max_iteration]) - 1 and options.script_module is not None:
            print()
            write_status('>> starting postprocessing', sim_key, params, conn)
            options.script_module.post(options, params, conn, final_routes)
            write_status('<< finished postprocessing', sim_key, params, conn)

        if conn is not None:
            print()
            # upload trip results to db
            write_status(
                '>> starting trip result database upload', sim_key, params, conn)
            s2t_miv.upload_trip_results(conn, sim_key, params, final_routes)
            write_status(
                '<< finished trip result database upload', sim_key, params, conn)

            print()
            run_all_pairs(
                options, conn, sim_key, params, final_routes, final_weights)

        cleanup([final_routes, final_weights], options.iteration_dir,
                sim_key, iteration, params, conn)

        write_status(
            "< End", sim_key, params, conn, constants.MSG_TYPE.finished)
    except (AssertionError, IOError, subprocess.CalledProcessError, t2s.MappingError), message:
        write_status(message, sim_key, params, conn, constants.MSG_TYPE.error)
    except ProgrammingError, message:
        conn.rollback()
        write_status(message, sim_key, params, conn, constants.MSG_TYPE.error)

    # exit gracefully
    if conn:
        conn.close()


def main(args):
    # get the options
    optParser = optparse.OptionParser()
    options = getOptions(args, optParser)

    if options.clean:
        shutil.rmtree(options.workdir_folder, True)
        conn = get_trips.get_conn(options.server)
        if conn is None:
            print("Warning! No database connection given, deleting files only.")
        else:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM core.%s;" % (SP.OPTIONAL[SP.status]))
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
        for key in processes.keys():
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
                target=simulation_request, args=(options, optParser, request))
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
