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
from collections import namedtuple
from .configuration import ConfigurationError


class NodeFormatError(Exception):
    pass


class PlanetLabError(Exception):
    pass


class Node:
    def __init__(self, hostname, port=None, username=None, password=None):
        self.hostname = hostname
        self.port = port
        self.username = username
        self.password = password

    def __str__(self):
        res = ""
        cred = ""
        if node.hostname != None:
            res = node.hostname;
        else:
            return res;        
        if node.port != None:
            res += ":" + str(node.port);
                    
        if node.username != None:
            cred = node.username;
        if node.password != None:
            cred += ":" + node.password;
        if "" != cred :
            res = cred + "@" + res;
        return res


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
        return Node(hostname, port, username, password)


class NodeList:
    def __init__(self, filename):
        self.filename = filename
        self.nodes = []
        logging.info("Loading node_results file '" + self.gplmt_filename + "'")

        with open(self.gplmt_filename, "r") as f:
            for line in f: 
                line = line.strip() 
                if len(line) == 0 or line.startswith("#"):
                    continue
                node = NodeResult.parse(line)
                self.nodes.append(node)
                logging.info("Found node '%s'", node)

        logging.info("Loaded %d node results", len(self.node_results))


class StringNodeList:
    def __init__(self, node_list_string):
        self.str = str
        logging.info("Loading node_results '%s'", node_list_string)
        node = Node.parse(node_list_string)
        self.nodes = [node]
        logging.info("Loaded node '" +Util.print_ssh_connection (node)+ "'")


class PlanetLabNodeList:
    def __init__(self, configuration):
        self.configuration = configuration
        self.nodes = []
        
        c = configuration
        if c.pl_password is None or c.pl_password == "":
            raise ConfigurationError("No PlanetLab password given in configuration.")
        if c.pl_username is None or c.pl_username == "":
            raise ConfigurationError("No PlanetLab username given in configuration.")
        if c.pl_api_url is None or c.pl_api_url == "":
            raise ConfigurationError("No PlanetLab API url given in configuration.")

        logging.info("Retrieving node_results assigned to slice '%s' for user '%s'",
                self.configuration.pl_slicename, self.configuration.pl_username)

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
            raise PlanetLabError("Could not retrieve data from PlanetLab API: " + str(e))
        
        for node in node_hostnames:
            n = NodeResult(node, 22, self.configuration.pl_slicename, None)
            logging.info("Planetlab API returned: " + n.hostname)
            self.nodes.append(n)

        logging.info("Planetlab API returned %s nodes", len(self.node_results))

