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
import asyncio
import sys
import lxml.etree
from lxml.etree import parse
from gplmtlib import *
from copy import deepcopy
import logging

parser = argparse.ArgumentParser()
parser.add_argument(
    "experiment_file", help="experiment description XML file")
parser.add_argument(
    "--dry", "-d", help="do a dry run")
parser.add_argument(
    "--batch", help="disable all interaction (e.g. password prompts)")
parser.add_argument(
    "--logroot-dir", help="Root directory for logs, will be created if necessary")
parser.add_argument(
    "--ssh-cooldown",
    default=1.0,
    help="Number of seconds to wait between ssh connections")
parser.add_argument(
    "--ssh-parallelism",
    default=30,
    help="Maximum number of concurrently opened ssh connections")

args = parser.parse_args()

logging.basicConfig(
            format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %T %Z',
        level=logging.INFO)

try:
    document = parse(args.experiment_file)
except OSError:
    print("Fatal: could not load experiment file", file=sys.stderr)
    sys.exit(1)

root = document.getroot()

if root.tag != "experiment":
    print("Fatal: Root element must be 'experiment', not '%s'" % (root.tag,))
    sys.exit(1)

process_includes(document, parent_filename=args.experiment_file)
ensure_names(document)

targets = document.findall('/target')

testbed = Testbed(
        targets,
        batch=args.batch,
        dry=args.dry,
        logroot_dir=args.logroot_dir,
        ssh_parallelism=args.ssh_parallelism,
        ssh_cooldown=args.ssh_cooldown)

steps = root.find("steps")

if steps is None:
    print("Warning: Nothing to do (no steps defined)")
    sys.exit(2)

named_tasklists = {}

for x in document.xpath("/experiment/tasklist[@name]"):
    named_tasklists[x.get('name')] = x

def resolve_tasklist(el):
    refname = el.get('ref')
    if refname is not None:
        tl = named_tasklists.get(refname)
        if tl is None:
            raise Exception("tasklist '%s' not found" % (refname,))
    else:
        tl = lxml.etree.Element('tasklist')
        tl.extend(deepcopy(list(el)))
    return tl
    

def run_steps(steps):
    for child in steps:
        if child.tag == "synchronize":
            testbed.join_all()
            continue
        if child.tag == "repeat":
            logging.warn("Repeat not implemented, skipping")
            continue
        if child.tag == "start-tasklist":
            targets_def = child.get("targets")
            if targets_def is None:
                logging.warn("start-tasklist has no targets, skipping")
                continue
            targets = targets_def.split(" \t,")
            tasklist = resolve_tasklist(child)
            for target in targets:
                testbed.schedule(target, tasklist)
            continue
        if child.tag == "loop-counted":
            num_iter_attr = child.get("iterations")
            if num_iter_attr is None:
                logging.error("counted loop is missing attribute iterations, skipping")
                continue
            try:
                num_iter = int(num_iter_attr)
            except ValueError:
                logging.error("counted loop has malformed attribute iterations (%s), skipping", num_iter_attr)
                continue
            logging.info("Starting counted loop")
            for x in range(num_iter):
                run_steps(list(child))
                testbed.join_all()
            logging.info("Done with counted loop")
            continue
        logging.error("Unexpected step '%s'", child.tag)
    testbed.join_all()

try:
    run_steps(steps)
except ExperimentExecutionError as e:
    logging.error("Aborting experiment:  %s" % (e.message))

# Necessary due to http://bugs.python.org/issue23548
loop = asyncio.get_event_loop()
loop.close()

logging.info("Experiment finished")

