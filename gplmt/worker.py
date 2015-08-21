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

Worker
"""

import threading
import socket
import os
import time
import sys
import select
import signal
import inspect
import subprocess
import datetime
import paramiko
from paramiko.ssh_exception import SSHException
from collections import namedtuple

from .configuration import *
from .util import *
from .tasks import *
from .targets import *
from .SCP import *

class UnsupportedOperationError(Exception):
    pass

TaskExecutionResult = namedtuple('TaskExecutionResult', 'result message output')

interrupt = False
def signal_handler(signal, frame):
    global interrupt
    interrupt = True
    print("User interrupt received!")
    time1 = time.time()
    # for the next <5> secs check if all threads are finished
    threads_done = False
    timeout = False
    while(not threads_done):
        threads_done = True
        for w in workersList:
            if(w.thread.isAlive()):
                if(timeout):
                    g_logger.log ("Thread taking too long, killing it...")
                    w.thread._Thread__stop()
                else:
                    threads_done = False
                    break
        time.sleep(0.1)
        if(time.time() - time1 > 5):
            timeout = True
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)


# Global variables
g_logger = None
g_notifications = None
g_configuration = None
workersList = list()

class AbstractWorker(threading.Thread):
    def __init__(self, threadID, node, tasks):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.node = node
        self.tasks = tasks
        self.timer = None
    def connect (self):
        raise NotImplementedError (inspect.stack()[0][3]) 
    def disconnect (self):       
        raise NotImplementedError (inspect.stack()[0][3]) 
    def exec_run_per_host (self, task):
        raise NotImplementedError (inspect.stack()[0][3]) 
    def exec_run (self, task):
        raise NotImplementedError (inspect.stack()[0][3]) 
    def exec_put (self, task):
        raise NotImplementedError (inspect.stack()[0][3]) 
    def exec_get (self, task):
        raise NotImplementedError (inspect.stack()[0][3])
    def interrupt_task (self):
        raise NotImplementedError (inspect.stack()[0][3])
    def run(self):   
        global interrupt
        tasklist_success = True
        # Connecting
        try:
            res = self.connect()
        except NotImplementedError as e:
            print("Not implemented: " + str(self.__class__) + " function: " +  str(e))
            pass
        except Exception as e:
            print("Exception in Worker: " + str (e))
            pass
        if (Tasks.Taskresult.success != res.result):
            g_notifications.node_connected (self.node, False, "Failed to connect: " + res.message)
            return
        else:
            g_notifications.node_connected (self.node, True, "Connected successfully")
        # Starting tasklist 
        g_logger.log (self.node.hostname + " : Starting tasklist '" + self.tasks.name + "'")
        g_notifications.tasklist_started (self.node, self.tasks, "")            
        task = self.tasks.get()        
        if (interrupt):
            g_notifications.tasklist_completed (self.node, self.tasks, Tasks.Taskresult.user_interrupt, "")                        
        # Executing Tasks 
        while (None != task and not interrupt):
        
            if (None != self.timer):
                self.timer.cancel()
                self.timer = None
        
            if (task.node and task.node != self.node.hostname):
                g_logger.log (self.node.hostname + " : Ignoring task due to set node attribute");
                task = self.tasks.get()
                continue
                
            delta = int(max((task.start_absolute - datetime.datetime.now()).total_seconds(), task.start_relative))
            
            if (delta > 0):
                g_logger.log (self.node.hostname + " : Continuing execution in " + str(delta) + " seconds")
                for x in range(0, delta):
                    time.sleep(1) 
                    if (interrupt):
                        g_notifications.tasklist_completed (self.node, self.tasks, Tasks.Taskresult.user_interrupt, "")
                        g_notifications.task_completed (self.node, task, Tasks.Taskresult.user_interrupt, "task was interrupted", "")
                        return
                        
                                                                     
            
            g_logger.log (self.node.hostname + " : Running task id " +str(task.id)+" '" + task.name + "'")     
            
            
            delta = int(min((task.stop_absolute - datetime.datetime.now()).total_seconds(), task.stop_relative))
            
            if (delta > 0 and delta < 31556926):
                g_logger.log (self.node.hostname + " : Task will be interrupted in " + str(delta) + " seconds")
                self.timer = threading.Timer(delta, self.interrupt_task)
                self.timer.start()
            
                               
            g_notifications.task_started (self.node, task, "")
            task_result = None
            try:
                if (task.type == Tasks.Operation.run):
                    task_result = self.exec_run (task)
                    assert (None != task_result)
                    g_notifications.task_completed (self.node, task, task_result.result, task_result.message, task_result.output)
                elif (task.type == Tasks.Operation.put):
                    task_result = self.exec_put (task)
                    assert (None != task_result)
                    g_notifications.task_completed (self.node,  task, task_result.result, task_result.message, task_result.output)
                elif (task.type == Tasks.Operation.get):
                    task_result = self.exec_get (task)
                    assert (None != task_result)                
                    g_notifications.task_completed (self.node,  task, task_result.result, task_result.message, task_result.output)
                elif (task.type == Tasks.Operation.run_per_host):
                    task_result = self.exec_run_per_host (task)
                    assert (None != task_result)
                    g_notifications.task_completed (self.node,  task, task_result.result, task_result.message, task_result.output)                   
                else:
                    print("UNSUPPORTED OPERATION!")
            except NotImplementedError as e:
                print("Not implemented" + str (e))
                pass
            except Exception as e2:
                print("Exception in Worker: " + str (e2))
                pass
            if (interrupt):
                break
            if (None == task_result):
                g_logger.log (self.node.hostname + " : Task '"+ task.name +"' failed to execute")
                task_result = TaskExecutionResult(Tasks.Taskresult.fail, "failed to execute task: " + task.name, "")                   
                pass                                
            if ((task_result.result != Tasks.Taskresult.success) and (task.stop_on_fail == True)):
                g_logger.log (self.node.hostname + " : Task failed and therefore execution is stopped")     
                self.disconnect()
                tasklist_success = False
                break                      
            task = self.tasks.get()

        if (self.timer != None):
            self.timer.cancel()
            self.timer = None

        if (interrupt):            
            g_notifications.tasklist_completed (self.node, self.tasks, Tasks.Taskresult.user_interrupt, "")
            if (None != task):
                g_notifications.task_completed (self.node, task, Tasks.Taskresult.user_interrupt, "task was interrupted", "")                                         
        elif (False == tasklist_success):
            g_notifications.tasklist_completed (self.node, self.tasks, Tasks.Taskresult.fail, "")            
        else:
            g_notifications.tasklist_completed (self.node, self.tasks, Tasks.Taskresult.success, "")   
        #disconnect
        try:
            res = self.disconnect()
        except NotImplementedError as e:
            print("Not implemented: " + str(self.__class__) + " function: " +  str(e))
            pass
        except Exception as e:
            print("Exception in Worker:" + str (e))
            pass
            
        if (False == res):
            g_notifications.node_disconnected (self.node, False, "Failed to disconnect")
        else:
            g_notifications.node_disconnected (self.node, True, "Disconnected successfully")
        g_logger.log (self.node.hostname + " : All tasks done for " + self.node.hostname)
        return            
             
            

class TestWorker(AbstractWorker):
    """
    Worker that succeeds at every task without doing anything.
    Prints the work that should've been done to stdout.
    """
    def connect(self):
        print("TestWorker connects to '%s'" % (self.node.hostname,))
        return TaskExecutionResult(Tasks.Taskresult.success, "", "")    
    def disconnect(self):
        print("TestWorker disconnects from '%s'" % (self.node.hostname,))
        return TaskExecutionResult(Tasks.Taskresult.success, "", "")     
    def exec_run_per_host(self, task):
        print("TestWorker executes per host")
        return TaskExecutionResult(Tasks.Taskresult.success, "exec_run_per_host successful", "")
    def exec_run(self, task):
        print("TestWorker executes '%s' and runs '%s'" % (task.name, task.command))
        return TaskExecutionResult(Tasks.Taskresult.success, "exec_run successful", "")        
    def exec_put(self, task):
        print("TestWorker puts '%s' from '%s' to '%s'" % (task.name, task.src, task.dest)
        return TaskExecutionResult(Tasks.Taskresult.success, "exec_put successful", "")             
    def exec_get(self, task):
        print("TestWorker puts '%s' from '%s' to '%s'" % (task.name, task.src, task.dest)
        return TaskExecutionResult(Tasks.Taskresult.success, "exec_get successful", "")     
    def interrupt_task(self):
        print("TestWorker task is interrupted by timeout")


class LocalWorker(AbstractWorker):
    def __init__(self, threadID, node, tasks):
        super().__init__(self, threadID, node, tasks)
        self.process = None

    def connect(self):
        logging.info("LocalWorker connects to '" + self.node.hostname + "'")
        try:
            if not os.path.exists(self.node.hostname):            
                os.makedirs(self.node.hostname)
                logging.info("Created " + self.node.hostname)
        except os.error as e:
            logging.info("Could not created " + self.node.hostname)
            msg = "Cound not create '%s'." % (self.node.hostname,)
            return TaskExecutionResult(Tasks.Taskresult.fail, msg, str(e))
        return TaskExecutionResult(Tasks.Taskresult.success, "", "")    

    def disconnect(self):       
        return TaskExecutionResult(Tasks.Taskresult.success, "Disconnected", "")

    def exec_run_per_host(self, task):
        raise UnsupportedOperationError("Local workers can't execute per-node commands")

    def exec_run(self, task):
        logging.info("LocalWorker executes on '" + self.node.hostname + "' : " + task.command + " " + task.arguments)
        try:
            self.process = subprocess.Popen( "exec " + task.command, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, shell=True)
            stdoutdata, stderrdata = self.process.communicate()
            output = stdoutdata
            output = output.rstrip()
        except Exception as e:
            print(e)
            return TaskExecutionResult(Taskresult.fail, "Could not execute command", str(e))

        if (task.expected_return_code != -1 and task.expected_return_code != returncode:
            return TaskExecutionResult(
                Tasks.Taskresult.return_value_did_not_match,
                "Expected return code %d but got %d" % (task.expected_return_code, returncode), 
                output)

        if task.expected_output is not None:
            found = False
            for l in output.splitlines():
                if task.expected_output in l:
                    found = True
            if not found:
                return TaskExecutionResult(
                    Tasks.Taskresult.return_value_did_not_match,
                    "Expected output should contain '" + str(task.expected_output) +"'",
                    output)
        return TaskExecutionResult(Taskresult.success, "successful", output)                

    def exec_put (self, task):
        raise NotImplementedError (inspect.stack()[0][3]) 

    def exec_get (self, task):
        raise NotImplementedError (inspect.stack()[0][3])

    def interrupt_task (self):
        logging.info(self.node.hostname + " : Task interrupted by timeout")
        if self.process is not None:
            self.process.terminate()


class RemoteSSHWorker (AbstractWorker):
    def __init__(self, threadID, node, tasks):
        super().__init__(self, threadID, node, tasks)
        self.task_interrupted = False

    def connect (self):
        self.ssh = None
        if interrupt:
            return TaskExecutionResult(Tasks.Taskresult.user_interrupt, "interrupted by user", "")            
        try: 
            self.ssh = paramiko.SSHClient()

            cfg = self.configuration
            
            if cfg.ssh_use_known_hosts:
                logging.info(self.node.hostname + " : Loading known hosts")
                self.ssh.load_system_host_keys()

            # Automatically add new hostkeys
            if cfg.ssh_add_unkown_hostkeys:
                self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # keyword arguments that will be passed to ssh.connect
            connect_args = {}

            # check for private key existence
            keyfile = None
            if g_configuration.ssh_keyfile is not None and os.path.exists(g_configuration.ssh_keyfile):
                logging.info("Node %s: Using ssh key file %s", self.node, ssh_keyfile)
                connect_args['keyfile'] = g_configuration.ssh_keyfile

            if self.node.username:
                logging.info("Node %s: Using username from nodes file.", self.node)
                connect_args['username'] = self.node.username
                if self.node.password is not None:
                    logging.info("Node %s: Using password from nodes file.", self.node)
                    connect_args['password'] = self.node.password
            elif cfg.ssh_username:
                logging.info("Node %s: Using credentials from GPLMT config", self.node)
                connect_args['username'] = cfg.ssh_username
                connect_args['password'] = cfg.ssh_password
            elif cfg.ssh_password:
                logging.info("Node %s: Using password-only from GPLMT config", self.node)
                connect_args['password'] = cfg.ssh_password

            logging.info("Node %s: Trying to connect to '%s'", self.node.hostname, self.node)
            self.ssh.connect (self.node.hostname,
                         port=self.node.port or 22,
                         timeout=10,
                         *connect_args)

            self.transport = self.ssh.get_transport()                         
        except (IOError,
                paramiko.SSHException,
                paramiko.BadHostKeyException, 
                paramiko.AuthenticationException,
                socket.error) as e:  
            logging.info(self.node.hostname + " : Error while trying to connect: " + str(e))
            return TaskExecutionResult (Tasks.Taskresult.fail, str(e), "")
        logging.info(self.node.hostname + " : Connected!")
        return TaskExecutionResult(Taskresult.success, "", "")

    def disconnect(self):       
        if self.ssh is None or self.transport is None:
            return TaskExecutionResult (Tasks.Taskresult.fail, "", "")
        self.ssh.close()
        return TaskExecutionResult(Taskresult.success, "", "")

    def exec_run_per_host(self, task):
        found = False
        default = None
        cmd = None          
        try:
            with open(task.command_file, 'r') as f:
                for line in f:
                    if line.strip().startswith('#'):
                        continue
                    sline = line.split(';', 2)
                    host = sline[0].strip()
                    if host == self.node.hostname:
                        cmd = sline[1].strip()
                        found = True
                    if sline[0] == '':
                        default = host
        except IOError as e:            
            return TaskExecutionResult (Tasks.Taskresult.fail, "Cannot open command file '" +task.command_file+ "' : " + str(e), "")
        t = task.copy()
        if found:
            logging.info(self.node.hostname + " : Found specific command '"+ cmd + "'")
            t.command = cmd
            t.arguments = ""
        elif default is not None:
            logging.info("Node %s: Using default command '%s'", self.node.hostname, default)
            t.command = default
            t.arguments = ""
        else:
            logging.info("Node %s: Task '%s' failed: no command to execute", self.node.hostname, task.name)
            return TaskExecutionResult(Tasks.Taskresult.fail, "no command to execute", "")  
        return self.exec_run(t)

    def exec_run (self, task):        
        global interrupt
        self.task_interrupted = False
        message = "undefined"
        output = ""
        if(interrupt):
            message = "'"+ task.name +  "' interrupted by user"
            g_logger.log (self.node.hostname + " : Task '"+ message)
            return TaskExecutionResult(Tasks.Taskresult.user_interrupt, "interrupted by user", "")
        if ((task.command == None) and (task.arguments == None)):
            message = "'"+ task.name +  "' no command to execute"
            g_logger.log (self.node.hostname + " : Task " + message)
            return TaskExecutionResult(Tasks.Taskresult.fail, "no command to execute", "")
        try:
            channel = self.transport.open_session()
            channel.settimeout(1.0)
            channel.get_pty ()
            channel.exec_command(task.command + " " + task.arguments)            
        except SSHException as e:
            g_logger.log (self.node.hostname + " : Error while trying to execute: " + str(e))
            return TaskExecutionResult(Tasks.Taskresult.fail, str(e), "") 
        if (task.timeout > 0):
            timeout = task.timeout
        else:
            timeout = -1
        result = Tasks.Taskresult.success
        exit_status = -1
        start_time = time.time ()
        
        stdout_data = ""
        stderr_data = ""
        
        while 1:
            if(interrupt):
                result = Tasks.Taskresult.user_interrupt
                break
            if (self.task_interrupted):
                channel.close()
                exit_status = 0
                break
                
            if (timeout != -1):
                delta = time.time() - start_time
                if (delta > timeout):
                    g_logger.log (self.node.hostname + " : Timeout after " +str(delta) +" seconds")                    
                    result = Tasks.Taskresult.timeout
                    break
            (r, w, e) = select.select([channel], [], [], 1)
            if r:
                got_data = False
                if channel.recv_ready():
                    data = r[0].recv(4096)
                    if data:
                        got_data = True
                        g_logger.log (self.node.hostname + " : '" + data + "'")
                        output += data
                        stdout_data += data
                if channel.recv_stderr_ready():
                    data = r[0].recv_stderr(4096)
                    if data:
                        got_data = True
                        g_logger.log (self.node.hostname + " : '" + data + "'")    
                        output += data
                        stderr_data += data
                if not got_data:
                    break        
        if (not self.task_interrupted and result == Tasks.Taskresult.success):
            exit_status = channel.recv_exit_status ()          
        if (result == Tasks.Taskresult.success):
            if (task.expected_return_code != -1):                    
                if (exit_status != task.expected_return_code):
                    g_logger.log (self.node.hostname + " : Task '"+ task.name + "' completed after "+ str(time.time() - start_time) +" sec, but exit code " +str(exit_status)+ " was not as expected " + str(task.expected_return_code))
                    #g_logger.log (stdout_data)
                    #g_logger.log (stderr_data)
                    result = Tasks.Taskresult.return_value_did_not_match
                else:
                    g_logger.log (self.node.hostname + " : Task '"+ task.name + "' completed after "+ str(time.time() - start_time) +" sec, exit code " +str(exit_status)+ " was as expected " + str(task.expected_return_code))       
            if (task.expected_output != None):
                output_contained = False
                if (task.expected_output in stdout_data):
                    output_contained = True
                if (task.expected_output in stderr_data):
                        output_contained = True                
                if (output_contained == True):
                    g_logger.log (self.node.hostname + " : Task '"+ task.name + "' expected output '"+task.expected_output+"' was found")
                else:
                    g_logger.log (self.node.hostname + " : Task '"+ task.name + "' expected output '"+task.expected_output+"' was not found in '" + output.rstrip() + "'")
                    result = Tasks.Taskresult.output_did_not_match
                    
        if (result == Tasks.Taskresult.success):
            message = "'"+ task.name +  "' successful"
            g_logger.log (self.node.hostname + " : Task " + message)
        elif (result == Tasks.Taskresult.timeout):
            message = "'"+ task.name +  "' with timeout"
            g_logger.log (self.node.hostname + " : Task "+ message)
        elif (result == Tasks.Taskresult.user_interrupt):
            message = "'"+ task.name +  "' interrupted by user"
            g_logger.log (self.node.hostname + " : Task "+ message)
        else: 
            message = "'"+ task.name +  "' failed"
            g_logger.log (self.node.hostname + " : Task "+ message)
        return TaskExecutionResult(result, message, output)  

    def exec_put (self, task):
        if not os.path.exists(task.src):
            return TaskExecutionResult(Taskresult.src_file_not_found, task.src, "")              
        result = None
        try:
            if g_configuration.ssh_transfer == Configuration.TransferMode.scp:
                scp = SCPClient(self.transport)
                scp.put(task.src, task.dest)
            if g_configuration.ssh_transfer == Configuration.TransferMode.sftp:
                # XXX(FlorianDold): can we use a context manager here?
                # How do we ensure that the sftp object is always closed?
                sftp = paramiko.SFTPClient.from_transport(self.transport)
                sftp.put(task.src, task.dest)
                sftp.close()
        except SCPException as e:
            logging.info(self.node.hostname + " : Task '"+ task.name + "' :" + str(e))
            result = TaskExecutionResult(Taskresult.fail, str(e), "")
        except paramiko.SSHException as e:
            logging.info(self.node.hostname + " : Task '"+ task.name + "' :" + str(e))
            result = TaskExecutionResult(Taskresult.fail, str(e), "")
        except (OSError, IOError) as e:
            logging.info(self.node.hostname + " : Task '"+ task.name + "' : " + str(e))
            result = TaskExecutionResult(Taskresult.src_file_not_found, str(e), "")

        if result is None:
            result = TaskExecutionResult(Tasks.Taskresult.success, "", "")        
        return result

    def exec_get (self, task):
        result = None
        if interrupt:
            message = "'"+ task.name +  "' interrupted by user"
            g_logger.log (self.node.hostname + " : Task '"+ message)
            return TaskExecutionResult(Tasks.Taskresult.user_interrupt, "interrupted by user", "")
        try:
            base = os.path.basename(task.src)
            dest = os.path.join(task.dest, '%s.%s' % (self.node.hostname, base))
            if (g_configuration.ssh_transfer == Configuration.TransferMode.scp): 
                scp = SCPClient (self.transport)
                scp.get (task.src, dest)
            if g_configuration.ssh_transfer == Configuration.TransferMode.sftp:
                sftp = paramiko.SFTPClient.from_transport (self.transport)
                sftp.get(task.src, dest)
                sftp.close()
        except SCPException as e:
            logging.info(self.node.hostname + " : Task '"+ task.name + "' :")
            result = TaskExecutionResult(Tasks.Taskresult.fail, str(e), "")  
        except paramiko.SSHException as e:
            logging.info(self.node.hostname + " : Task '"+ task.name + "' :" + str(e))
            result = TaskExecutionResult(Tasks.Taskresult.fail, str(e), "")
        except (OSError, IOError) as e:
            logging.info(self.node.hostname + " : Task '"+ task.name + "' : " + str(e))
            result = TaskExecutionResult(Tasks.Taskresult.src_file_not_found, str(e), "")  
        if result is None:          
            result = TaskExecutionResult(Tasks.Taskresult.success, "Store source '"+task.src+"' in '" +task.dest+"'", "")      
        return result

    def interrupt_task (self):
        logging.info(self.node.hostname + " : Task interrupted by timeout")
        self.task_interrupted = True   


class PlanetLabWorker (RemoteSSHWorker):
    def connect(self):
        self.ssh = None

        if interrupt:
            return TaskExecutionResult(Tasks.Taskresult.user_interrupt, "interrupted by user", "")            

        try: 
            self.ssh = paramiko.SSHClient()

            config = self.configuration
            
            if config.ssh_use_known_hosts:
                logging.info("Node %s: Loading known hosts", self.node.hostname)
                self.ssh.load_system_host_keys()

            # Automatically add new hostkeys
            if config.ssh_add_unkown_hostkeys:
                self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Check for private key existence.
            # If key is not found, password will be used.
            keyfile = None
            if g_configuration.pl_keyfile is not None: 
                if (os.path.exists (g_configuration.pl_keyfile)):
                    g_logger.log (self.node.hostname + " : Found " + g_configuration.pl_keyfile)
                    keyfile = g_configuration.pl_keyfile
                else:
                    g_logger.log (self.node.hostname + " : Not found " + g_configuration.pl_keyfile)

            logging.info("Node %s: Trying to connect to %s", self.node.hostname, self.node)
            logging.info("Node %s: Using username %s", self.config.hostname, config.pl_slicename)

            self.ssh.connect (self.node.hostname,
                     port=self.node.port or 22,
                     username=config.pl_slicename, 
                     timeout=10,
                     key_filename=keyfile,
                     password=config.pl_keyfile_password)
            self.transport = self.ssh.get_transport()                         
        except (IOError,
                paramiko.SSHException,
                paramiko.BadHostKeyException, 
                paramiko.AuthenticationException,
                socket.error) as e:  
            logging.info(self.node.hostname + " : Error while trying to connect: " + str(e))
            return TaskExecutionResult(Taskresult.fail, str(e), "")

        logging.info(self.node.hostname + " : Connected!")
        return TaskExecutionResult(Taskresult.success, "", "")
  

class NodeWorker:
    def __init__(self, target, node, tasks):
        self.target = target
        self.node = node
        self.tasks = tasks
        self.thread = None
        
        if (self.target == Targets.Target (Targets.Target.undefined)):
            self.thread = AbstractWorker (1, self.node, self.tasks);
        elif (self.target == Targets.Target (Targets.Target.test)):
            self.thread = TestWorker (1, self.node, self.tasks);                     
        elif (self.target == Targets.Target (Targets.Target.local)):
            self.thread = LocalWorker (1, self.node, self.tasks);
        elif (self.target == Targets.Target (Targets.Target.remote_ssh)):
            self.thread = RemoteSSHWorker (1, self.node, self.tasks);
        elif (self.target == Targets.Target (Targets.Target.planetlab)):
            self.thread = PlanetLabWorker (1, self.node, self.tasks);
        return        

    def start (self):
        g_logger.log ("Starting execution for node " + self.node.hostname)
        self.thread.start()


class Worker:
    def __init__(self, configuration, target, nodes, tasks, notifications):
        self.target = target
        self.node_results = nodes
        self.workers_waiting = []
        self.workers_running = []
        self.workers_finished = []
        self.tasks = tasks
        self.parallelism = configuration.gplmt_parallelism
        self.current_workers = 0
        self.total_workers = 0

    def start(self):
        if self.parallelism != 0:
            logging.info("Starting execution on target '%s'", self.target)
        else:
            logging.info("Starting execution on target '%s' with parallelism of %d", self.target, self.parallelism)
            
        self.total_workers = 0
        for node in self.node_results.node_results:
            nw = NodeWorker(self.target, node, self.tasks.copy())
            self.workers_waiting.append(nw)
            self.total_workers += 1
            
        self.current_workers = 0
        while self.total_workers > len(self.workers_finished):
            while ((0 != self.parallelism) and (len(self.workers_waiting) > 0) and (self.current_workers <= self.parallelism)):
                nw = self.workers_waiting.pop(0)
                nw.start()
                nw = self.workers_running.append(nw)
                self.current_workers += 1
            for worker in self.workers_running:
                if not worker.thread.isAlive():
                    print(worker.node.hostname + " finished")
                    self.workers_running.remove(worker)
                    self.workers_finished.append(worker)
                    self.current_workers -= 1
            time.sleep(0.5)
            g_logger.log(str(len(self.workers_finished)) +  " of " + str (self.total_workers) + " nodes finished")
            
        g_notifications.summarize()
        
