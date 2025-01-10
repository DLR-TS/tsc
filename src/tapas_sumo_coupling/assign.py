# Copyright (C) 2013-2022 German Aerospace Center (DLR) and others.
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

from tapas_sumo_coupling.common import abspath_in_dir
from tapas_sumo_coupling.constants import TAPAS_EXTRA_TIME

@benchmark
def run_duaiterate(options, first_depart, last_depart, trip_file, weight_file, meso=True):
    dua_dir = os.path.join(options.iteration_dir, 'dua')
    if not os.path.exists(dua_dir):
        os.makedirs(dua_dir)

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
            'sumo--meso-jam-threshold=-1',  # edge speed specific threshold
            'sumo--meso-junction-control.limited',
        ]
    params += [
        # city traffic has shorter headways than highway traffic...
        'sumo--max-depart-delay', '300',
        'duarouter--additional-files', ','.join(additional),
        'duarouter--vtype-output', '/dev/null',
        'duarouter--routing-threads', '16',
    ]
    with open(abspath_in_dir(dua_dir, 'duaIterate.cfg'), 'w') as f:
        print(duaIterate.initOptions().parse_args(args=params).config_as_string, file=f)

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
    if os.path.exists(oneshot_routes) and options.resume:
        print("Route file", oneshot_routes, "exists! Skipping assignment.")
        return oneshot_routes, oneshot_weights
    aggregation = 1800
    begin = (int(first_depart) / aggregation) * aggregation
    additional = [options.vtype_file, 'dump_' + suffix + '.xml']
    if options.bidi_taz_file:
        additional.append(options.bidi_taz_file)
    base_dir = os.path.dirname(options.net_file)
    if not meso:
        for add in (os.path.join(base_dir, 'tlsOffsets.add.xml'),
                    os.path.join(oneshot_dir, 'vehroutes_%s_tls.add.xml' % suffix)):
            if os.path.exists(add):
                additional.append(add)
    extra_opt = addOpt.split()
    extra_cfg = os.path.join(base_dir, 'extra.params')
    if os.path.exists(extra_cfg):
        extra_opt += open(extra_cfg).read().split()
    trips = [trip_file]
    if os.path.exists(options.background_trips):
        trips.append(options.background_trips)
        additional.append(glob.glob(os.path.join(base_dir, 'suburb.taz.xml*'))[0])
    specificPT = glob.glob(abspath_in_dir(oneshot_dir, 'pt*.xml*'))
    additional += sorted(specificPT if specificPT else glob.glob(os.path.join(base_dir, 'pt*.xml*')))
    additional += sorted(glob.glob(os.path.join(base_dir, 'fleet*.xml*')), reverse=True)

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
    if meso and os.path.exists(os.path.join(base_dir, "landmarks.csv.gz")):
        addOpt += """
        <astar.landmark-distances value="%s"/>""" % os.path.join(base_dir, "landmarks.csv.gz")
    if options.trip_emissions:
        addOpt += """
        <tripinfo-output value="%s"/>
        <device.emissions.probability value="1"/>""" % options.trip_emissions
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
        <time-to-teleport.ride value="3600"/>
        %s

</configuration>""" % (options.net_file, ",".join(trips),
                       ','.join(additional),
                       oneshot_routes, suffix,
                       begin, last_depart + TAPAS_EXTRA_TIME,
                       addOpt)
        )

    oneshotcfg = abspath_in_dir(oneshot_dir, '%s.sumocfg' % suffix)
    # oneshot_emissions = abspath_in_dir(oneshot_dir, 'emissions_%s.xml' % suffix)
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
    pt_files = list(sorted(glob.glob(os.path.join(os.path.dirname(options.net_file), 'pt*.xml*'))))
    input_files = [trip_file] + pt_files[-1:]
    route_file = base + ".rou.xml.gz"
    additional = [options.vtype_file] + pt_files[:-1]
    if options.bidi_taz_file:
        additional.append(options.bidi_taz_file)
    if os.path.exists(route_file) and options.resume:
        print("Route file", route_file, "exists! Skipping computation.")
        return route_file, weight_file
    duarouter_args = [
        sumolib.checkBinary('duarouter'),
        '--net-file', options.net_file,
        '--route-files', ",".join(input_files),
        '--additional-files', ",".join(additional),
        '--routing-algorithm', 'astar',
        '--routing-threads', '16',
        '--bulk-routing',
        '--output', route_file,
        '--alternatives-output', 'NUL',
        '--write-costs',
        '--route-length',
        '--ignore-errors',
        '--unsorted-input',
        '--verbose'
    ]
    if weight_file is None:
        print("computing routes for all TAZ-pairs within the empty network")
    else:
        print("computing routes for all TAZ-pairs using weights from %s" % weight_file)
        duarouter_args += ['--weights', os.path.abspath(weight_file)]
    subprocess.check_call(duarouter_args + ["--save-configuration", base + ".duarcfg"])
    with open(base + '.log', 'w') as f:
        subprocess.check_call([sumolib.checkBinary('duarouter'), base + ".duarcfg"], stderr=f, stdout=f)
    return route_file, weight_file


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
    ptFiles = sorted(glob.glob(os.path.join(os.path.dirname(subnet_file), "pt*.add.xml")))
    if ptFiles:
        vehicleFiles = ",".join([f for f in ptFiles if os.path.basename(f).startswith("pt_vehicles")])
        stopFiles = ",".join([f for f in ptFiles if f not in vehicleFiles])
        routePrefix = os.path.join(os.path.dirname(routes), "pt")
        cutOpts += ["-a", stopFiles, "--pt-input", vehicleFiles, "--pt-output", routePrefix + "_vehicles.add.xml", "--stops-output", routePrefix + "_stops.add.xml"]
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
    ptTypeFiles = glob.glob(os.path.join(os.path.dirname(subnet_file), "pt*types.xml"))
    if ptFiles and ptTypeFiles:
        subOpt.vtype_file += "," + os.path.abspath(ptTypeFiles[0])
    subOpt.background_trips = ""
#    addOpt = "--max-depart-delay 1 --max-num-vehicles 9000 --device.rerouting.adaptation-steps 360 --device.rerouting.probability 0.6 "
    addOpt = "--max-depart-delay 1 --device.rerouting.probability 0.6 "
    if "oneshot" in options.assignment:
        routes, weights = run_oneshot(subOpt, first_depart, last_depart, routes, weights, False, addOpt)
    if "gawron" in options.assignment:
        routes, weights = run_duaiterate(subOpt, first_depart, last_depart, routes, weights, False)
    return routes, weights
