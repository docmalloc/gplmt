#!/usr/bin/env python
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
#    Free Software Foundation, Inc., 59 Temple Place - Suite 330,
#    Boston, MA 02111-1307, USA.
#
# GNUnet Planetlab deployment and automation toolset 
#
# Main file

# Checking dependencies
# ElementTree XML Parser
import sys
import getopt, getpass

try: 
    from elementtree import ElementTree
    elementtree_loaded = True 
except ImportError: 
    elementtree_loaded = False
try:
    import paramiko
    paramiko_loaded = True 
except ImportError: 
    paramiko_loaded = False 
try:
    import minixsv
    minixsv_loaded = True 
except ImportError: 
    minixsv_loaded = False 
try:
    import gplmt.Targets as Targets
    import gplmt.Util as Util
    import gplmt.Configuration as Configuration
    import gplmt.Nodes as Nodes
    import gplmt.Tasks as Tasklist
    import gplmt.Worker as Worker
    import gplmt.Notifications as Notifications
except ImportError as e: 
    print "That's a bug! please check README: '" +  __file__+ "' " + str (e)
    imports = False
    


def main():
    global main
    tasks_file = None
    single_host = None
    nodes_file = None
    pl_password = None
    config_file = None    
    verbose = False
    command = None
    startid = -1
    target = Targets.Target (Targets.Target.undefined)
    undefined_target = Targets.Target(Targets.Target.undefined)
    try:
        main = Main ()
        
    # Init
    # Check dependencies 
        if (False == elementtree_loaded):
            print "ElementTree XML parsing module is required for execution, please check README"
            sys.exit(2)
        if (False == paramiko_loaded):
            print "paramiko SSH module is required for execution, please check README"
            sys.exit(2)
        if (False == minixsv_loaded):
            print "minixsv module is required for execution, please check README"
            sys.exit(2)       
        
    # Parse command line arguments
        try:
            opts, args = getopt.getopt(sys.argv[1:], "C:hvVc:n:l:t:ap:s:H:", ["help", "verbose", "config=", "nodes=", "tasklist=", "command=", "all", "password", "startid", "host"])
        except getopt.GetoptError, err:
            # print help information and exit:
            print str(err) # will print something like "option -a not recognized"
            usage()
            sys.exit(2)
        for o, a in opts:
            if o in ("-V", "--verbose"):
                verbose = True
            elif o in ("-h", "--help"):
                usage()
                sys.exit()
            elif o in ("-c", "--config"):
                config_file = Util.handle_filename(a)
            elif o in ("-H", "--host"):
                single_host = a                     
            elif o in ("-n", "--nodes"):
                nodes_file = Util.handle_filename(a)
            elif o in ("-t", "--target"):
                target = Targets.Target.create(a)
            elif o in ("-l", "--tasklist"):
                tasks_file = Util.handle_filename(a)
            elif o in ("-p", "--password"):
                pl_password = a
            elif o in ("-C", "--command"):
                command = a                
            elif o in ("-s", "--startid"):
                startid = a                                        
            else:
                print "Unknown argument '" +str(o)+ "'"
                usage()
                sys.exit()
    
        if (verbose == True):
            main.gplmt_logger = Util.Logger (True)
        else:
            main.gplmt_logger = Util.Logger (False)
            
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

# Clean up


# ---------------------------------------------------

def usage():
    print "GNUnet PlanetLab deployment and automation toolset\n\
Arguments mandatory for long options are also mandatory for short options.\n\
  -c, --config=FILENAME      use configuration file FILENAME\n\
  -n, --nodes=FILENAME       use node file FILENAME\n\
  -l, --tasks=FILENAME       use tasks file FILENAME\n\
  -t, --target=TARGET        TARGET={local|remote_ssh|planetlab}\n\
  -C, --command=             run single commandgplmt_taskfile of taskfile, print output using -v\n\
  -a, --all                  use all nodes assigned to PlanetLab slice instead of nodes file\n\
  -p, --password             password to access PlanetLab API\n\
  -H, --host                 run tasklist on given host\n\
  -s, --startid              start with this task id \n\
  -h, --help                 print this help\n\
  -V, --verbose              be verbose \n\
Report bugs to gnunet-developers@gnu.org. \n\
GNUnet home page: http://www.gnu.org/software/gnunet/ \n\
General help using GNU software: http://www.gnu.org/gethelp/"

class Main:
    gplmt_logger = None;
    def __init__(self):
        self.verbose = False;
        
if __name__ == "__main__":
    main() 
