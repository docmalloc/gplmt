#!/usr/bin/env python3
#
#  gplmt-light, a lightweight distributed testbed controller
#  Copyright (C) 2015  Florian Dold
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os.path
import lxml.etree
from lxml.builder import E
import asyncio
import logging
import signal
import getpass
import xmlrpc.client
from concurrent.futures import FIRST_COMPLETED


signal.signal(signal.SIGCHLD, signal.SIG_DFL)

class Testbed:
    def __init__(self, targets_xml,dry=False):
        self.nodes = {}
        self.groups = {}
        for el in targets_xml:
            self._process_declaration(el)

        self.tasks = []

    def join_all(self):
        if not len(self.tasks):
            logging.info("Synchronized nodes (no tasks)")
            return
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.wait(self.tasks))
        logging.info("Synchronized nodes")

    def join_one(self):
        if not len(self.tasks):
            logging.info("Synchronized nodes (no tasks)")
            return
        loop = asyncio.get_event_loop()
        done, pending = loop.run_until_complete(asyncio.wait(self.tasks, return_when=FIRST_COMPLETED))
        logging.info("Synchronized nodes")

    def _process_group(self, els):
        members = []
        for el in els:
            refname = el.get('ref')
            if refname is not None:
                members.append(refname)
                continue
            name = el.get('name')
            if name is None:
                raise ExperimentSyntaxError("target must have ref or name")
            members.append(name)
            self._process_declaration(el)
        self.groups[els.get('name')] = members
    

    def _process_declaration(self, el):
        name = el.get('name')
        if name is None:
            raise Exception("target needs name")
        tp = el.get('type')
        if tp is None:
            raise Exception("target needs type")
        if tp == 'local':
            self.nodes[name] = LocalNode(el)
            return
        if tp == 'ssh':
            self.nodes[name] = SSHNode(el)
            return
        if tp == 'group':
            self._process_group(el)
            return
        if tp == 'planetlab':
            self._process_pl_slice(el)
            return
        raise Exception("Unknown type: %s" % (tp,))

    def _process_pl_slice(self, el):
        api_url = find_text(el, 'apiurl')
        if not api_url:
            raise ExperimentSyntaxError("Planetlab slice requires 'apiurl'")
        slicename = find_text(el, "slicename")
        if not slicename:
            raise ExperimentSyntaxError("Planetlab slice requires 'slicename'")

        groupname = el.get("name")
        if groupname is None:
            groupname = slicename

        server = xmlrpc.client.ServerProxy(api_url)

        user = find_text(el, 'user')
        if user is None:
            raise ExperimentSyntaxError("Planetlab slice requires 'user'")
        pw = find_text(el, 'password')
        if pw is None:
            # XXX: check if interaction is allowed
            pw = getpass.getpass("Planetlab Password: ")
        auth = {}
        auth['Username'] = user
        auth['AuthString'] = pw
        auth['AuthMethod'] = "password"

        try:
            node_ids = server.GetSlices(auth, [slicename], ['node_ids'])[0]['node_ids']

            node_hostnames = [node['hostname'] for node in server.GetNodes(auth, node_ids, ['hostname'])]
        except Exception as e:
            # XXX: Catch specific exceptions
            logging.error("Planetlab API call failed, not adding nodes", exc_info=True)
            # XXX: Propagate the error
            return

        members = []
        for num, hostname in enumerate(node_hostnames):
            cfg = E.target({"type":"ssh"})
            name = "_pl." + groupname + "." + str(num)
            self.nodes[name] = SSHNode(cfg)
            members.append(name)
        self.groups[groupname] = members


    def _resolve_target(self, target_name):
        target_nodes = []
        unresolved_names = {target_name}

        while len(unresolved_names):
            n = unresolved_names.pop()
            if n in self.nodes:
                target_nodes.append(self.nodes[n])
            elif n in self.groups:
                unresolved_names.update(self.groups[n])
            else:
                raise Exception("Unknown target %s" % (n,))

        return target_nodes


    def schedule(self, target_name, tasklist):
        print("groups", self.groups)
        print("resolving target", target_name)
        target_nodes = self._resolve_target(target_name)
        for node in target_nodes:
            coro = node.run(tasklist)
            loop = asyncio.get_event_loop()
            task = loop.create_task(coro)
            self.tasks.append(task)


def find_text(node, query):
    res = node.find(query)
    if res is None:
        return None
    return res.text


class Node:
    @asyncio.coroutine
    def run(self, tasklist):
        self.list_name = tasklist.get('name', '(unnamed)')
        logging.info("running tasklist '%s'", self.list_name)
        for task in tasklist:
            yield from self._run_task(task)

    @asyncio.coroutine
    def _sleep_until_ready(self, task):
        # XXX: Implement
        pass

    @asyncio.coroutine
    def _run_until_timeout(self, coro, task_xml):
        # XXX: Implement
        yield from asyncio.async(coro)

    @asyncio.coroutine
    def _run_task(self, task):
        name = task.get('name', '(unnamed-task)')
        if task.get('enabled', 'true').lower() == 'false':
            logging.info("Task %s disabled", name)
            return
        yield from self._sleep_until_ready(task)
        if task.tag == 'run':
            command_el = task.find('command')
            if command_el is None:
                logging.warn(
                        "Task %s from list %s is of type 'run', but has no command",
                        name, self.list_name)
                return
            command = command_el.text
            expected_ret_el = task.find('expected_return_code')
            if expected_ret_el is None:
                expected_return_code = None
            else:
                try:
                    expected_ret = int(expected_ret_el.text)
                except ValueError:
                    expected_ret = None
                    logging.error("Invalid number '%s'",
                            expected_ret_el.text)
            expected_output_el = task.find('expected_output')
            if expected_output_el is None:
                expected_output = None
            else:
                expected_output = expected_output_el.text
            coro = self.execute(command,
                    expected_return_code, expected_output)

            yield from self._run_until_timeout(coro, task)
            return
        if task.tag == 'get':
            source = find_text(task, 'source')
            destination = find_text(task, 'destination')
            coro = self.get(source, destination)
            yield from self._run_until_timeout(coro, task)
            return
        if task.tag == 'put':
            source = find_text(task, 'source')
            destination = find_text(task, 'destination')
            coro = self.put(source, destination)
            yield from self._run_until_timeout(coro, task)
            return
        if task.tag == 'sequence':
            for child_task in task:
                self._run_task(child_task)
            return
        if task.tag == 'parallel':
            parallel_tasks = []
            for child_task in task:
                coro = self._run_task(child_task)
                loop = asyncio.get_event_loop()
                task = loop.create_task(coro)
                parallel_tasks.append(task)
            yield from asyncio.wait(parallel_tasks)
            return


class LocalNode(Node):
    def __init__(self, node_xml):
        pass

    @asyncio.coroutine
    def execute(self, command, expected_ret, expected_out):
        logging.info("Executing command '%s'", command)
        proc = yield from asyncio.create_subprocess_shell(command)
        yield from proc.wait()

    @asyncio.coroutine
    def put(self, source, destination):
        logging.warn("Task type 'put' not available for local nodes, ignoring.")
        
    @asyncio.coroutine
    def get(self, source, destination):
        logging.warn("Task type 'get' not available for local nodes, ignoring.")


class SSHNode(Node):
    def __init__(self, node_xml):
        self.host = find_text(node_xml, 'host')
        if self.host is None:
            raise ExperimentSyntaxError("SSH target requires host")
        self.user = find_text(node_xml, 'user')
        if self.user is None:
            raise ExperimentSyntaxError("SSH target requires user")
        self.port = find_text(node_xml, 'port')
        if self.port is None:
            self.port = 22
            self.portstr = ""
        else:
            self.portstr = "-p %s" % (self.port,)
        self.target = "%s@%s" % (self.user, self.host)

    @asyncio.coroutine
    def execute(self, command, expected_ret, expected_out):
        logging.info("Executing command '%s'", command)
        ssh_cmd = ("ssh -o StrictHostKeyChecking=no %s %s -- %s" % (
            self.portstr, self.target, command))
        logging.debug("SSH command '%s'", ssh_cmd)
        proc = yield from asyncio.create_subprocess_shell(ssh_cmd)
        yield from proc.wait()

    @asyncio.coroutine
    def put(self, source, destination):
        logging.warn("Task type 'put' not available for local nodes, ignoring.")
        
    @asyncio.coroutine
    def get(self, source, destination):
        logging.warn("Task type 'get' not available for local nodes, ignoring.")


class ExperimentSyntaxError(Exception):
    pass


def replace(element, replacement):
    parent = element.getparent()
    if parent is None:
        raise ValueError("Can't replace element without parent")
    for idx, child in enumerate(parent):
        if child is element:
            child_idx = idx
            break
    else:
        raise Exception("concurrent modification")
    parent.remove(element)
    parent.insert(child_idx, replacement)


def process_includes(doc, env=None):
    includes = doc.findall('//include')
    for el in includes:
        filename = el.get('file')
        if filename is None:
            raise ExperimentSyntaxError("Filename missing in include")
        # XXX: Implement defaulting, shell style.
        filename = os.path.expandvars(filename)
        xml_parser = lxml.etree.XMLParser(remove_blank_text=True)
        doc = lxml.etree.parse(filename, parser=xml_parser)
        # XXX: Check that including this element here
        # preserves document validity.
        # XXX: Handle recursive include processing
        # XXX: Handle namespace prefixing
        replace(el, doc.getroot())

