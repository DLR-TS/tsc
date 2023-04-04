#!/usr/bin/env python3

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

# @file    install_scenario_templates.py
# @author  Marek Heinrich
# @author  Michael Behrisch
# @date    2014-12-15

# Create a scenario template directory mainly by creating a network and copying files.
# Relies on a data directory which currently resides in the simo svn trunk/projects/tapas.

from __future__ import print_function
import os
import sys
import shutil
import glob
from xml.sax import parse

if 'SUMO_HOME' in os.environ:
    sys.path += [os.path.join(os.environ['SUMO_HOME'], 'tools'),
                 os.path.join(os.environ['SUMO_HOME'], 'tools', 'net'),
                 os.path.join(os.environ['SUMO_HOME'], 'tools', 'import', 'gtfs'),
                 os.path.join(os.environ['SUMO_HOME'], 'tools', 'import', 'osm')]
else:
    sys.exit("please declare environment variable 'SUMO_HOME'")
import sumolib  # noqa
import edgesInDistricts  # noqa
import generateBidiDistricts  # noqa
import gtfs2pt  # noqa
import osmTaxiStop  # noqa
import split_at_stops  # noqa

from tapas_sumo_coupling import database, import_navteq, get_germany_taz
from tapas_sumo_coupling.common import listdir_skip_hidden, call


def getOptions():
    argParser = sumolib.options.ArgumentParser()
    database.add_db_arguments(argParser)
    argParser.add_argument("--clean", action="store_true", default=False,
                           help="remove any old data before processing")
    argParser.add_argument("-v", "--verbose", action="store_true",
                           default=False, help="tell me what you are doing")
    argParser.add_argument("-p", "--pre", default=os.path.join(os.getcwd(), 'data'),
                           help="input directories with pre scenarios")
    argParser.add_argument("-t", "--templates", default=os.path.join(os.getcwd(), 'scenario_templates'),
                           help="output dir with scenario templates")
    argParser.add_argument("-s", "--scenarios",
                           help="only process selected scenarios")
    argParser.add_argument("-i", "--shape-id-column", default="*:NO,RBS_OD_ORT_1412:ORT,Berlin_1223:VBZ_ID",
                           help="name of the column in the shape files which contains the taz id")
    argParser.add_argument("--suburb-taz", default="suburb",
                           help="name of taz file for surrounding districts")
    argParser.add_argument("--landmarks", default="landmarks",
                           help="name of file listing landmark edges")
    argParser.add_argument("--no-network", action="store_true", default=False,
                           help="skip network building")
    argParser.add_argument("--osm-ptlines", action="store_true", default=False,
                           help="use osm information on public transport lines")
    return argParser.parse_args()


def evaluate_pre_scen(options):
    for p in options.pre.split(","):
        for d in sorted(listdir_skip_hidden(p)):
            if os.path.isdir(os.path.join(options.pre, d)):
                if options.scenarios is None or d in options.scenarios.split(","):
                    yield os.path.join(p, d)


def ensure_tmp(scenario_template_dir):
    tmp_output_dir = os.path.join(scenario_template_dir, 'tmp_output')
    if os.path.exists(tmp_output_dir):
        shutil.rmtree(tmp_output_dir)
    os.mkdir(tmp_output_dir)
    return tmp_output_dir


def get_symlink_dir(scenario_pre_dir, subdir):
    check_dir = os.path.join(scenario_pre_dir, subdir)
    if not os.path.isfile(check_dir):
        return check_dir
    with open(check_dir) as s:
        TSC_HOME = os.path.abspath(os.path.dirname(__file__))
        return os.path.join(scenario_pre_dir, s.read().strip().replace("$TSC_HOME", TSC_HOME))


def create_template_folder(scenario_pre_dir, options):
    scenario_name = os.path.basename(scenario_pre_dir)
    # create (template) subfolder in scenarios for the 'selected scenarios'
    if options.verbose:
        print("creating template dir for", scenario_name)
    # check if the directory is existing (which means there is old data)
    scenario_template_dir = os.path.join(options.templates, scenario_name)
    dir_exists = os.path.isdir(scenario_template_dir)
    if dir_exists:
        print("Warning! Folder '%s' does exist and may contain old data." % scenario_name)
    else:
        # make a new template folder
        os.makedirs(scenario_template_dir)
    log_dir = os.path.join(scenario_template_dir, "log")
    if not os.path.exists(log_dir):
        os.mkdir(log_dir)

    # copy static input such as vehicle types, edge lists and processing scripts
    for ff in sorted(listdir_skip_hidden(scenario_pre_dir)):
        if (ff[-3:] in ['.gz', 'xml', 'cfg'] and ff[:12] != 'template_gen') or ff == '__init__.py':
            print("copying %s" % ff)
            shutil.copyfile(os.path.join(scenario_pre_dir, ff), os.path.join(scenario_template_dir, ff))

    net_name = 'net.net.xml.gz'
    net_path = os.path.join(scenario_template_dir, net_name)
    generated = os.path.join(scenario_template_dir, "generated_nets.txt")
    if not options.no_network:
        # check for navteq-dlr or osm data
        navteq_dlr_dir = os.path.join(scenario_pre_dir, 'navteq-dlr')
        osm_dir = os.path.join(scenario_pre_dir, 'osm')

        if os.path.isfile(navteq_dlr_dir):
            # emulate symlink
            navteq_dlr_dir = os.path.join(options.pre, open(navteq_dlr_dir).read().strip())
        if os.path.isdir(navteq_dlr_dir) or os.path.isdir(osm_dir):
            tmp_output_dir = ensure_tmp(scenario_template_dir)

            if os.path.isdir(navteq_dlr_dir):
                # get the zip file containing the network
                zip_list = [ff for ff in listdir_skip_hidden(
                    navteq_dlr_dir) if ff[-4:] == '.zip']
                if len(zip_list) != 1:
                    print('could not determine which .zip file to use')
                    print(navteq_dlr_dir, ":  ", listdir_skip_hidden(navteq_dlr_dir))
                    return
                navteq_dlr_zip = os.path.join(navteq_dlr_dir, zip_list[0])

                print("starting to import navteq ...")
                configs = sorted(glob.glob(os.path.join(scenario_pre_dir, 'template_gen*.netccfg')))
                importOptions = import_navteq.get_options(
                    ['-c', ",".join(configs), '-o', tmp_output_dir, '-v', navteq_dlr_zip])
                import_navteq.importNavteq(importOptions)

            if os.path.isdir(osm_dir):
                print("starting to import osm ...")
                configs = sorted(glob.glob(os.path.join(scenario_pre_dir, 'template_gen*.netccfg')))
                netconvert = sumolib.checkBinary('netconvert')

                for idx, config in enumerate(configs):
                    netconvert_call = [netconvert, '-c', config,
                                       '--output-file', os.path.join(tmp_output_dir, '%s_net.net.xml.gz' % idx),
                                       '--log', os.path.join(log_dir, '%s.log' % os.path.basename(config)[:-8])]
                    if options.osm_ptlines:
                        netconvert_call += ['--ptstop-output', os.path.join(tmp_output_dir, '%s_stops.add.xml.gz' % idx),
                                            '--ptline-output', os.path.join(tmp_output_dir, '%s_ptlines.xml.gz' % idx)]
                    if idx > 0:
                        netconvert_call += ['--sumo-net-file', os.path.join(tmp_output_dir, '%s_net.net.xml.gz' % (idx-1))]
                        if options.osm_ptlines:
                            netconvert_call += ['--ptstop-files', os.path.join(tmp_output_dir, '%s_stops.add.xml.gz' % (idx-1)),
                                                '--ptline-files', os.path.join(tmp_output_dir, '%s_ptlines.xml.gz' % (idx-1))]
                    call(netconvert_call, options.verbose)

                poly_config = os.path.join(scenario_pre_dir, 'template_gen.polycfg')
                if os.path.isfile(poly_config):
                    call([sumolib.checkBinary('polyconvert'), '-c', poly_config,
                          '-o', os.path.join(scenario_template_dir, "shapes.xml"), '-v'], options.verbose)

            # find last files
            for root, _, files in os.walk(tmp_output_dir):
                final_files = [file_name for file_name in files if file_name.split('_')[0] == str(idx)]
                for file_name in final_files:
                    dest_file = os.path.join(scenario_template_dir, file_name.split('_')[1])
                    if os.path.exists(dest_file):  # we need this for windows only
                        os.remove(dest_file)
                    os.rename(os.path.join(root, file_name), dest_file)

            shutil.rmtree(tmp_output_dir)
    setup_file = os.path.join(scenario_pre_dir, 'setup.py')
    if os.path.exists(setup_file):
        call([sys.executable, setup_file, scenario_pre_dir, scenario_template_dir], options.verbose)
    if not os.path.exists(net_path) and not os.path.exists(generated):
        print("Could not find network '%s' for %s, cleaning up!" % (net_path, scenario_name))
        if not dir_exists:
            shutil.rmtree(scenario_template_dir)
        return
    if os.path.exists(generated):
        with open(generated) as netlist:
            net_files = [os.path.join(scenario_template_dir, n.strip()) for n in netlist.readlines()]
    else:
        net_files = [net_path]
    for net_file in net_files:
        build_gtfs(get_symlink_dir(scenario_pre_dir, 'gtfs'), net_file, options.verbose)
        build_fleet(osm_dir, net_file, options.verbose)
        build_taz_etc(scenario_pre_dir, net_file, options)


def build_gtfs(gtfs_dir, net_path, verbose):
    scenario_template_dir = os.path.dirname(net_path)
    log_dir = os.path.join(scenario_template_dir, "log")
    if os.path.isdir(gtfs_dir):
        if verbose:
            print("calling gtfs2pt")
        tmp_output_dir = ensure_tmp(scenario_template_dir)
        for cfg in glob.glob(os.path.join(gtfs_dir, "*.cfg")):
            gtfs_call = ['-c', cfg, '-n', os.path.abspath(net_path),
                         '--additional-output', os.path.join(tmp_output_dir, 'pt_stops.add.xml.gz'),
                         '--route-output', os.path.join(tmp_output_dir, 'pt_vehicles.add.xml.gz'),
                         '--map-output', os.path.join(tmp_output_dir, 'output'),
                         '--network-split', os.path.join(tmp_output_dir, 'resources'),
                         '--fcd', os.path.join(tmp_output_dir, 'fcd'),
                         '--gpsdat', os.path.join(tmp_output_dir, 'gpsdat'),
                         '--vtype-output', os.path.join(tmp_output_dir, 'vType.xml')]
            if glob.glob(os.path.join(scenario_template_dir, 'ptlines*')):
                # if routes from osm
                osm_routes = glob.glob(os.path.join(scenario_template_dir, 'ptlines*'))[0]
                gtfs_call += ['--osm-routes', osm_routes, '--repair',
                              '--dua-repair-output', os.path.join(log_dir, 'repair_errors.txt'),
                              '--warning-output',  os.path.join(log_dir, 'missing.xml')]
            gtfs2pt.main(gtfs2pt.get_options(gtfs_call))
            tmp_net = os.path.join(tmp_output_dir, os.path.basename(net_path))
            os.rename(os.path.abspath(net_path), tmp_net)
            split_call = ['-n', tmp_net,
                         '-r', os.path.join(tmp_output_dir, 'pt_vehicles.add.xml.gz'),
                         '--split-output', os.path.join(tmp_output_dir, 'splits.edg.xml'),
                         '--stop-output', os.path.join(scenario_template_dir, 'pt_stops.add.xml.gz'),
                         '--route-output', os.path.join(scenario_template_dir, 'pt_vehicles.add.xml.gz'),
                         '-o', os.path.abspath(net_path),
                         os.path.join(tmp_output_dir, 'pt_stops.add.xml.gz')]
            split_at_stops.main(split_at_stops.get_options(split_call))
        shutil.rmtree(tmp_output_dir)


def build_fleet(osm_dir, net_path, verbose):
    scenario_template_dir = os.path.dirname(net_path)
    osmInput = glob.glob(os.path.join(osm_dir, "*.osm.xml*"))
    if osmInput:
        if verbose:
            print("importing taxi stops from", osmInput[0])
        osmTaxiStop.main(osmTaxiStop.parseArgs(["-s", osmInput[0], "-t", "busStop",
                                                "-n", os.path.abspath(net_path),
                                                "-o", os.path.join(scenario_template_dir, "fleet_stops.add.xml"),
                                                "-f", os.path.join(scenario_template_dir, "fleet.add.xml")]))


def build_taz_etc(scenario_pre_dir, net_path, options):
    scenario_template_dir = os.path.dirname(net_path)
    # generate bidi taz
    net = None
    bidi_path = os.path.join(scenario_template_dir, "bidi.taz.xml.gz")
    if not os.path.exists(bidi_path) or os.path.getmtime(bidi_path) < os.path.getmtime(net_path):
        if options.verbose:
            print("calling generateBidiDistricts.main %s, %s" % (net_path, bidi_path))
        net = generateBidiDistricts.main(net_path, bidi_path, 20., 500., True)
    add = bidi_path

    # check for shapes folder and import from shapes
    shapes_dir = get_symlink_dir(scenario_pre_dir, 'shapes')
    if os.path.isdir(shapes_dir):
        polyconvert = sumolib.checkBinary('polyconvert')
        idCol = dict([e.split(":") for e in options.shape_id_column.split(",")])
        for dbf in sorted(glob.glob(os.path.join(shapes_dir, "*.dbf"))):
            prefix = os.path.basename(dbf)[:-4]
            tazFile = os.path.join(scenario_template_dir, "districts.taz.xml.gz")
            if prefix in idCol:
                tazFile = os.path.join(scenario_template_dir, prefix + ".taz.xml.gz")
            if options.verbose:
                print("generating taz file %s" % tazFile)
            if not os.path.exists(tazFile) or os.path.getmtime(tazFile) < os.path.getmtime(net_path):
                if options.verbose:
                    print("importing shapes from %s ..." % dbf)
                polyReader = sumolib.shapes.polygon.PolygonReader(True)
                polyFile = os.path.join(scenario_template_dir, prefix + ".poly.xml.gz")
                call([polyconvert, "-n", net_path, "-o", polyFile,
                      "--shapefile-prefixes", os.path.join(shapes_dir, prefix),
                      "--shapefile.add-param", "--shapefile.traditional-axis-mapping",
                      "--shapefile.id-column", idCol.get(prefix, idCol["*"])], options.verbose)
                if options.verbose:
                    print("calculating contained edges for %s ..." % polyFile)
                parse(sumolib.openz(polyFile), polyReader)
                polys = polyReader.getPolygons()
                if net is None:
                    net = sumolib.net.readNet(net_path, withConnections=False, withFoes=False)
                eIDoptions, _ = edgesInDistricts.parse_args(["--assign-from", "--output", tazFile])
                reader = edgesInDistricts.DistrictEdgeComputer(net)
                reader.computeWithin(polys, eIDoptions)
                reader.writeResults(eIDoptions)

    if options.suburb_taz:
        tazFile = os.path.join(scenario_template_dir, options.suburb_taz + ".taz.xml.gz")
        if not os.path.exists(tazFile) or os.path.getmtime(tazFile) < os.path.getmtime(net_path):
            if options.verbose:
                print("generating taz file %s" % tazFile)
            polys = []
            if net is None:
                net = sumolib.net.readNet(net_path, withConnections=False, withFoes=False)
            for tazid, shapes in get_germany_taz.get_polys(options, net=net):
                for idx, shape in enumerate(shapes):
                    polys.append(sumolib.shapes.polygon.Polygon("%s:%s" % (tazid, idx), shape=shape))
            eIDoptions, _ = edgesInDistricts.parse_args(["--assign-from", "--output", tazFile, "--merge-separator", ":"])
            reader = edgesInDistricts.DistrictEdgeComputer(net)
            reader.computeWithin(polys, eIDoptions)
            reader.writeResults(eIDoptions)
        add += "," + tazFile
    lm = os.path.join(scenario_pre_dir, options.landmarks)
    if os.path.isfile(lm):
        landmarkFile = os.path.join(scenario_template_dir, "landmarks.csv.gz")
        if options.verbose:
            print("generating landmark file %s from %s" % (landmarkFile, lm))
        call([sumolib.checkBinary('duarouter'), "-n", net_path, "-a", add, "--astar.landmark-distances", lm,
              "--astar.save-landmark-distances", landmarkFile,
              "--routing-threads", "24", "-v",
              "-o", "NUL", "--ignore-errors", "--aggregate-warnings", "5"], options.verbose)
    else:
        print("could not find landmark data for %s" % scenario_template_dir)


def main():
    # generate scenario template folders from input-folders.
    # Each scenario has it's general data sorted
    # in an separate folder underneath pre_scen

    options = getOptions()

    if options.clean and os.path.exists(options.templates):
        print("removing templates %s" % options.templates)
        shutil.rmtree(options.templates)

    for path in evaluate_pre_scen(options):
        folder = os.path.basename(path)
        print("----- generating template %s" % folder)
        create_template_folder(path, options)
    if not os.path.exists(os.path.join(options.templates, "__init__.py")):
        open(os.path.join(options.templates, "__init__.py"), 'w').close()


if __name__ == "__main__":
    main()
