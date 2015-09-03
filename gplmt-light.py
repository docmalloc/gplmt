#!/usr/bin/env python3
#
#  gplmt-light, a lightweight distributed testbed controller
#  Copyright (C) 2015  Florian Dold
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#


import argparse
import sys
from lxml.etree import parse
from gplmtlib import process_includes, Workers

parser = argparse.ArgumentParser()
parser.add_argument(
    "experiment_file", help="experiment description XML file")

args = parser.parse_args()

try:
    document = parse(args.experiment_file)
except OSError:
    print("Fatal: could not load experiment file", file=sys.stderr)
    sys.exit(1)

root = document.getroot()

if root.tag != "experiment":
    print("Fatal: Root element must be 'experiment', not '%s'" % (root.tag,))
    sys.exit(1)

process_includes(root)

targets = root.find('targets')

scheduler = Scheduler(targets)

steps = root.find("steps")

if steps is None:
    print("Warning: Nothing to do (no steps defined)")
    sys.exit(2)

def run_steps(steps):
    for child in steps:
        if child.tag == "synchronize":
            workers.join()
            continue
        if child.tag == "repeat":
            print("Warning: Repeat not implemented, skipping")
            continue
        if child.tag == "start-tasklist":
            targets_def = child.get("targets")
            if targets_def is None:
                print("Warning: start-tasklist has no targets, skipping")
                continue
            targets = targets_def.split(" \t,")
            # TODO: acquire task list
            task = ...
            for target in targets:
                scheduler.schedule(target, task)
            continue
        print("Fatal: Unexpected step '%s'" % (child.tag,))
    workers.join()

run_steps(steps)


