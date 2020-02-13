#!/usr/bin/env python
"""
@file    db_manipulator.py
@author  Marek.Heinrich@dlr.de
@author  Michael.Behrisch@dlr.de
@date    2014-12-15
@version $Id: db_manipulator.py 4618 2015-06-26 13:05:56Z behr_mi $

database methods for testing

Copyright (C) 2014-2015 DLR/TS, Germany
All rights reserved
"""

from __future__ import print_function
import sys
import subprocess
import time
from optparse import OptionParser

from get_trips import get_conn


def get_options():
    optParser = OptionParser()
    optParser.add_option(
        "-s", "--server", default='test', help="postgres server name")
    return optParser.parse_args()


def run_sql(conn, sql):
    cursor = conn.cursor()
    command = ""
    for line in sql:
        parts = line.upper().split()
        if len(parts) >= 3 and parts[0] == "--" and parts[1] == "SLEEP":
            conn.commit()
            time.sleep(float(parts[2]))
        else:
            command += " " + line.strip()
        if command.endswith(";"):
            command = command.strip()
            cursor.execute(command)
            if command.upper().startswith("SELECT"):
                for result in cursor:
                    print(result)
            command = ""
    if command:
        print("Warning: Unfinished command '%s'" % command)
    conn.commit()


def run_instructions(server, sqlList):
    conn_test = get_conn(server)
    for sql in sqlList:
        run_sql(conn_test, sql)
    conn_test.close()


def start(server, call, pre_test, par_test, post_test):
    if pre_test:
        print("running pre test instructions")
        run_instructions(server, pre_test)
    process_db_manipulator = None
    if par_test:
        # run as parallel process
        print("starting parallel test instructions")
        process_db_manipulator = multiprocessing.Process(
            target=run_instructions, args=(server, par_test))
        process_db_manipulator.start()
    print("starting main")
    sys.stdout.flush()
    subprocess.call(call, shell=True, stdout=sys.stdout, stderr=sys.stderr)
    sys.stdout.flush()
    sys.stderr.flush()
    if process_db_manipulator:
        print("waiting for parallel test")
        process_db_manipulator.join()
    if post_test:
        print("running post test instructions")
        run_instructions(server, post_test)


if __name__ == "__main__":
    options, args = get_options()
    # get connection to (test) db
    print('using server', options.server)
    conn = get_conn(options.server)

    for a in args:
        run_sql(conn, open(a))
    conn.close()
