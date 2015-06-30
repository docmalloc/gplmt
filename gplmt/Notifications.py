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
#    Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
#    Boston, MA 02110-1301, USA.
#
# GNUnet Planetlab deployment and automation toolset 
#
# Notifications     

try:
    import gplmt.Tasks as Tasklist
    import time
    import sys
except ImportError as e: 
    print "That's a bug! please check README: " + str(e)


class Notification:
    def __init__(self, logger):
        assert (None != logger)
        self.logger = logger
    def node_connected (self, node, success, message):
        assert (0)
    def node_disconnected (self, node, success, message):
        assert (0) 
    def tasklist_started (self, node, tasks, message):
        assert (0)
    def tasklist_completed (self, node, tasks, success, message):
        assert (0)
    def task_started (self, node, tasks, message):
        assert (0)
    def task_completed (self, node, tasks, success, message):
        assert (0)

class NodeResultCollection:
    def __init__(self):
        self.nodes_results = list ()
    def add (self, node_res):
        self.nodes_results.append (node_res)
    def size (self):
        return len(self.nodes_results)
    def get (self, node):
        for n in self.nodes_results:
            if (n.node == node):
                return n
        return None
        
class Task:
    def __init__ (self, task):
        self.fail = True
        self.task = task
        self.msg = ""
        self.output = ""
    def finished (self, result, fail, msg, output):
        self.result = result
        self.fail = fail
        self.msg = msg
        self.output = output
        
class TaskList:
    def __init__(self, name):
        self.name = name
        self.success = False
        self.start = time.time()
        self.end = 0

class TaskListCollection:
    def __init__(self):
        self.tasklists = list ()
    def add (self, tasklist):
        self.tasklists.append (tasklist)
    def get (self, name):
        for tl in self.tasklists:
            if (tl.name == name):
                return tl
        return None

class NodeResult:
    def __init__(self, node):
        self.node = node
        self.start = 0
        self.end = 0
        self.tasks = list ()
        self.tasklists = TaskListCollection()
        self.connectSuccess = False

class FileLoggerNotification (Notification):
    def __init__(self, logger):
        assert (None != logger)
        self.logger = logger
        self.nodes_results = NodeResultCollection ()
    def node_connected (self, node, success, message):
        return
    def node_disconnected (self, node, success, message):
        return 
    def tasklist_started (self, node, tasks, message):
        return
    def tasklist_completed (self, node, tasks, success, message):
        self.nodes_results.add (NodeResult(node))
        if (success == True):
            print node + " : Tasklist '" +  tasks.name + "' completed successfully"
        else:
            print node + " : Tasklist '" +  tasks.name + "' completed with failure"
    def task_started (self, node, task, message):
        return
    def task_completed (self, node, task, result, message, output):
        return   


class TaskListResultNotification (Notification):
    def __init__(self, logger):
        assert (None != logger)
        self.logger = logger
        self.nodes_results = NodeResultCollection ()
    def summarize (self):
        maxNodeLen = 0
        maxTasklistLen = 0
        # Calculate max length of node names and tasklist names
        for nres in self.nodes_results.nodes_results:            
            nodeLen = len(nres.node.hostname)
            if (nodeLen > maxNodeLen):
                maxNodeLen = nodeLen
            for tl in nres.tasklists.tasklists:
                tlLen = len(tl.name)
                if(tlLen > maxTasklistLen):
                    maxTasklistLen = tlLen
        # Sort output (success then fail)
        #self.nodes_results.nodes_results.sort(key=lambda x: not x.tasklists.tasklists[0].success)
        # Print organized output
          
        for nres in self.nodes_results.nodes_results:
            sys.stdout.write(nres.node.hostname)
            diff = maxNodeLen - len(nres.node.hostname)
            sys.stdout.write(' ' * diff + ' | ')
            fail_in = ""
            if (False == nres.connectSuccess):
                print 'failed in: connecting: ' + nres.error_msg
                continue
            for tl in nres.tasklists.tasklists:
                sys.stdout.write(tl.name)
                diff = maxTasklistLen - len(tl.name)
                sys.stdout.write(' ' * diff + ' | ')
                fail_in = ""
                for t in nres.tasks:                    
                    if (t.fail == True):
                        fail_in = fail_in + " " +  t.task.name                 
            print 'success' if (tl.success == Tasklist.Taskresult.success) else 'failed in: ' +fail_in 
            for t in nres.tasks:
                if (t.fail == True):
                    print "\tFailed Task: '" + t.task.name + "' with '" +t.msg+ "' and '" + t.output.rstrip() + "'"
                #else:
                    #print "\tSuccessful Task: '" + t.task.name + "' with '" +t.msg+ "' and '" +t.output.rstrip()+ "'"                                 
        #    tsk_str = ""
        #    for t in nres.tasks:
        #        tsk_f = "[e]"
        #        if (t.fail == True):
        #            tsk_f = "[f]"
        #        else:
        #            tsk_f = "[s]"
        #        tsk_str += t.task.name + " " + tsk_f + " ->"
        #    print nres.name
    def node_connected (self, node, success, message):
        
        # Get node object
        node_result_object = self.nodes_results.get(node)
        # Create it if it doesn't exist
        if(None == self.nodes_results.get(node)):
            node_result_object = NodeResult(node)
            self.nodes_results.add(node_result_object)
        # Set node start time as of now
        node_result_object.start = time.time()
        node_result_object.connectSuccess = success
        if (False == success):
            node_result_object.error_msg = message
        return
    def node_disconnected (self, node, success, message):
        # Mainly need to set node end connection time
        nodeObj = self.nodes_results.get(node)
        nodeObj.end = time.time()
        return 
    def tasklist_started (self, node, tasks, message):
        # Get node object
        nodeObj = self.nodes_results.get(node)
        # Create it if it doesn't exist (shouldn't node_connected be called before this?)
        if(None == self.nodes_results.get(node)):
            nodeObj = NodeResult(node)
            self.nodes_results.add(nodeObj)
        # Create tasklist object
        tasklist = TaskList(tasks.name)
        # Add it to the collection of node tasklists
        nodeObj.tasklists.add(tasklist)
        return
    def tasklist_completed (self, node, tasks, success, message):
        # Mainly want to set tasklist end time and success status
        nodeObj = self.nodes_results.get(node)
        tasklist = nodeObj.tasklists.get(tasks.name)
        tasklist.end = time.time()
        tasklist.success = success            
        #if (success == True):
        #    print node + " : Tasklist '" +  tasks.name + "' completed successfully"
        #else:
        #    print node + " : Tasklist '" +  tasks.name + "' completed with failure"
    def task_started (self, node, task, message):
        nodeObj = self.nodes_results.get(node)
        if (None == nodeObj):
            print "NodeResult not found!"
            return 
        nodeObj.tasks.append (Task (task))
        return
    def task_completed (self, node, task, result, message, output):       
        nodeObj = self.nodes_results.get(node)
        for t in nodeObj.tasks:
            if t.task is task:
                if (result != Tasklist.Taskresult.success):
                    #print "\tTASK FAIL: Task '" + t.task.name + "' with '" +t.msg+ "' and '" +t.output+ "'"
                    t.finished (result, True, message, output)
                else:
                    #print "\tTASK SUC: Task '" + t.task.name + "' with '" +t.msg+ "' and '" +t.output+ "'"
                    t.finished (result, False, message, output)
        return         

class SimpleNotification (Notification):
    def __init__(self, logger):
        assert (None != logger)
        self.logger = logger
        #self.nodes_results = NodeResultCollection ()
    def summarize (self):
        #for n in self.nodes_results:
        #    tsk_str = ""
        #    for t in n.tasks:
        #        tsk_f = "[e]"
        #        if (t.fail == True):
        #            tsk_f = "[f]"
        #        else:
        #            tsk_f = "[s]"
        #        tsk_str += t.task.name + " " + tsk_f + " ->"
        #    print n.name  
        return
    def node_connected (self, node, success, message):
        if (success == True):
            print node.hostname + " : connected successfully"
        else:
            print node.hostname + " : connection failed: " + message
    def node_disconnected (self, node, success, message):
        if (success == True):
            print node.hostname + " : disconnected"
        else:
            print node.hostname + " : disconnected with failure"    
    def tasklist_started (self, node, tasks, message):
        print node.hostname + " : Tasklist '" +  tasks.name + "' started"
        #self.nodes_results.add (NodeResult(node))
    def tasklist_completed (self, node, tasks, success, message):
        if (success == Tasklist.Taskresult.success):
            print node.hostname + " : Tasklist '" +  tasks.name + "' completed successfully"
        elif (success == Tasklist.Taskresult.user_interrupt):
            print node.hostname + " : Tasklist '" +  tasks.name + "' was interrupted"
        else:
            print node.hostname + " : Tasklist '" +  tasks.name + "' completed with failure"
    def task_started (self, node, task, message):
        print node.hostname + " : Task '" +  task.name + "' started"
    def task_completed (self, node, task, result, message, output):
        if (result == Tasklist.Taskresult.success):
            print node.hostname + " : Task '" +  task.name + "' completed successfully"
        elif (result == Tasklist.Taskresult.src_file_not_found):
            print node.hostname + " : Task '" +  task.name + "' failed : source file not found: " + message
        else:
            print node.hostname + " : Task '" +  task.name + "' completed with failure: " + message

if __name__ == "__main__":
    print "Nothing to do here!"
    sys.exit(1)
