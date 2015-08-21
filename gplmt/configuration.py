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

Configuration
"""


import configparser
import logging
import os
import sys
from enum import Enum

class TransferMode(Enum):
    none=0
    sftp=1
    scp=2


class ConfigurationError(Exception):
    pass

class Configuration:
    def __init__(self, filename=None):
        """ Create a new Configuration.

            return False
        Optionally load values from 'filename'.
        """
        if filename is None:
            filename = os.path.join(os.path.expanduser("~"), ".gplmt", "gplmt.conf")
            logging.info("Falling back to default config %s", filename)
        else:
            logging.info("Loading configuration file %s", self.gplmt_filename)
        self.config = configparser.RawConfigParser()
        try:
            # Strange API, config.read returns list of files
            # successfully parsed.
            parsed_files = self.config.read(filename)
        except configparser.Error as e:
            raise ConfigurationError("Error parsing configuration: " + str(e))
        if len(parsed_files) != 1:
            raise ConfigurationError("Configuration file %s not found" % (filename))

        self._parse('pl_slicename', 'planetlab', 'slice')
        self._parse('pl_api_url', 'planetlab', 'api_url')
        self._parse('pl_password', 'planetlab', 'password')
        self._parse('pl_username', 'planetlab', 'username')
        self._parse('pl_keyfile', 'planetlab', 'keyfile')
        self._parse('pl_keyfile_password', 'planetlab', 'keyfile_password')

        self._parse('gplmt_taskfile', 'gplmt', 'tasks', converter=expand_filename)
        self._parse('gplmt_nodesfile', 'gplmt', 'nodes', converter=expand_filename)
        self._parse('gplmt_parallelism', 'gplmt', 'max_parallelism', converter=int)
        self._parse('gplmt_notifications', 'gplmt', 'notification')
        self._parse('gplmt_userdir', 'gplmt', 'userdir')

        # XXX(FlorianDold): Why do we need these here?
        self._parse('bb_template', 'buildbot', 'template')
        self._parse('bb_task_file', 'buildbot', 'result_tasks_file', converter=expand_filename)
        self._parse('bb_result_cfg', 'buildbot', 'result_cfg', converter=expand_filename)
        self._parse('bb_bb_cmd', 'buildbot', 'buildbot_command')
        self._parse('bb_master', 'buildbot', 'master')
        self._parse('bb_force_pw', 'buildbot', 'force_pw')
        self._parse('bb_force_user', 'buildbot', 'force_user')
        self._parse('bb_force_enable', 'buildbot', 'force_enable')
        self._parse('bb_slaveport', 'buildbot', 'slaveport')
        self._parse('bb_webport', 'buildbot', 'webport')

        self._parse('ssh_username', 'ssh', 'username')
        self._parse('ssh_add_unknown_hostkeys', 'ssh', 'add_unknown_hostkeys')
        # XXX(FlorianDold): option name is odd, 'ssh_' should be stripped
        self._parse('ssh_use_known_hosts', 'ssh', 'ssh_use_known_hosts')
        # XXX(FlorianDold): option name is odd, 'ssh_' should be stripped
        self._parse('ssh_keyfile', 'ssh', 'ssh_keyfile')
        # XXX(FlorianDold): option name is odd, 'ssh_' should be stripped
        self._parse('ssh_password', 'ssh', 'ssh_password')
        # XXX(FlorianDold): option name is odd, 'ssh_' should be stripped
        self._parse('ssh_transfer', 'ssh', 'ssh_transfer', converter=conv_ssh_transfer)

    def upgrade(self, name, proposed_value):
        old_value = getattr(self, name, None)
        if old_value is None:
            setattr(self, name, proposed_value)

    def _parse(self, name, cfg_section, cfg_option, converter=str, default=None, required=False):
        raw_val = self.config.get(cfg_section, cfg_option, fallback=None)
        if raw_val is None:
            if required:
                msg = "Required option '%s' in section '%s' not found." % (cfg_option, cfg_option)
                raise ConfigurationError(msg)
            val = default
        val = converter(raw_val)
        setattr(self, name, val)



