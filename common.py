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

# @file    common.py
# @author  Jakob Erdmann
# @author  Michael Behrisch
# @date    2013-12-15

# common helper functions

from __future__ import print_function, division
import subprocess
import os
import csv

import constants


def abspath_in_dir(d, f):
    try:
        return os.path.abspath(os.path.join(d, f))
    except OSError:
        # getcwd (and thus abspath) can fail on cifs mounts, see https://bugs.python.org/issue17525
        return os.path.normpath(os.path.join(os.environ['PWD'], d, f))

def call(cmd):
    # ensure unix compatibility
    print(cmd)
    if isinstance(cmd, str):
        cmd = filter(lambda a: a != '', cmd.split(' '))
    subprocess.call(cmd)

def ensure_dir(dir):
    if not os.path.isdir(dir):
        os.mkdir(dir)


def listdir_skip_hidden(dir_path):
    assert os.path.isdir(dir_path), dir_path
    dir_list = [ff for ff in os.listdir(dir_path) if not ff[0] == '.']
    return dir_list


def chunked_sequence_generator(sequence, markerfunc, assertUniqe=False):
    initial_item = next(sequence)
    chunk = [initial_item]
    marker = markerfunc(initial_item)
    known_markers = set()

    for item in sequence:
        if markerfunc(item) == marker:
            chunk.append(item)
        else:
            yield marker, chunk
            known_markers.add(marker)
            chunk = [item]
            marker = markerfunc(item)
            if assertUniqe and marker in known_markers:
                raise Exception('Marker %s appears twice in in sequence %s (using markerfunc=%s).' % (
                    marker, sequence, markerfunc))
    yield marker, chunk


def csv_sequence_generator(csvfile, fields, assertUniqe=False):
    if type(fields) == str:
        fields = [fields]
    gen = chunked_sequence_generator(
        csv.DictReader(open(csvfile)),
        lambda row: tuple([row[f] for f in fields]),
        assertUniqe)
    for item in gen:
        yield item

def build_uid(row, clone_idx=0):
    # build unique id for each trip
    return '%s_%s_%s_%s' % (row[constants.TH.person_id], row[constants.TH.household_id], int(row[constants.TH.depart_minute]), clone_idx)

def parseTaz(moving):
    fromTaz = None
    toTaz = None
    if moving.param is not None:
        for p in moving.param:
            if p.key == "taz_id_start":
                fromTaz = int(p.value)
            if p.key == "taz_id_end":
                toTaz = int(p.value)
    if fromTaz is None:
        if moving.fromTaz is None:
            print(moving)
        fromTaz = int(moving.fromTaz)
    if toTaz is None:
        toTaz = int(moving.toTaz)
    return fromTaz, toTaz
