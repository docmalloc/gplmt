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
# Utilities
import os
import sys

def handle_filename (f): 
    f = os.path.expanduser(f)         
    return f

def print_ssh_connection (node):    
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


    return res;

class Logger:

    def __init__(self, verbose):
        if (True == verbose):
            self.verbose = True
        else:
            self.verbose = False   
    def log (self, message):
        global main
        if (True == self.verbose):
            print (message)
            
if __name__ == "__main__":
    print "Nothing to do here!"
    sys.exit(1)