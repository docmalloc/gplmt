#!/usr/bin/env python
import sys, os, xmlrpclib, getopt, getpass, random


def usage():
    print "GNUnet PlanetLab deployment and automation toolset\n\
Arguments mandatory for long options are also mandatory for short options.\n\
  -c, --config=    configuration file\n\
  -p, --user=      Planetlab username\n\
  -p. --password=       Planetlab password\n\
  -s, --slice=       Planetlab slice\n\
  -n, --nodes=    Files containing nodes\n\
  -h, --help                 print this help\n\
  -o, --operation=  all,my,add_nodes_file, add_nodes_all, del_nodes_file, create_buildbot_cfg\n\
  \n\
  Parameters for buildbot configuration creation\n\
  -t, --template=    buildbot configuration template\n\
  -b, --bconfig      filename for resulting buildbot configuration\n\
  -r, --btask        filename for resulting tasklist\n\
  -w, --bcmd        buidlbot command to execute\n\
  Additional paramaters need to be configured in configuration file\n\
Report bugs to gnunet-developers@gnu.org. \n\
GNUnet home page: http://www.gnu.org/software/gnunet/ \n\
General help using GNU software: http://www.gnu.org/gethelp/"

# configuration
pl_user = None
pl_password = None
pl_slicename = None
cfgfile = None
nodesfile = None
op = None
bconfig = None
template = None
bb_task_file = None
bb_cmd = None

def parse_arg ():
    global cfgfile
    global pl_user
    global pl_password
    global pl_slicename
    global op
    global nodesfile
    global bconfig
    global template
    global bb_task_file
    global bb_cmd
    try:
        opts, args = getopt.getopt(sys.argv[1:], "w:r:b:hc:u:p:s:o:n:t:", ["bcmd=","btask=", "bconfig=","help", "config", "pl_user=", "pl_password=", "slice=", "operation=", "nodes=", "template"])
    except getopt.GetoptError, err:
        # print help information and exit:
        print str(err) # will print something like "option -a not recognized"
        usage()
        sys.exit(2)
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-u", "--pl_user"):
            pl_user = a
        elif o in ("-p", "--pl_password"):
            pl_password = a
        elif o in ("-c", "--config"):
            cfgfile = a          
        elif o in ("-s", "--slice"):
            pl_slicename = a
        elif o in ("-n", "--nodes"):
            nodesfile = a           
        elif o in ("-t", "--template"):
            template = a
        elif o in ("-b", "--bconfig"):
            bconfig = a
        elif o in ("-r", "--btask"):
            bb_task_file = a
        elif o in ("-w", "--bcmd"):
            bb_cmd = a                                          
                                                                                     
                                       
        elif o in ("-o", "--operation"):
            if (a == "all"):
                op = "all"
            elif (a == "my"):
                op = "my"
            elif (a == "add_nodes_file"):
                op = "add_nodes_file"
            elif (a == "add_nodes_all"):
                op = "add_nodes_all"
            elif (a == "del_nodes_file"):
                op = "del_nodes_file"
            elif (a == "create_buildbot_cfg"):
                op = "create_buildbot_cfg"                                                                                  
            else:
                usage()
                sys.exit()            
        else:
            assert False, "unhandled option"
            
def update_conf (configuration):
    global cfgfile
    global pl_user
    global pl_password
    global pl_slicename
    global op
    global nodesfile
    global bconfig
    global template
    global bb_task_file
    global bb_cmd
    if (None != pl_user):
        configuration.pl_user = pl_user
    if (None != pl_password):
        configuration.pl_password = pl_password
    if (None != pl_slicename):
        configuration.pl_slicename = pl_slicename
    if (None != pl_password):
        configuration.pl_password = pl_password
    if (None != template):
       configuration.bb_template = template
    if (None != bconfig):
       configuration.bb_result_cfg = bconfig     
    if (None != bb_task_file):
       configuration.bb_task_file = bb_task_file
    if (None != bb_cmd):
       configuration.bb_bb_cmd = bb_cmd                                                   

def load_nodes (filename):
    if (False == os.path.exists(filename)):
        return None
    fobj = open (filename, "r") 
    nodes = list()
    for line in fobj: 
        line = line.strip() 
        #print "Found node '" + line + "'"
        nodes.append(line)
    return nodes
    

def list_my_nodes (configuration):
    # PlanetLab XML RPC server
    server = xmlrpclib.ServerProxy(configuration.pl_api_url)
    # PlanetLab auth struct
    auth = {}
    auth['Username'] = configuration.pl_username
    auth['AuthString'] = configuration.pl_password
    auth['AuthMethod'] = "password"
    # PlanetLab Slice data
    slice_data = {}
    slice_data['name'] = configuration.pl_slicename
    
    # request nodes assigned to slice
    try:
        node_ids = server.GetSlices(auth, [slice_data['name']], ['node_ids'])[0]['node_ids']
        node_hostnames = [node['hostname'] for node in server.GetNodes(auth, node_ids, ['hostname'])]
    
        for node in node_hostnames:
            print node
    except Exception as e:
        print "Error while retrieving node list: " + str(e) 
    
def list_all_nodes (configuration):
    # PlanetLab XML RPC server
    server = xmlrpclib.ServerProxy(configuration.pl_api_url)
    # PlanetLab auth struct
    auth = {}
    auth['Username'] = configuration.pl_username
    auth['AuthString'] = configuration.pl_password
    auth['AuthMethod'] = "password"
    # PlanetLab Slice data
    slice_data = {}
    slice_data['name'] = configuration.pl_slicename
    
    # request all sites on PL
    try:
        sites = server.GetSites(auth,{},['site_id','name','latitude','longitude'])
        nsites = len(sites)
    except Exception as e:
        print "Error while retrieving site list: " + str(e)     
    # request all nodes on PL
    filter_dict = {"boot_state":"boot"}
    try:
        nodes = server.GetNodes(auth,filter_dict,['site_id','node_id','hostname','boot_state'])
        nnodes = len(nodes)
        for node in nodes:
            print node.get('hostname')
    except Exception as e:
        print "Error while retrieving node list: " + str(e) 
       
def add_to_nodes (configuration, nodes):
    server = xmlrpclib.ServerProxy(configuration.pl_api_url)
    # PlanetLab auth struct
    auth = {}
    auth['Username'] = configuration.pl_username
    auth['AuthString'] = configuration.pl_password
    auth['AuthMethod'] = "password"
    # PlanetLab Slice data
    slice_data = {}
    slice_data['name'] = configuration.pl_slicename
       
    # request nodes assigned to slice    
    try:
        res = server.AddSliceToNodes (auth, configuration.pl_slicename, nodes)
        if (res == 1):
            print "Added slice '" + configuration.pl_slicename+ "' to nodes :" + str(nodes)
            sys.stdout.flush()
        else: 
            print "Failed to add nodes " + str(nodes)
            sys.stdout.flush()
    except Exception as e:
        print "Failed to add node :" + str(e)
           
           
def add_to_all_nodes (configuration):
    server = xmlrpclib.ServerProxy(configuration.pl_api_url)
    # PlanetLab auth struct
    auth = {}
    auth['Username'] = configuration.pl_username
    auth['AuthString'] = configuration.pl_password
    auth['AuthMethod'] = "password"
    # PlanetLab Slice data
    slice_data = {}
    slice_data['name'] = configuration.pl_slicename
       
    # request all sites on PL
    try:
        sys.stdout.write('Retrieving PL sites list... ')
        sys.stdout.flush()
        sites = server.GetSites(auth,{},['site_id','name','latitude','longitude'])
        nsites = len(sites)
        sys.stdout.write('Received ' + str(nsites) + ' sites\n\n')
        sys.stdout.flush()
    except Exception as e:
        print "Error while retrieving sites list: " + str(e) 
    
    # request all nodes on PL
    sys.stdout.write('Retrieving PL nodes list for sites')
    sys.stdout.flush()
    filter_dict = {"boot_state":"boot"}
    try:
        nodes = server.GetNodes(auth,filter_dict,['site_id','node_id','hostname','boot_state'])
        nnodes = len(nodes)
        sys.stdout.write('... got ' +str(nnodes)+ ' nodes \n\n')
        node_str = list()
        for node in nodes:
            print node.get('hostname')            
            node_str.append(node.get('hostname'))
            res = server.AddSliceToNodes(auth, configuration.pl_slicename, node_str)
        if (res == 1):
            print 'Added slice ' + configuration.pl_slicename + "to nodes " + str(nodes)
            sys.stdout.flush()
        else:
            print "Failed to add nodes :" + str(nodes)+ " to slice " + configuration.pl_slicename            
    except Exception as e:
        print "Error while adding nodes to list: " + str(e) 
       
def del_nodes (configuration, nodes):
    server = xmlrpclib.ServerProxy(configuration.pl_api_url)
    # PlanetLab auth struct
    auth = {}
    auth['Username'] = configuration.pl_username
    auth['AuthString'] = configuration.pl_password
    auth['AuthMethod'] = "password"
    # PlanetLab Slice data
    slice_data = {}
    slice_data['name'] = configuration.pl_slicename
       
    # request nodes assigned to slice    
    try:
        res = server.DeleteSliceFromNodes (auth, configuration.pl_slicename, nodes)
        if (res == 1):
            print "Deleted nodes :" + str(nodes) + " from slice " + configuration.pl_slicename
            sys.stdout.flush()
        else:
            print "Failed to delete node :" + str(nodes)+ " from slice " + configuration.pl_slicename
    except Exception as e:
        print "Failed to delete node :" + str(e)+ " from slice " + configuration.pl_slicename
            
def create_buildbot_cfg (configuration):
    global nodesfile
    server = xmlrpclib.ServerProxy(configuration.pl_api_url)
    # PlanetLab auth struct
    auth = {}
    auth['Username'] = configuration.pl_username
    auth['AuthString'] = configuration.pl_password
    auth['AuthMethod'] = "password"
    # PlanetLab Slice data
    slice_data = {}
    slice_data['name'] = configuration.pl_slicename
    
    # Load nodes
    node_hostnames = []
    if (("" != configuration.pl_username) and 
        ("" != configuration.pl_password) and 
        ("" != configuration.pl_slicename) and 
        (None == nodesfile)):
        # Request nodes assigned to slice
        try:
            node_ids = server.GetSlices(auth, [slice_data['name']], ['node_ids'])[0]['node_ids']
            node_hostnames = [node['hostname'] for node in server.GetNodes(auth, node_ids, ['hostname'])]
        except Exception as e:
            print "Error while retrieving node list: " + str(e) 
            sys.exit (2)
    elif (None != nodesfile):
        # Use nodes files
        try:
            f = open (nodesfile, 'r')
        except IOError as e:
            print "Could not open node file: " + str(e) 
            sys.exit (2)        
        for line in f:
            node_hostnames.append(line)        
        f.close()
    else: 
        print "No node file or PlanetLab credentials given"
        sys.exit (2)

    if ("" == configuration.bb_template):
        print "No configuration template given"
        sys.exit (2)
    if ("" == configuration.bb_task_file):
        print "No file to store resulting tasks given"
        sys.exit (2)
    if ("" == configuration.bb_result_cfg):
        print "No file to store resulting configuration given"
        sys.exit (2)
    if ("" == configuration.bb_bb_cmd):
        print "No buildbot command given"
        sys.exit (2)
    if ("" == configuration.bb_master):
        print "No buildbot master given"
        sys.exit (2)
    if (0 == configuration.bb_slaveport):
        print "No buildbot slave port given"
        sys.exit (2)
    if (0 == configuration.bb_webport):
        print "No buildbot web port given"
        sys.exit (2)        
                                
                
    # Create buildslave information
    template = {}
    master_cfg_slaves = ""
    master_cfg_builder_definition = ""
    master_cfg_builder_summary = ""
    master_cfg_scheduler_builders = ""
    slave_cmds = ""
    c = 0
    try:
        f_cmd = open(configuration.bb_task_file, 'w')
    except IOError as e:
        print "Cannot open output command file "+ configuration.bb_task_file +": "+str(e)
        sys.exit (2)
        
    for node in node_hostnames:
        node = node.strip()
        print "Found node '" + node + "'" 
        password = ''.join([random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890') for i in range(64)])
        # slaves
        master_cfg_slaves += 'BuildSlave("'+node+'","'+password+'"),\n'
        # builder definition
        master_cfg_builder_definition += "builder"+str(c)+" = {'name': \"" + node +"\"," +  "'slavename': \"" + node + "\",'builddir':\"" + node +"\",'factory': f,'category': \"GNUnet\",}\n"
        # scheduler
        master_cfg_scheduler_builders += '"'+node+'", '
        # builder summary
        master_cfg_builder_summary += "builder"+str(c)+", "
        # cmd
        f_cmd.writelines (node +";" + configuration.bb_bb_cmd + " " + configuration.bb_master + " " + node + " "+ password + "\n")
        c += 1   
    try:
        f_cmd.close()
    except IOError as e:
        print "Cannot close output task file "+ configuration.bb_task_file +": "+str(e)
        sys.exit (2)
    
    #print master_cfg_slaves
    #print master_cfg_builder_definition
    #print master_cfg_builder_summary    
    
    # Create master.cfg
    master_file = ""
    try:
        f_tmpl = open(configuration.bb_template, 'r')
    except IOError as e:
        print "Cannot open template file "+ configuration.bb_template
        sys.exit (2)
    
    for line in f_tmpl:
        line.strip()
        line = line.replace ("%GPLMT_BUILDER_DEFINITION",  master_cfg_builder_definition)
        line = line.replace ("%GPLMT_BUILDER_SUMMARY",  master_cfg_builder_summary)
        line = line.replace ("%GPLMT_SLAVES",  master_cfg_slaves)
        line = line.replace ("%GPLMT_SCHEDULER_BUILDERS",  master_cfg_scheduler_builders)
        line = line.replace ("%GPLMT_WEB_PORT",  configuration.bb_webport)
        line = line.replace ("%GPLMT_SLAVE_PORT",  configuration.bb_slaveport)
        if ("" != configuration.bb_force_user):
            line = line.replace ("%GPLMT_FORCE_USER",  configuration.bb_force_user)
        if ("" != configuration.bb_force_pw):            
            line = line.replace ("%GPLMT_FORCE_PWD",  configuration.bb_force_pw)
        if ("yes" == configuration.bb_force_enable):            
            line = line.replace ("%GPLMT_FORCE_ENABLE",  "")
        else:
            line = line.replace ("%GPLMT_FORCE_ENABLE",  "#")                    
        master_file += line        
    f_tmpl.close()    
    try:
        f_cfg = open(configuration.bb_result_cfg, 'w')
    except IOError as e:
        print "Cannot open template file "+ configuration.bb_result_cfg +": "+str(e)
        sys.exit (2)    
    f_cfg.writelines(master_file)
    f_cfg.close()  
           
def main():
    global nodesfile
    global cfgfile
    global op
    #import gplmt
    import gplmt.Configuration as Configuration
    import gplmt.Util as Util
    
    logger = Util.Logger (False)
    # Parse command line arguments
    parse_arg ()
    configuration = Configuration.Configuration (cfgfile, logger)
    configuration.load ()
    update_conf (configuration)

    if ((configuration.pl_username == "") or 
         (configuration.pl_slicename == "")):
        #usage ()
        sys.exit (2)
    if (configuration.pl_api_url == ""):
        # PlanetLab Europe
        configuration.pl_api_url = "https://www.planet-lab.eu/PLCAPI/"
    if (configuration.pl_password == ""):
        print "Please enter PlanetLab password:"            
        configuration.pl_password = getpass.getpass()    

    if (None != nodesfile):
        nodes = load_nodes(nodesfile)
        if (None == nodes):
             print "Nodes file " +nodesfile+ " not found"
             sys.exit(1)
    else:
        nodes = None

    if (op == "all"):
        list_all_nodes (configuration)
    elif (op == "my"):
        list_my_nodes (configuration)
    elif (op == "my"):
        list_my_nodes (configuration)
    elif ((None != nodes) and (op == "add_nodes_file")):
        add_to_nodes(configuration, nodes)
    elif ((None != nodes) and (op == "del_nodes_file")):
        del_nodes (configuration, nodes)        
    elif (op == "add_nodes_all"):
        add_to_all_nodes(configuration)
    elif (op == "create_buildbot_cfg"):
        create_buildbot_cfg (configuration)                                                      
    else:
        usage()
        sys.exit()       
    
    
if (__name__ == "__main__"):
    # Modify search path to include gplmt
    sys.path.append('../')
    main ()
