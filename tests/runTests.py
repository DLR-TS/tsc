#!/usr/bin/env python
# Eclipse SUMO, Simulation of Urban MObility; see https://eclipse.dev/sumo
# Copyright (C) 2008-2025 German Aerospace Center (DLR) and others.
# This program and the accompanying materials are made available under the
# terms of the Eclipse Public License 2.0 which is available at
# https://www.eclipse.org/legal/epl-2.0/
# This Source Code may also be made available under the following Secondary
# Licenses when the conditions for such availability set forth in the Eclipse
# Public License 2.0 are satisfied: GNU General Public License, version 2
# or later which is available at
# https://www.gnu.org/licenses/old-licenses/gpl-2.0-standalone.html
# SPDX-License-Identifier: EPL-2.0 OR GPL-2.0-or-later

# @file    runTests.py
# @author  Michael Behrisch
# @date    2012-03-29


import argparse
import glob
import logging
import os
import subprocess


def run(args):
    if type(args) is list:
        args = " ".join(args)
    env = os.environ
    root = os.path.abspath(os.path.dirname(__file__))
    for d in sorted(glob.glob(os.path.join(root, "*env", "*", "activate")) + glob.glob(os.path.join(root, "..", "*env", "*", "activate"))):
        env_dir = os.path.dirname(os.path.dirname(d))
        if env.get("VIRTUAL_ENV"):
            print("Virtual environment %s already active, ignoring %s." % (env["VIRTUAL_ENV"], env_dir))
        else:
            print("Using virtual environment %s." % env_dir)
            env["VIRTUAL_ENV"] = env_dir
            if os.name != "posix":
                env["PATH"] = "%s\\Scripts;%s" % (env_dir, env["PATH"])
            else:
                env["PATH"] = "%s/bin:%s" % (env_dir, env["PATH"])

    env["TEXTTEST_HOME"] = root
    env["TSC_HOME"] = os.path.join(root, "..")
    apps = "tsc,tsc.sqlite3"
    process = subprocess.Popen("%s %s -a %s" % ("texttest", args, apps), env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    with process.stdout:
        for line in process.stdout:
            logging.info(line)
    process.wait()


if __name__ == "__main__":
    optParser = argparse.ArgumentParser()
    options, args = optParser.parse_known_args()
    run(["-" + a for a in args])
