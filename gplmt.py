#!/usr/bin/env python3
#
#    This file is part of GNUnet.
#    (C) 2010 Christian Grothoff (and other contributing authors)
#
#    GNUnet is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published
#    by the Free Software Foundation; either version 2, or (at your
#    option) any later version.
#
#    GNUnet is distributed in the hope that it will be useful, but
#    WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#    General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with GNUnet; see the file COPYING.  If not, write to the
#    Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
#    Boston, MA 02110-1301, USA.

"""
GNUnet Planetlab deployment and automation toolset

Main file
"""

import argparse
import getopt
import getpass
import logging
import paramiko
import sys
from lxml.etree import ElementTree
from gplmt import Target
from gplmt import Configuration
from gplmt import Tasklist
from gplmt import Worker
from gplmt.util import *
from gplmt.notifications import *


description = "GNUnet PlanetLab deployment and automation toolset"
epilog = ("Report bugs to gnunet-developers@gnu.org. \n"
          "GNUnet home page: http://www.gnu.org/software/gnunet/ \n"
          "General help using GNU software: http://www.gnu.org/gethelp/")


parser = argparse.ArgumentParser(description=description, epilog=epilog)
parser.add_argument(
    '-c', '--config',
    help="use configuration file %(metavar)s",
    dest='config_file')
parser.add_argument(
    '-n', '--nodes',
    help="use nodes file %(metavar)s",
    dest='nodes_file')
parser.add_argument(
    '-l', '--tasks',
    help="use tasks file %(metavar)s",
    dest='tasks_file')
parser.add_argument(
    '-t', '--target',
    help="one of local, remote_ssh, planetlab",
    dest='target')
parser.add_argument(
    '-C', '--command',
    help="run single command",
    dest='command')
parser.add_argument(
    '-a', '--all',
    help="use all nodes assigned to PlanetLab slice instead of nodes file")
parser.add_argument(
    '-p', '--password',
    help="password to access PlanetLab API",
    dest='pl_password')
parser.add_argument(
    '-H', '--host',
    help="run tasklist on given host",
    dest='single_host')
parser.add_argument(
    '-s', '--startid',
    help="start with this task id",
    dest='startid')
parser.add_argument(
    '-v', '--verbose',
    help="be verbose",
    type=bool, dest='verbose')


def main():
    args = parser.parse_args()
    config = Configuration(args.config_file)
    config.upgrade("pl_password", args.pl_password)
    config.upgrade("gplmt_taskfile", args.tasks_file)
    config.upgrade("gplmt_nodesfile", args.nodes_file)

    if command is not None:
        print("Loading single command:", command)
        tasklist = Tasklist(config.gplmt_taskfile, startid, config)
        tasklist.load_singletask(command)
    elif configuration.gplmt_taskfile is not None:
        print("Loading task file : ", configuration.gplmt_taskfile)
        tasklist = Tasklist(configuration.gplmt_taskfile, main.gplmt_logger, startid, configuration)
        tasklist.load()
    else:
        print("No tasks or commands given!")
        sys.exit(2)

    if args.target == Target.undefined and tarklist.target == Target.undefined:
        print("No target to run on defined!")
        sys.exit(3)

    if args.target == Target.undefined and tasklist.target != Target.undefined:
        target = tasklist.target
    else:
        target = args.target
        print("Duplicate target to run on defined, command line wins!")

    print("Using target ", target)

    if target == Target.planetlab and configuration.pl_password is None:
        while configuration.pl_password is None or configuration.pl_password == "":
            configuration.pl_password = getpass.getpass("Please enter PlanetLab password: ")
            configuration.pl_password = configuration.pl_password.strip()
    if (single_host is None and
            configuration.gplmt_nodesfile is None and
            target != Target.planetlab):
        print("No nodes to use given!")
        sys.exit(4)

    # Use a single host
    if single_host is not None:
        logging.info("Using single node '%s'", single_host)
        nodes = Nodes.StringNodes(single_host, main.gplmt_logger)
        if not nodes.load():
            sys.exit(5)
    # Use a nodes file
    elif configuration.gplmt_nodesfile is not None:
        logging.info("Using node file '%s'", configuration.gplmt_nodesfile)
        nodes = Nodes(configuration.gplmt_nodesfile, main.gplmt_logger)
        if not nodes.load():
            sys.exit(7)
    elif target == Target.planetlab:
        # Load PlanetLab nodes
        main.gplmt_logger.log("Using PlanetLab nodes")
        nodes = Nodes.PlanetLabNodes(configuration, main.gplmt_logger)
        if (nodes.load() == False):
            sys.exit(6)
    else:
        print("No nodes file given!")
        sys.exit(8)

    # Set up notification
    if configuration.gplmt_notifications == 'simple':
        notifications = Notifications.SimpleNotification(main.gplmt_logger)
    elif (configuration.gplmt_notifications == 'result'):
        notifications = Notifications.TaskListResultNotification(main.gplmt_logger)
    else:
        notifications = Notifications.TaskListResultNotification(main.gplmt_logger)

    try:
        worker = Worker.Worker(configuration, target, nodes, tasklist, notifications)
        worker.start()
    except KeyboardInterrupt:
        print("Interrupt during execution, FIXME!")
        sys.exit(0)

if __name__ == '__main__':
    main()
