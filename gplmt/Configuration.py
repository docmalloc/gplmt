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
# Configuration


try:
    import ConfigParser
    import os
    import sys
except ImportError as e: 
    print "That's a bug! please check README: " + str(e)
    sys.exit (1) 

class TransferMode:
    none=0
    sftp=1
    scp=2

class Configuration:
    def __init__(self, filename, logger):
        assert (None != logger)
        self.gplmt_filename = filename
        self.gplmt_logger = logger
        self.gplmt_parallelism = sys.maxint
        self.gplmt_notifications = ""
        self.gplmt_taskfile = None
        self.gplmt_nodesfile = None
        self.gplmt_userdir = ""
        self.hen_gw = None
        self.hen_gw_username = None
        self.hen_gw_keyfile = None
        self.hen_gw_keyfile_password = None
        self.hen_node_username = None
        self.hen_node_keyfile = None
        self.hen_node_password = None
        self.pl_slicename = ""
        self.pl_api_url = ""
        self.pl_username = None
        self.pl_password = None
        self.pl_keyfile = None
        self.pl_keyfile_password = None
        self.ssh_username = ""
        self.ssh_add_unkown_hostkeys = False
        self.ssh_keyfile = None
        self.ssh_password = ""
        self.ssh_use_known_hosts = False
        self.ssh_transfer = TransferMode.scp
        self.bb_template = ""
        self.bb_task_file = ""
        self.bb_result_cfg = ""
        self.bb_bb_cmd = ""
        self.bb_master = ""
        self.bb_force_enable = ""
        self.bb_force_user = ""
        self.bb_force_pw = ""
        self.bb_webport = 0
        self.bb_slaveport = 0
    def load (self):
        if (None == self.gplmt_filename):            
            default_cfg = os.path.expanduser("~") + os.sep + ".gplmt" + os.sep+ "gplmt.conf"
            if (False == os.path.exists (default_cfg)):
                print "Default configuration " +default_cfg+ " not found"
                return False
            else:
                self.gplmt_logger.log ("Default configuration " +default_cfg+ " found")
                self.gplmt_filename = default_cfg
        self.gplmt_logger.log ("Loading configuration file '" + self.gplmt_filename + "'")
        if (False == os.path.exists (self.gplmt_filename)):
            print "File does not exist: '" + self.gplmt_filename + "'"
            return False
        config = ConfigParser.RawConfigParser()
        try:
            config.read(self.gplmt_filename)
        except ConfigParser.Error as e:
            print "Error parsing configuration: " + str (e)
            return False
        
        # required values
        try:
            try: 
                self.pl_slicename = config.get("planetlab", "slice")
            except ConfigParser.NoOptionError as e:
                pass
            # optional values
            try:
                self.pl_api_url = config.get("planetlab", "api_url")
            except ConfigParser.NoOptionError as e:
                pass
            try:
                self.pl_username = config.get("planetlab", "username")
            except ConfigParser.NoOptionError as e:
                pass
            try:
                self.pl_password = config.get("planetlab", "password")
            except ConfigParser.NoOptionError as e:
                pass            
            try:
                self.pl_keyfile = os.path.expanduser(config.get("planetlab", "pl_keyfile"))
            except ConfigParser.NoOptionError as e:
                pass
            try: 
                self.pl_keyfile_password = config.get("planetlab", "pl_keyfile_password")
            except ConfigParser.NoOptionError as e:
                pass
        except ConfigParser.NoSectionError:
            pass                
        
        try:
            try: 
                self.hen_gw = config.get("hen", "hen_gw")
            except ConfigParser.NoOptionError as e:
                pass
            try:
                self.hen_gw_username = config.get("hen", "hen_gw_username")
            except ConfigParser.NoOptionError as e:
                pass
            try:
                self.hen_gw_keyfile = config.get("hen", "hen_gw_keyfile")
            except ConfigParser.NoOptionError as e:
                pass
            try:
                self.hen_gw_keyfile_password = config.get("hen", "hen_gw_keyfile_password")
            except ConfigParser.NoOptionError as e:
                pass
            try:
                self.hen_node_username = config.get("hen", "hen_node_username")
            except ConfigParser.NoOptionError as e:
                pass
            try:
                self.hen_node_keyfile = config.get("hen", "hen_node_keyfile")
            except ConfigParser.NoOptionError as e:
                pass
            try:
                self.hen_node_password = config.get("hen", "hen_node_password")
            except ConfigParser.NoOptionError as e:
                pass
        except ConfigParser.NoSectionError:
            pass

        try:          
            try: 
                # gplmt options
                self.gplmt_taskfile = os.path.expanduser(config.get("gplmt", "tasks"))
            except ConfigParser.NoOptionError as e:
                pass
            
            try: 
                self.gplmt_nodesfile = os.path.expanduser(config.get("gplmt", "nodes"))
            except ConfigParser.NoOptionError as e:
                pass

            try: 
                # gplmt options
                self.gplmt_parallelism = config.get("gplmt", "max_parallelism")
                self.gplmt_parallelism = int(self.gplmt_parallelism)
            except ConfigParser.NoOptionError as e:
                pass
            try: 
                self.gplmt_notifications = config.get("gplmt", "notification")
            except ConfigParser.NoOptionError as e:
                pass
            try: 
                self.gplmt_userdir = config.get("gplmt", "userdir")
            except ConfigParser.NoOptionError as e:
                pass
        except ConfigParser.NoSectionError:
            pass                

        # buildbot options
        try:
            try: 
                self.bb_template = config.get("buildbot", "template")
            except ConfigParser.NoOptionError as e:
                pass
            try: 
                self.bb_task_file = os.path.expanduser(os.path.expanduser(config.get("buildbot", "result_task_file")))
            except ConfigParser.NoOptionError as e:
                pass        
            try: 
                self.bb_result_cfg = os.path.expanduser(config.get("buildbot", "result_cfg"))
            except ConfigParser.NoOptionError as e:
                pass
            try: 
                self.bb_bb_cmd = config.get("buildbot", "buildbot_command")
            except ConfigParser.NoOptionError as e:
                pass
            try: 
                self.bb_master = config.get("buildbot", "master")
            except ConfigParser.NoOptionError as e:
                pass
            try: 
                self.bb_force_pw = config.get("buildbot", "force_pw")
            except ConfigParser.NoOptionError as e:
                pass
            try: 
                self.bb_force_user = config.get("buildbot", "force_user")
            except ConfigParser.NoOptionError as e:
                pass            
            try:
                self.bb_force_enable = config.get("buildbot", "force_enable")
            except ConfigParser.NoOptionError as e:
                pass                
            try: 
                self.bb_slaveport = config.get("buildbot", "slaveport")
            except ConfigParser.NoOptionError as e:
                pass
            try: 
                self.bb_webport = config.get("buildbot", "webport")
            except ConfigParser.NoOptionError as e:
                pass                         
        except ConfigParser.NoSectionError:
            pass                                
        
        # ssh options
        try:
            try: 
                self.ssh_username = config.get ("ssh", "ssh_username")
            except ConfigParser.NoOptionError as e:
                pass            
            try: 
                self.ssh_add_unkown_hostkeys = config.getboolean ("ssh", "add_unkown_hostkeys")
            except ConfigParser.NoOptionError as e:
                pass
            try: 
                self.ssh_use_known_hosts = config.getboolean ("ssh", "ssh_use_known_hosts")
            except ConfigParser.NoOptionError as e:
                pass
            try: 
                self.ssh_keyfile = os.path.expanduser(config.get("ssh", "ssh_keyfile")) 
            except ConfigParser.NoOptionError as e:
                pass
            try: 
                self.ssh_password = config.get("ssh", "ssh_password")
            except ConfigParser.NoOptionError as e:
                pass        
            try: 
                transfer = config.get("ssh", "ssh_transfer")
                if (transfer == "scp"):
                    self.ssh_transfer = TransferMode.scp
                elif (transfer == "sftp"):
                    self.ssh_transfer = TransferMode.sftp
                else:
                    print "Invalid ssh transfer mode: only SFTP or SCP are supported"
                    return False
            except ConfigParser.NoOptionError as e:
                pass  
        except ConfigParser.NoSectionError:
            pass           
        return True
        
if __name__ == "__main__":
    print "Nothing to do here!"
    sys.exit(1)
