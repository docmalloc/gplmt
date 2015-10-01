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



experiment = Experiment.from_file(args.experiment_file, settings=args)
experiment.run()

