#!/usr/bin/env python
"""
@file    import_navteq.py
@author  Jakob.Erdmann@dlr.de
@author  Michael.Behrisch@dlr.de
@date    2013-12-15
@version $Id: import_navteq.py 8059 2019-11-13 07:20:49Z behr_mi $

create a SUMO network from NavTeQ input

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
import zipfile
import glob
import subprocess
from optparse import OptionParser

from common import ensure_dir
from constants import SVC

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:   
    sys.exit("please declare environment variable 'SUMO_HOME'")

import sumolib
from sumolib.miscutils import benchmark


def get_options(args):
    optParser = OptionParser()

    optParser.add_option("--output-dir", "-o", default="output",
                         help="directory to keep all net related output")
    optParser.add_option("--net-prefix", default='net',
                         help="specify the prefix for the unaltered net file")
    optParser.add_option("--config", "-c", default='template_gen.netccfg',
                         help="netconvert configs to run")
    optParser.add_option("--verbose", "-v", action="store_true", default=False,
                         help="be verbose")

    options, remaining_args = optParser.parse_args(args=args)
    if len(remaining_args) < 1:
        sys.exit('mandatory argument: <navteq-prefix>')

    #######
    # what is the navteq prefix
    # when generating GDF files, containing all network data,
    # every file is prefixed with this navteq prefix,
    # the prefix must be known for handling the files for import

    # get navteq prefix, eventually extract 7z or zip file
    options.prefix_raw = remaining_args[0]
    options.unpack_dir_navteq = os.path.dirname(options.prefix_raw)

    # maybe unzip a zip file, and derive navteq-prefix
    if options.prefix_raw.endswith('.zip'):
        netZip = zipfile.ZipFile(options.prefix_raw)
        netZip.extractall(options.unpack_dir_navteq)
        for f in netZip.namelist():
            if '_links_unsplitted.txt' in f:
                options.prefix = os.path.join(options.unpack_dir_navteq, f[:f.index('_links_unsplitted.txt')])
                break
    else:
        options.prefix = options.prefix_raw

    options.netfile = os.path.join(options.output_dir, "%s.net.xml" % options.net_prefix)

    return options


@benchmark
def importNavteq(options):
    ensure_dir(options.output_dir)
    netconvert = sumolib.checkBinary('netconvert')
    polyconvert = sumolib.checkBinary('polyconvert')

    for idx, config in enumerate(options.config.split(",")):
        netconvert_call = [netconvert, '--aggregate-warnings', '5', '--output-file', options.netfile, '-c', config]
        if idx > 0:
            tmp_net = os.path.join(
                options.output_dir, options.net_prefix + "_tmp.net.xml")
            os.rename(options.netfile, tmp_net)
            netconvert_call += ['--sumo-net-file', tmp_net]
        else:
            netconvert_call += ['--dlr-navteq', options.prefix]
        if options.verbose:
            print(' '.join(netconvert_call))
            sys.stdout.flush()
        subprocess.call(netconvert_call)

    polyconvertCmd = [
        polyconvert,
        '--verbose',
        '--dlr-navteq-poly-files', options.prefix + '_polygons.txt',
        #'--dlr-navteq-poi-files', options.prefix + '_points_of_interest.txt',
        '--output', os.path.join(options.output_dir, "shapes.xml"),
        '-n', options.netfile
    ]
    if options.verbose:
        print(polyconvertCmd)
        sys.stdout.flush()
    subprocess.call(polyconvertCmd)


@benchmark
def main():
    options = get_options(sys.argv[1:])
    importNavteq(options)

if __name__ == "__main__":
    main()
