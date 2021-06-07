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

# @file    assign.py
# @author  Jakob Erdmann
# @author  Michael Behrisch
# @date    2013-12-15

# assignment methods for tapas trips

from __future__ import print_function, division
import os
import sys
import subprocess
import glob
import copy

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path += [tools, os.path.join(tools, 'assign'), os.path.join(tools, 'route')]
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")

import duaIterate
import sumolib
from sumolib.miscutils import working_dir, benchmark
import cutRoutes
import sort_routes

from common import abspath_in_dir
from constants import TAPAS_EXTRA_TIME

@benchmark
def run_duaiterate(options, first_depart, last_depart, trip_file, weight_file, meso=True):
    dua_dir = os.path.join(options.iteration_dir, 'dua')
    if not os.path.exists(dua_dir):
        os.makedirs(dua_dir)
    duaIterate_params = abspath_in_dir(dua_dir, 'duaIterate.params')

    aggregation = 1800
    begin = (int(first_depart) / aggregation) * aggregation
    additional = [options.vtype_file]
    if options.bidi_taz_file:
        additional.append(options.bidi_taz_file)
    trips = [trip_file]
    if os.path.exists(options.background_trips):
        trips.append(options.background_trips)
    params = [
        '--router-verbose',
        '--net-file', options.net_file,
        '--trips', ",".join(trips),
        '--additional', ','.join(additional),
        '--begin', str(begin),
        '--end',  str(last_depart + TAPAS_EXTRA_TIME),
        '--nointernal-link',
        # compromise between cheating and solving deadlocks
        '--time-to-teleport', '60',
        # '--route-steps','200', # work around a bug where not enough vehicles are emitted
        '--last-step', str(options.last_step),
        '--disable-summary',
        '--routing-algorithm', options.routing_algorithm,
        # 3600 may be to imprecise for convergence, compromise weight
        # aggregation since CH is static
        '--aggregation', str(aggregation),
        # to many alts cost space/time and may hinder convergence
        '--max-alternatives', '3',
        '--continue-on-unbuild',
        '--inc-base', '100',   #
        '--incrementation', '1',      #
        '--inc-start', '0.40',   #
        # '--inc-max', str(scale),   # we scale on trip level now
        '--router-verbose',  #
        '--zip',  #
        '--disable-tripinfos',
        '--vehroute-file', 'routesonly',
        # gawrons a (default 0.5): higher values increase route probability
        # volatility
        '--gA', '1',
        # '--binary', # do we dare use binary mode?
        # '--time-inc',     # reduce running time on initial runs...
        '--weight-memory',
    ]
    if meso:
        params += [
            '--mesosim',
            '--meso-recheck', '10',
            '--meso-multiqueue',
            # now come the positional args (needed when passing negative values
            '--',
            'sumo--meso-tauff', '1.4',
            'sumo--meso-taufj', '1.4',
            'sumo--meso-taujf', '2.0',
            'sumo--meso-taujj', '2.0',
            'sumo--meso-jam-threshold', '-1',  # edge speed specific threshold
            'sumo--meso-junction-control.limited',
        ]
    params += [
        'sumo--phemlight-path', options.phemlight_path,
        # city traffic has shorter headways than highway traffic...
        'sumo--max-depart-delay', '300',
        'duarouter--phemlight-path', options.phemlight_path,
        'duarouter--additional-files', ','.join(additional),
        'duarouter--vtype-output', '/dev/null',
        'duarouter--routing-threads', '16',
    ]
    with open(duaIterate_params, 'w') as f:
        print(os.linesep.join(params), file=f)

    with working_dir(dua_dir):
        duaIterate.main(params)

    routes = abspath_in_dir(
        dua_dir, "vehroute_%03i.xml" % (options.last_step - 1))
    weights = abspath_in_dir(
        dua_dir, "dump_%03i_%s.xml" % (options.last_step - 1, aggregation))
    return routes, weights


@benchmark
def run_oneshot(options, first_depart, last_depart, trip_file, weight_file, meso=True, addOpt=""):
    oneshot_dir = os.path.join(options.iteration_dir, 'oneshot')
    if not os.path.exists(oneshot_dir):
        os.makedirs(oneshot_dir)
    suffix = "oneshot_meso" if meso else "oneshot_micro"
    oneshot_routes = abspath_in_dir(
        oneshot_dir, 'vehroutes_%s.rou.xml' % suffix)
    oneshot_weights = abspath_in_dir(oneshot_dir, 'aggregated_%s.xml' % suffix)
    if os.path.exists(oneshot_routes):
        print("Route file", oneshot_routes, "exists! Skipping assignment.")
        return oneshot_routes, oneshot_weights
    aggregation = 1800
    begin = (int(first_depart) / aggregation) * aggregation
    additional = [options.vtype_file, 'dump_' + suffix + '.xml']
    if options.bidi_taz_file:
        additional.append(options.bidi_taz_file)
    base_dir = os.path.dirname(options.net_file)
    if not meso:
        for add in (os.path.join(base_dir, 'tlsOffsets.add.xml'), os.path.join(oneshot_dir, 'vehroutes_%s_tls.add.xml' % suffix)):
            if os.path.exists(add):
                additional.append(add)
    extra_opt = addOpt.split()
    extra_cfg = os.path.join(base_dir, 'extra.params')
    if os.path.exists(extra_cfg):
        extra_opt += open(extra_cfg).read().split()
    trips = [trip_file]
    if os.path.exists(options.background_trips):
        trips.append(options.background_trips)
        additional.append(os.path.join(base_dir, 'suburb.taz.xml'))
    specificPT = glob.glob(abspath_in_dir(oneshot_dir, 'pt*.xml'))
    additional += sorted(specificPT if specificPT else glob.glob(os.path.join(base_dir, 'pt*.xml')))

    tempcfg = abspath_in_dir(oneshot_dir, '%s_temp.sumocfg' % suffix)
    addOpt = ""
    if meso:
        addOpt += """
        <mesosim value="true"/>
        <meso-recheck value="10"/>
        <meso-multi-queue value="true"/>
        <meso-jam-threshold value="-0.5"/>
        <meso-junction-control.limited value="true"/>
        <meso-minor-penalty value="0.5"/>
        <meso-tls-penalty value="0.5"/>"""
    if meso and os.path.exists(os.path.join(base_dir, "landmarks.csv")):
        addOpt += """
        <astar.landmark-distances value="%s"/>""" % os.path.join(base_dir, "landmarks.csv")
    with open(tempcfg, 'w') as f:
        f.write(
            """<configuration>
        <net-file value="%s"/>
        <route-files value="%s"/>
        <additional-files value="%s"/>

        <vehroute-output value="%s"/>
        <vehroute-output.sorted value="true"/>
        <vehroute-output.last-route value="true"/>
        <vehroute-output.intended-depart value="true"/>
        <vehroute-output.route-length value="true"/>
        <vehroute-output.skip-ptlines value="true"/>
        <vehroute-output.exit-times value="true"/>

        <pedestrian.model value="nonInteracting"/>
        <routing-algorithm value="astar"/>
        <device.rerouting.probability value="1"/>
        <device.rerouting.threads value="16"/>
        <device.rerouting.adaptation-interval value="10"/>
        <device.rerouting.adaptation-weight value="0.5"/>
        <device.rerouting.period value="300"/>
        <device.rerouting.pre-period value="10"/>
        <device.taxi.dispatch-algorithm value="greedyShared"/>

        <save-state.period value="3600"/>
        <save-state.suffix value=".xml.gz"/>
        <summary-output value="summary.xml.gz"/>

        <no-step-log value="true"/>
        <log-file value="%s.sumo.log"/>
        <ignore-route-errors value="true"/>

        <begin value="%s"/>
        <end value="%s"/>
        %s

        <phemlight-path value="%s"/>

</configuration>""" % (options.net_file, ",".join(trips),
                       ','.join(additional),
                       oneshot_routes, suffix,
                       begin, last_depart + TAPAS_EXTRA_TIME,
                       addOpt, options.phemlight_path
                       )
        )

    oneshotcfg = abspath_in_dir(oneshot_dir, '%s.sumocfg' % suffix)
    oneshot_emissions = abspath_in_dir(oneshot_dir, 'emissions_%s.xml' % suffix)
    with working_dir(oneshot_dir):
        with open(additional[1], 'w') as f:
            f.write('<additional>\n    <edgeData id="dump" freq="%s" file="%s" excludeEmpty="true" minSamples="1"/>\n' %
                    (aggregation, oneshot_weights))
#            f.write('    <edgeData type="emissions" id="dump_emission" freq="%s" file="%s" excludeEmpty="true" minSamples="1"/>\n' %
#                    (aggregation, oneshot_emissions))
            f.write('</additional>\n')
        subprocess.check_call(
            [sumolib.checkBinary('sumo'), "-c", tempcfg, "--save-configuration", oneshotcfg] + extra_opt)
        os.remove(tempcfg)
        subprocess.check_call(
            [sumolib.checkBinary('sumo'), "-c", oneshotcfg, "-v"])
    return oneshot_routes, oneshot_weights


@benchmark
def run_bulk(options, first_depart, last_depart, trip_file, weight_file):
    base = trip_file[:-4]
    route_file = base + ".rou.xml"
    duarouter_args = [
        sumolib.checkBinary('duarouter'),
        '--net-file', options.net_file,
        '--trip-files', trip_file,
        '--additional-files', options.vtype_file,
        '--routing-algorithm', 'astar',
        '--routing-threads', '8',
        '--bulk-routing',
        '--output', route_file,
        '--ignore-errors',
        '--verbose'
    ]
    if weight_file is None:
        print("computing routes for all TAZ-pairs within the empty network")
    else:
        print("computing routes for all TAZ-pairs using weights from %s" %
              weight_file)
        duarouter_args += ['--weights', weight_file]
    with open(base + '.log', 'w') as f:
        subprocess.check_call(duarouter_args, stderr=f, stdout=f)
    return base + ".rou.alt.xml", weight_file


@benchmark
def run_marouter(options, first_depart, last_depart, trip_file, weight_file):
    aggregation = 1800
    begin = (int(first_depart) / aggregation) * aggregation
    marouter_dir = os.path.join(options.iteration_dir, 'marouter')
    if not os.path.exists(marouter_dir):
        os.makedirs(marouter_dir)
    marocfg = abspath_in_dir(marouter_dir, 'tapas.marocfg')
    ma_routes = abspath_in_dir(marouter_dir, 'ma_flows.rou.xml')
    ma_weights = abspath_in_dir(marouter_dir, 'ma_weights.xml')
    with open(marocfg, 'w') as f:
        f.write("""<configuration>
    <net-file value="%s"/>
    <route-files value="%s"/>
    <additional-files value="%s"/>
    <taz-param value="taz_id_start,taz_id_end"/>

    <output value="%s"/>
    <netload-output value="%s"/>
    <log-file value="marouter.log"/>
    <ignore-errors value="true"/>

    <routing-algorithm value="astar"/>
    <routing-threads value="16"/>
    <max-iterations value="5"/>

    <begin value="%s"/>
    <end value="%s"/>
</configuration>""" % (options.net_file, trip_file,
                       options.taz_file, ma_routes, ma_weights,
                       begin, last_depart + TAPAS_EXTRA_TIME)
        )

    with working_dir(marouter_dir):
        subprocess.check_call([sumolib.checkBinary('marouter'), "-c", marocfg, "-v"])
    return ma_routes, ma_weights


@benchmark
def run_sumo(options, first_depart, last_depart, trip_file, weight_file, meso=True):
    output_dir = options.iteration_dir
    suffix = "sim_meso" if meso else "sim_micro"
    sim_routes = abspath_in_dir(
        output_dir, 'vehroutes_%s.rou.xml' % suffix)
    sim_weights = abspath_in_dir(output_dir, 'aggregated_%s.xml' % suffix)
    aggregation = 1800
    begin = (int(first_depart) / aggregation) * aggregation
    additional = [options.vtype_file, 'dump_' + suffix + '.xml']
    offsetFile = os.path.join(os.path.dirname(options.vtype_file), 'tlsOffsets.add.xml')
    if os.path.exists(offsetFile):
        additional.append(offsetFile)

    sumocfg = abspath_in_dir(output_dir, '%s.sumocfg' % suffix)
    with open(sumocfg, 'w') as f:
        f.write(
            """<configuration>
        <net-file value="%s"/>
        <route-files value="%s"/>
        <additional-files value="%s"/>

        <device.taxi.dispatch-algorithm value="greedyShared"/>

        <vehroute-output value="%s"/>
        <vehroute-output.sorted value="true"/>
        <vehroute-output.last-route value="true"/>
        <vehroute-output.intended-depart value="true"/>
        <vehroute-output.route-length value="true"/>
        <vehroute-output.exit-times value="true"/>

        <no-step-log value="true"/>
        <log-file value="%s.sumo.log"/>
        <ignore-route-errors value="true"/>

        <begin value="%s"/>
        <end value="%s"/>
        <time-to-teleport value="60"/>
        <mesosim value="%s"/>
        <meso-recheck value="10"/>
        <meso-multi-queue value="true"/>
        <meso-junction-control.limited value="true"/>
        <meso-minor-penalty value="0.5"/>
        <meso-tls-penalty value="1.0"/>
</configuration>""" % (options.net_file, trip_file,
                       ','.join(additional),
                       sim_routes, suffix,
                       begin, last_depart + TAPAS_EXTRA_TIME,
                       meso
                       )
        )

    with working_dir(output_dir):
        with open(additional[1], 'w') as f:
            f.write('<a>\n    <edgeData id="dump" freq="%s" file="%s" excludeEmpty="true" minSamples="1"/>\n</a>' %
                    (aggregation, sim_weights))
        subprocess.check_call(
            [sumolib.checkBinary('sumo'), "-c", sumocfg, "-v"])
    return sim_routes, sim_weights


def run_default(options, first_depart, last_depart, routes, weights):
    if "marouter" in options.assignment:
        routes, weights = run_marouter(options, first_depart, last_depart, routes, weights)
    if "oneshot" in options.assignment:
        routes, weights = run_oneshot(options, first_depart, last_depart, routes, weights)
    if "gawron" in options.assignment:
        routes, weights = run_duaiterate(options, first_depart, last_depart, routes, weights)
    if "marouter" == options.assignment:
        routes, weights = run_sumo(options, first_depart, last_depart, routes, weights)
    return routes, weights


def run_subnet(options, first_depart, last_depart, routes, weights, subnet_file):
    tmpRoutes = routes[:-4] + "_cut_tmp.xml"
    cutOpts = [subnet_file, routes, "--orig-net", options.net_file, "-b", "-o", tmpRoutes]
    ptFiles = sorted(glob.glob(os.path.join(os.path.dirname(subnet_file), "pt*")))
    if ptFiles:
        routePrefix = os.path.join(os.path.dirname(routes), "pt")
        cutOpts += ["-a", ptFiles[1], "--pt-input", ptFiles[2], "--pt-output", routePrefix + "_vehicles.add.xml", "--stops-output", routePrefix + "_stops.add.xml"]
    cutRoutes.main(cutRoutes.get_options(cutOpts))
    with open(tmpRoutes) as routeIn, open(routes[:-4] + "_cut.xml", 'w') as routeOut:
        for line in routeIn:
            routeOut.write(line.replace('<vehicle', '<vehicle departLane="best" departSpeed="max"'))
    routes = os.path.abspath(routeOut.name)
    subOpt = copy.copy(options)
    subOpt.net_file = os.path.abspath(subnet_file)
    subnet = os.path.basename(subnet_file)[:-8]
    subOpt.bidi_taz_file = subOpt.net_file[:-8] + '_bidi.taz.xml'
    subOpt.vtype_file = subOpt.net_file[:-8] + '_vtypes.xml'
    if ptFiles:
        subOpt.vtype_file += "," + os.path.abspath(ptFiles[0])
    subOpt.background_trips = ""
#    addOpt = "--max-depart-delay 1 --max-num-vehicles 9000 --device.rerouting.adaptation-steps 360 --device.rerouting.probability 0.6 "
    addOpt = "--max-depart-delay 1 --device.rerouting.probability 0.6 "
    if "oneshot" in options.assignment:
        routes, weights = run_oneshot(subOpt, first_depart, last_depart, routes, weights, False, addOpt)
    if "gawron" in options.assignment:
        routes, weights = run_duaiterate(subOpt, first_depart, last_depart, routes, weights, False)
    return routes, weights
