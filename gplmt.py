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
import sys
import getopt, getpass
from elementtree import ElementTree
import paramiko
import minixsv
from gplmt import Targets
from gplmt import Util
from gplmt import Configuration
from gplmt import Tasks as Tasklist
from gplmt import Worker
from gplmt import Notifications

description = "GNUnet PlanetLab deployment and automation toolset"
epilog = ("Report bugs to gnunet-developers@gnu.org. \n"
          "GNUnet home page: http://www.gnu.org/software/gnunet/ \n"
          "General help using GNU software: http://www.gnu.org/gethelp/")


parser = argparse.ArgumentParser(description=description, epilog=epilog)
parser.add_argument(
    '-c', '--config', help="use configuration file %(metavar)s",
    dest='config_file')
parser.add_argument(
    '-n', '--nodes', help="use nodes file %(metavar)s",
    dest='nodes_file')
parser.add_argument(
    '-l', '--tasks', help="use tasks file %(metavar)s",
    dest='tasks_file')
parser.add_argument(
    '-t', '--target', help="one of local, remote_ssh, planetlab"
    dest='target')
parser.add_argument(
    '-C', '--command', help="run single command",
    dest='command')
parser.add_argument('-a', '--all', help="use all nodes assigned to PlanetLab slice instead of nodes file")
parser.add_argument(
    '-p', '--password', help="password to access PlanetLab API",
    dest='pl_password')
parser.add_argument(
    '-H', '--host', help="run tasklist on given host"
    dest='single_host')
parser.add_argument(
    '-s', '--startid', help="start with this task id",
    dest='startid')
parser.add_argument(
    '-v', '--verbose', help="be verbose", type=bool,
    dest='verbose')


def main():
        if (config_file != None):                            
            # Load configuration file
            configuration = Configuration.Configuration (config_file, main.gplmt_logger);
            if (configuration.load() == False):
                print "Failed to load configuration..."
                sys.exit(2)
        else:
            # Load default configuration file
            configuration = Configuration.Configuration (None, main.gplmt_logger);
            if (configuration.load() == False):
                print "Failed to load default configuration..."
                sys.exit(2)
                
        # Update configuration      
        if (None != pl_password):
            configuration.pl_password = pl_password
        if (None != tasks_file):
            configuration.gplmt_taskfile = tasks_file
        if (None != nodes_file):
            configuration.gplmt_nodesfile = nodes_file                        
        
    
        # Load gplmt_taskfile file
        if (None != command):
            print "Loading single command : " + str (command)
            tasklist = Tasklist.Tasklist (configuration.gplmt_taskfile, main.gplmt_logger, startid, configuration);
            tasklist.load_singletask(command, main.gplmt_logger)
        elif (configuration.gplmt_taskfile):      
            print "Loading task file : " + configuration.gplmt_taskfile          
            tasklist = Tasklist.Tasklist (configuration.gplmt_taskfile, main.gplmt_logger, startid, configuration);
            if (tasklist.load() == False):
                sys.exit(2)  
        else:
            print "No tasks given!"          
            sys.exit(2)  
             
        # Check target
        if ((target == undefined_target) and (tasklist.target == undefined_target)):  
            print "No target to run on defined!"
            return
        if ((target == undefined_target) and (tasklist.target != undefined_target)): 
                target = tasklist.target
        else:
            print "Duplicate target to run on defined, command line wins!" 
            
        print "Using target " +  str (target)       
        
        if (target == Targets.Target (Targets.Target.planetlab)):            
            if (configuration.pl_password == None):
                while ((configuration.pl_password == None) or (configuration.pl_password == "")):
                    print "Please enter PlanetLab password:"            
                    configuration.pl_password = getpass.getpass()
                    configuration.pl_password = configuration.pl_password.strip()              
    
        # Load hosts files: single host, nodes files, planetlab
        # command line beats configuration
        if ((None == single_host) and (None == configuration.gplmt_nodesfile) and
            (target != Targets.Target (Targets.Target.planetlab))):
            print "No nodes to use given!\n"
            usage()
            sys.exit(4)
            
        # Use a single host
        if (single_host != None):
            main.gplmt_logger.log ("Using single node '" + single_host + "'")
            nodes = Nodes.StringNodes (single_host, main.gplmt_logger)
            if (nodes.load() == False):
                sys.exit(5) 
        # Use a nodes file
        elif (None != configuration.gplmt_nodesfile):
            main.gplmt_logger.log ("Using node file '" + configuration.gplmt_nodesfile + "'")
            nodes = Nodes.Nodes (configuration.gplmt_nodesfile, main.gplmt_logger);
            if (nodes.load() == False):
                sys.exit(7)      
        elif (target == Targets.Target (Targets.Target.planetlab)):
            # Load PlanetLab nodes                
            main.gplmt_logger.log ("Using PlanetLab nodes")
            nodes = Nodes.PlanetLabNodes (configuration, main.gplmt_logger)
            if (nodes.load() == False):
                sys.exit(6)        
        else:
            print "No nodes file given!\n" 
            sys.exit(8)      
    
        # Set up notification
        if (configuration.gplmt_notifications == "simple"):
            notifications = Notifications.SimpleNotification (main.gplmt_logger)
        elif (configuration.gplmt_notifications == "result"):
            notifications = Notifications.TaskListResultNotification (main.gplmt_logger)
        else:
            notifications = Notifications.TaskListResultNotification (main.gplmt_logger)
    except KeyboardInterrupt:
        sys.exit(0)
# Start execution
    try:
        worker = Worker.Worker (main.gplmt_logger, configuration, target, nodes, tasklist, notifications)
        worker.start()
    except KeyboardInterrupt:
        print "Interrupt during execution, FIXME!"
        sys.exit(0)        

if __name__ == "__main__":
    main() 
