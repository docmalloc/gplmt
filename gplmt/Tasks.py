#!/usr/bin/python
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
# Nodes
try: 
    import Util
    import sys
    import os
    import gplmt
    from xml.parsers import expat  
    from minixsv import pyxsval as xsv 
    from elementtree import ElementTree
    elementtree_loaded = True 
    from genxmlif import GenXmlIfError
    # gplmt imports
    import Targets as Targets
except ImportError as e: 
    print "That's a bug! please check README: " +  __file__+ " " + str (e)
    sys.exit(1)
    

glogger = None

supported_operations = ["run", "monitor", "get", "put", "run_per_host"]

class Taskresult:
    unspecified = -1
    success = 0
    timeout = 1
    fail = 2 
    return_value_did_not_match = 3
    output_did_not_match = 4
    src_file_not_found = 5
    user_interrupt = 6    

class Operation:
    none=0
    run=1
    monitor=2
    get=3
    put=4
    run_per_host=5

class Task:
    def __init__(self):
        self.id = -1
        self.name = ""
        self.type = Operation.none
        self.command = ""
        self.arguments = ""
        self.timeout = 0
        self.expected_return_code = -1
        self.expected_output = None
        self.stop_on_fail = False
        self.set = None
        self.src = None
        self.dest = None
        self.command_file = None
        self.output_prefix = None
        
    def copy (self):
        t = Task ()
        t.id = self.id 
        t.name = self.name
        t.type = self.type
        t.command = self.command
        t.arguments = self.arguments
        t.timeout = self.timeout
        t.expected_return_code = self.expected_return_code
        t.expected_output = self.expected_output
        t.stop_on_fail = self.stop_on_fail
        t.set = self.set
        t.src = self.src
        t.dest = self.dest
        t.command_file = self.command_file
        t.output_prefix = self.output_prefix
        return t
    def log (self):
        glogger.log ("Task " + str(self.id) + ": " + self.name)
    def check (self):
        if (Operation.none):
            return False
        if (self.type == Operation.run):                   
            if ((self.id == -1) or (self.name == "") or (self.command == "")):
                return False
        if (self.type == Operation.put):                   
            if ((self.id == -1) or (self.name == "") or 
                (self.src == None) or (self.dest == None)):
                return False
        if (self.type == Operation.get):                   
            if ((self.id == -1) or (self.name == "") or 
                (self.src == None) or (self.dest == None)):
                return False            
        if (self.type == Operation.run_per_host):                   
            if ((self.id == -1) or (self.name == "") or (self.command_file == "")):
                return False                    
        return True
                        
class Taskset:
    def __init__(self):
        self.set = list()


def handle_task (elem, tasks):
    t = Task ()
    
    if (None != elem.attrib.get("name")):
        t.name = elem.attrib.get("name")

    if (None != elem.attrib.get("id")):
        t.id = elem.attrib.get("id")
    
    if (tasks.startid != -1):
        if (tasks.startid == t.id):
            tasks.startid_found = True
            glogger.log ("Task " + str (t.id) + " '" + t.name + "' has start ID") 
        if (tasks.startid_found == False):
            glogger.log ("Task " + str (t.id) + " '" + t.name + "' skipped")
            return None;
    
    if (None != elem.attrib.get("enabled")):
        if ("FALSE" == str(elem.attrib.get("enabled")).upper()):
            glogger.log ("Task " + str (t.id) + " '" + t.name + "' is disabled")
            return
    
    if (elem.tag == "run"):     
        t.type = Operation.run
    elif (elem.tag == "monitor"):            
        t.type = Operation.monitor
    elif (elem.tag == "get"):            
        t.type = Operation.get
    elif (elem.tag == "put"):       
        t.type = Operation.put
    elif (elem.tag == "run_per_host"):       
        t.type = Operation.run_per_host        
    else:
        t.type = Operation.none
        
    for child in elem:
        if ((child.tag == "command_file") and (child.text != None)):
            t.command_file = Util.handle_filename(child.text)
            if (False == os.path.exists(t.command_file)):
                print "Command file '" +t.command_file+ "' not existing"
                sys.exit()
                return None 
                 
        if ((child.tag == "output_prefix") and (child.text != None)):
            t.output_prefix = child.text
        if ((child.tag == "command") and (child.text != None)):
            t.command = child.text
        if ((child.tag == "arguments") and (child.text != None)):
            t.arguments = child.text
        if (child.tag == "timeout"):
            try:
                t.timeout = int(child.text)
            except ValueError:
                print "Invalid timeout '"+child.text+"' for task id " + str (t.id) + " name " + t.name
        if (child.tag == "expected_return_code"):
            try:
                t.expected_return_code = int(child.text)
            except ValueError:
                print "Invalid expected return code '" +child.text+ "' for task id " + str (t.id) + " name " + t.name
        if ((child.tag == "expected_output") and (child.text != None)):
            t.expected_output = child.text                            
        if ((child.tag == "stop_on_fail") and (child.text != None)):
            if (str.upper(child.text) == "TRUE"):
                t.stop_on_fail = True
            else:
                t.stop_on_fail = False        
        if ((child.tag == "source") and (child.text != None)):
            t.src = child.text
            if ('' != g_configuration.gplmt_userdir and Operation.put == t.type):
                t.src = os.path.join(g_configuration.gplmt_userdir, os.path.basename(t.src))
        if ((child.tag == "destination") and (child.text != None)):
            t.dest = child.text
            if ('' != g_configuration.gplmt_userdir and Operation.get == t.type):
                t.dest = os.path.join(g_configuration.gplmt_userdir, os.path.basename(t.dest))

    if (False == t.check()):
        print "Parsed invalid task with id " + str (t.id) + " name '" + t.name + "'"
        return None 
    else:
        t.log ()
        return t

def handle_sequence (elem, tasks):
    if (None != elem.attrib.get("enabled")):
        if ("FALSE" == str(elem.attrib.get("enabled")).upper()):
            glogger.log ("Element was disabled")
            return
    for child in elem:
            handle_child (child, tasks)
            
def handle_parallel (elem, tasks):
    glogger.log ("Found parallel execution with " + str(len(elem)) + " elements")
    if (None != elem.attrib.get("enabled")):
        if ("FALSE" == str(elem.attrib.get("enabled")).upper()):
            glogger.log ("Element was disabled")
            return
    ptask = Taskset ()
    for child in elem:
        if (elem.tag in supported_operations):
            t = handle_task (elem)
            if (None != t):
                ptask.set.append(t)
                print "Added " + t.name + " to set"
        elif (elem.tag == "parallel"):
            glogger.log ("x")
        #    handle_parallel (elem, l)
        elif (elem.tag == "sequence"):
            glogger.log ("x")
        #        handle_sequence (elem, l)
        else:
            print "Invalid element in task file: " + elem.tag
    tasks.l.append (ptask)            
    
def handle_child (elem, tasks):
    global support_operations
    if (elem.tag in supported_operations):
        t = handle_task (elem, tasks)
        if (None != t):
            tasks.l.append(t)
    elif (elem.tag == "parallel"):
        handle_parallel (elem, tasks)
    elif (elem.tag == "sequence"):
        handle_sequence (elem, tasks)
    else:
        print "Invalid element in task file: " + elem.tag

def handle_options (root, tasks):
    for child in root:
        if (child.tag == "target"):
            if (child.text != None):
                tasks.target = Targets.Target.create(child.text)
                glogger.log ("Tasklist specified target: '" + str(tasks.target) + "'")
        elif (child.tag == "log_dir"):
            if (child.text != None):
                tasks.log_dir = child.text
                glogger.log ("Tasklist specified log dir: '" + str(tasks.log_dir) + "'")
        else:
            print "Invalid option in task file: " + str(child.tag)

def print_sequence (l):
    for i in l:
        print "->",
        if (i.__class__.__name__ == "Task"):
            print i.name,
        elif (i.__class__.__name__ == "Taskset"):
            print "{",
            print_sequence (i.set)
            print "}",

    

class Tasklist:
    def __init__(self, filename, logger, startid, configuration,
                 name="<Undefined>", log_dir=""):
        assert (None != logger)
        global glogger
        glogger = logger
        global g_configuration;
        g_configuration = configuration
        self.logger = logger
        self.filename = filename
        self.l = list ()
        self.startid = startid
        self.startid_found = False
        self.log_dir = log_dir
        self.target = Targets.Target (Targets.Target.undefined)
    def load_singletask (self, cmd, logger):
        t = Task()
        self.name = "Execute single command"
        t.id = 0
        t.name = "Executing single command: '" +str(cmd)+"'" 
        t.type = Operation.run
        t.command = cmd
        t.timeout = 0
        t.expected_return_code = -1
        t.expected_output = None
        t.stop_on_fail = True
        t.set = None
        t.src = None
        t.dest = None
        t.command_file = None
        t.output_prefix = None        
        self.l.append(t)
    def load (self):        
        self.logger.log ("Loading tasks file '" + self.filename + "'")
        enabled = True
        try:
            xsv.parseAndValidate (self.filename)
        except xsv.xsvalErrorHandler.XsvalError as e:
            print "File '" + self.filename + "' does not validate against schema: \n" + str(e)
            return False
        except GenXmlIfError as e:
            print "File '" + self.filename + "' is not well-formed: \n" + str(e)
            return False
        except IOError:
            print "File '" + self.filename + "' not found \n"
            return False
        
        try:
            root = ElementTree.parse (self.filename).getroot()
            if (None != root.attrib.get("name")):
                self.name = root.attrib.get("name")
            if (None != root.attrib.get("enabled")):
                if (False == root.attrib.get("enabled")):
                    enabled = False
        except expat.ExpatError as e:
            print "File '" + self.filename + "'is malformed: " + str(e)
            return False                
        except IOError:
            print "File '" + self.filename + "' not found"
            return False
        if (enabled == True):
            for child in root:
                if (child.tag == "options"):
                    handle_options (child, self)
                else:
                    handle_child (child, self)
        else:
            print "Tasklist " + self.filename + " was disabled"
        #print_sequence (self.l)
        self.logger.log("Loaded %s tasks" % len(self.l))
        
        return True        
    def copy (self):
        t = Tasklist (self.filename, self.logger, -1, g_configuration)
        # Create a copy of the task list as described in 
        # http://docs.python.org/library/copy.html
        t.filename = self.filename
        t.name = self.name
        t.l = self.l[:]
        return t
    def get (self):
        if (len (self.l) > 0):
            item = self.l[0]
            self.l.remove(item)
            return item
        else:
            return None
        
if __name__ == "__main__":
    print "Nothing to do here!"
    sys.exit(1)
