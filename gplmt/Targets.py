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
# Target

import sys

class Target ():
    undefined = 0
    test = 1
    local = 2
    remote_ssh = 3
    planetlab = 4
    hen = 5
    def __init__(self, Type = undefined):
        self.value = Type
    def __str__(self):
        if self.value == Target.test:
            return 'test'        
        if self.value == Target.local:
            return 'local'
        if self.value == Target.remote_ssh:
            return 'remote_ssh'
        if self.value == Target.planetlab:
            return 'planetlab'
        if self.value == Target.hen:
            return 'hen'
        else:
            return "undefined"
    def __ne__(self,y):
        if (y == None):
            return True
        if (self.value==y.value):
            return False
        else:
            return True        
    def __cmp__(self,y):
        if (y == None):
            return False
        return self.value==y.value     
    def __eq__(self,y):
        if (y == None):
            return False
        return self.value==y.value
    @staticmethod
    def create (source_str):
        if (str.lower(source_str) == str (Target (Target.test))):
            return Target (Target.test)
        elif (str.lower(source_str) == str (Target (Target.local))):
            return Target (Target.local)
        elif (str.lower(source_str) == str (Target (Target.remote_ssh))):
            return Target (Target.remote_ssh)
        elif (str.lower(source_str) == str (Target (Target.planetlab))):
            return Target (Target.planetlab)
        elif (str.lower(source_str) == str (Target (Target.hen))):
            return Target (Target.hen)
        else:
            return Target (Target.undefined) 

if __name__ == "__main__":
    for s in  ["local", "remote_ssh", "planetlab", "hen"]:
        print s
    sys.exit(0)
   
