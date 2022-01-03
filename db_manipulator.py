#!/usr/bin/env python

# Copyright (C) 2014-2020 German Aerospace Center (DLR) and others.
# This program and the accompanying materials are made available under the
# terms of the Eclipse Public License 2.0 which is available at
# https://www.eclipse.org/legal/epl-2.0/
# This Source Code may also be made available under the following Secondary
# Licenses when the conditions for such availability set forth in the Eclipse
# Public License 2.0 are satisfied: GNU General Public License, version 2
# or later which is available at
# https://www.gnu.org/licenses/old-licenses/gpl-2.0-standalone.html
# SPDX-License-Identifier: EPL-2.0 OR GPL-2.0-or-later

# @file    db_manipulator.py
# @author  Marek Heinrich
# @author  Michael Behrisch
# @date    2014-12-15

# database methods for testing

from __future__ import print_function
import os
import sys
import subprocess
import multiprocessing
import time

import sqlite3
try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("Warning! Could not load psycopg2, postgres database operations won't work.", file=sys.stderr)

sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
from sumolib.options import ArgumentParser


def add_db_arguments(argParser):
    argParser.add_argument("--host", help="postgres server name or IP (or 'sqlite3' for a local sqlite database)")
    argParser.add_argument("--port", default=5432, type=int, help="postgres server port")
    argParser.add_argument("--user", help="postgres server credentials (username)")
    argParser.add_argument("--password", help="postgres server credentials")
    argParser.add_argument("--database", default="tapas", help="postgres server database name")
    argParser.add_argument("--read-only", action="store_true", default=False,
                           help="only read from the database but never write")


def get_conn(options_or_config_file, conn=None):
    try:
        conn.cursor()
        return conn
    except Exception:
        pass
    if isinstance(options_or_config_file, str):
        argParser = ArgumentParser()
        add_db_arguments(argParser)
        print("parsing", options_or_config_file)
        options = argParser.parse_args(["-c", options_or_config_file])
    else:
        options = options_or_config_file
    if options.host is None:
        return None
    if options.host == "sqlite3":
        conn = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
        sqlite3.register_adapter(bool, int)
        sqlite3.register_converter("boolean", lambda v: bool(int(v)))  # sqlite has no native boolean type and would return ints
        sqlite3.register_converter("double", lambda v: [float(t) for t in v[1:-1].split(b",")] if v[:1] == b"{" else float(v))  # sqlite has no native double[]
        try:
            conn.enable_load_extension(True)
            conn.execute("SELECT load_extension('mod_spatialite%s')" % ('.so' if os.name == "posix" else ''))
        except Exception as e:
            print("Warning! Could not load mod_spatialite, geometry related database operations won't work.", e, file=sys.stderr)
        database = options.database % os.environ
        conn.execute("ATTACH ? AS core", (os.path.join(os.path.dirname(database), 'core.db'),))
        conn.execute("ATTACH ? AS tmp", (os.path.join(os.path.dirname(database), 'tmp.db'),))  # 'temp' is already reserved in sqlite
        conn.execute("ATTACH ? AS public", (database,))  # attaching 'public' last makes it the default if name clashes should occur
        return conn
    try:
        conn = psycopg2.connect(host=options.host, port=options.port, user=options.user, password=options.password, database=options.database)
        conn.set_session(readonly=options.read_only)
        return conn
    except psycopg2.OperationalError as e:
        print(e, file=sys.stderr)
        return None


def table_exists(conn, table, schema="public"):
    cursor = conn.cursor()
    if isinstance(conn, sqlite3.Connection):
        cursor.execute("SELECT name FROM %s.sqlite_master WHERE type='table' AND name=?" % schema, (table,))
    else:
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND table_name=%s", (schema, table))
    return len(cursor.fetchall()) > 0


def check_schema_table(conn, schema, table):
    if isinstance(conn, sqlite3.Connection) and schema == 'temp':
        schema = 'tmp'
    return '.'.join((schema, table)), table, table_exists(conn, table, schema)


def execute(conn, command, parameters):
    cursor = conn.cursor()
    try:
        if not isinstance(conn, sqlite3.Connection):
            command = command.replace('?', '%s')
            if command.startswith("INSERT") and len(parameters) > 1000:
                psycopg2.extras.execute_values(cursor, command, parameters)
                conn.commit()
                return
        cursor.execute(command, parameters)
    except psycopg2.errors.ReadOnlySqlTransaction as e:
        print(e)
    conn.commit()


def run_sql(conn, sql):
    cursor = conn.cursor()
    command = ""
    for line in sql:
        if line.startswith("--"):
            parts = line.upper().split()
            if len(parts) >= 3:
                if parts[1] == "SLEEP":
                    conn.commit()
                    time.sleep(float(parts[2]))
                if parts[1] == "POSTGRESQL" and parts[2] == "EXIT":
                    if not isinstance(conn, sqlite3.Connection):
                        break
        else:
            if command:
                command += " "
            command += line.strip()
            if command.endswith(";"):
                command = command.strip()
                # print(command)
                sys.stdout.flush()
                cursor.execute(command)
                if command.upper().startswith("SELECT"):
                    for result in cursor:
                        print(result)
                command = ""
    if command:
        print("Warning: Unfinished command '%s'" % command)
    conn.commit()


def run_instructions(options, sqlList):
    conn_test = get_conn(options)
    try:
        for sql in sqlList:
            run_sql(conn_test, sql)
    except psycopg2.ProgrammingError as e:
        print(e, file=sys.stderr)
    conn_test.close()


def start(options, call, pre_test, par_test, post_test):
    if pre_test:
        print("running pre test instructions")
        run_instructions(options, pre_test)
    process_db_manipulator = None
    if par_test:
        # run as parallel process
        print("starting parallel test instructions")
        process_db_manipulator = multiprocessing.Process(
            target=run_instructions, args=(options, par_test))
        process_db_manipulator.start()
    print("starting main")
    sys.stdout.flush()
    subprocess.call(call)
    sys.stdout.flush()
    sys.stderr.flush()
    if process_db_manipulator:
        print("waiting for parallel test")
        process_db_manipulator.join()
    if post_test:
        print("running post test instructions")
        run_instructions(options, post_test)


if __name__ == "__main__":
    argParser = ArgumentParser()
    add_db_arguments(argParser)
    argParser.add_argument("sqlfile", nargs="*", help="SQL files to process")
    options = argParser.parse_args()
    # get connection to (test) db
    print('using server', options)
    run_instructions(options, [open(o) for o in options.sqlfile])
