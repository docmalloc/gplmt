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

Nodes
"""

import sys 
import os 
import urllib
import xmlrpc
import socket
from .util import *

class NodeResult:
    def __init__(self, hostname, port = None, username = None, password = None):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password

    @staticmethod
    def parse(line):
        parts = line.split('#') # allow comments 
        if len(parts) > 1: #credentials supplied
            line = parts[0]
        line = line.replace(" ", "")
        if len(line) == 0:
            return None
        parts = line.split('@')
        hostname = None
        port = None
        username = None
        password = None

        if len(parts) == 2: #credentials supplied
            creds = parts[0].split(':')
            if len(creds) == 2: # username and password
                username = creds[0]
                password = creds[1]
            else: # username
                username = parts[0]
            line = parts[1]

        elif len(parts) > 2:            
            raise Exception("Invalid node definition: " + line)
            return None 

        #parse host/port
        hostport = line.split(':')
        hostname = hostport[0]
        if len(hostport) == 2:
            port = int(hostport[1])
        elif len(hostport) > 2:
            raise Exception("Invalid node definition: " + line)
            return None 
        return NodeResult(hostname, port, username, password)


class Nodes:
    def __init__(self, filename, logger):
        assert (None != logger)
        self.gplmt_logger = logger
        self.gplmt_filename = filename
        self.node_results = list ()
    def load (self):        
        self.gplmt_logger.log ("Loading node_results file '" + self.gplmt_filename + "'")
        try:
            fobj = open (self.gplmt_filename, "r") 
            for line in fobj: 
                line = line.strip() 
                node = NodeResult.parse(line)                
                if (None != node):
                    self.node_results.append(node)
                    self.gplmt_logger.log ("Found node '" + Util.print_ssh_connection (node) + "'")
            fobj.close()
        except IOError:
            print("File " + self.gplmt_filename + " not found")
            return False
        self.gplmt_logger.log ("Loaded " + str(len(self.node_results)) + " node_results")
        return True

class StringNodes:
    def __init__(self, str, logger):
        assert (None != logger)
        self.str = str
        self.gplmt_logger = logger
        self.node_results = list ()
    def load (self):        
        self.gplmt_logger.log ("Loading node_results '" + self.str + "'")
        node = NodeResult.parse(self.str)
        if (None == node):
            return False  
        self.node_results.append(node)
        self.gplmt_logger.log ("Loaded node '" +Util.print_ssh_connection (node)+ "'")
        return True    

class PlanetLabNodes:
    def __init__(self, configuration, logger):
        assert (None != logger)
        self.gplmt_logger = logger
        self.configuration = configuration
        self.node_results = list ()
    def load (self):        
        if self.configuration.pl_password == "":
            print("No PlanetLab password given in configuration fail!")
            return False
        if (self.configuration.pl_username == ""):            
            print("No PlanetLab username given in configuration, fail!")
            return False
        if (self.configuration.pl_api_url == ""):            
            print("No PlanetLab API url given in configuration, fail!")
            return False
        self.gplmt_logger.log ("Retrieving node_results assigned to slice '" + self.configuration.pl_slicename + "' for user " +self.configuration.pl_username)
        try:
            server = xmlrpc.client.ServerProxy(self.configuration.pl_api_url)
        except:
            print("Could not connect to PlanetLab API, fail!")
            return False
        
        slice_data = {}
        slice_data['name'] = self.configuration.pl_slicename

        auth = {}
        auth['Username'] = self.configuration.pl_username
        auth['AuthString'] = self.configuration.pl_password
        auth['AuthMethod'] = "password"
        
        try:
            node_ids = server.GetSlices(auth, [slice_data['name']], ['node_ids'])[0]['node_ids']
            node_hostnames = [node['hostname'] for node in server.GetNodes(auth, node_ids, ['hostname'])]
        except Exception as e:
            print("Could not retrieve data from PlanetLab API: " + str(e))
            return False            
        
        for node in node_hostnames:
            n = NodeResult(node, 22, self.configuration.pl_slicename, None)
            self.gplmt_logger.log ("Planetlab API returned: " + n.hostname)            
            self.node_results.append(n)
        self.gplmt_logger.log ("Planetlab API returned " + str(len(self.node_results)) + " node_results")     
        return True

