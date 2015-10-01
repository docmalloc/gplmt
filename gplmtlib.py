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

import asyncio
import getpass
import isodate
import logging
import lxml.etree
import os.path
import shlex
import signal
import xmlrpc.client
from concurrent.futures import FIRST_COMPLETED
from lxml.builder import E
from contextlib import contextmanager

__all__ = [
    "Testbed",
    "Experiment",
    "ExperimentExecutionError",
    "ExperimentSyntaxError",
    "process_includes",
]


class Experiment:
    def __init__(self, experiment_xml, settings):
        self.experiment_xml = experiment_xml
        self.settings = settings
        self.targets = self.experiment_xml.findall('/targets/target')
        self.steps = self.experiment_xml.find("steps")
        self.tasklists_env = {}

        for x in experiment_xml.xpath("/experiment/tasklists/tasklist[@name]"):
            self.tasklists_env[x.get('name')] = x

    @classmethod
    def from_file(cls, filename, settings):
        try:
            document = lxml.etree.parse(filename)
        except OSError:
            raise ExperimentSetupError("Could not read experiment file\n")

        root = document.getroot()

        if root.tag != "experiment":
            print("Fatal: Root element must be 'experiment', not '%s'" % (root.tag,))
            sys.exit(1)

        process_includes(document, parent_filename=filename)
        establish_names(document)
        return Experiment(document, settings)

    def _run(self):
        testbed = Testbed(self.targets, self.settings)

        try:
            for step in self.steps:
                testbed.run_step(step, self.tasklists_env)
            testbed.join_all()
        except ExperimentExecutionError as e:
            logging.error("Experiment error: %s", e.message)
            raise Exception()

        testbed.run_teardowns(self.tasklists_env)

    def run(self):
        try:
            self._run()
        finally:
            # Necessary due to http://bugs.python.org/issue23548
            loop = asyncio.get_event_loop()
            loop.close()


class Testbed:
    # XXX: maybe pass args object instead of single params
    def __init__(self, targets_xml, settings):
        self.batch = settings.batch
        self.ssh_cooldown = settings.ssh_cooldown
        self.logroot_dir = settings.logroot_dir
        self.nodes = {}
        self.groups = {}
        self.settings = settings
        for el in targets_xml:
            self._process_declaration(el)

        self.tasks = []

        self.teardowns = []

        # counter for sequential numbering of task runs
        self.run_counter = 0

        self.ssh_cooldown_lock = asyncio.Lock()
        self.ssh_parallel_sema = asyncio.Semaphore(settings.ssh_parallelism)

    @asyncio.coroutine
    def ssh_acquire(self):
        yield from self.ssh_parallel_sema.acquire()
        if self.ssh_cooldown is not None:
            yield from self.ssh_cooldown_lock.acquire()
            # as soon as we get the lock,
            # we schedule a function that releases it
            # after the cooldown period.
            loop = asyncio.get_event_loop()
            loop.call_later(
                    self.ssh_cooldown,
                    lambda: self.ssh_cooldown_lock.release())

    def run_teardowns(self, tasklists_env):
        try:
            for target, tasklist in self.teardowns:
                self.schedule(target, tasklist, tasklists_env)
                self.join_all()
        except ExperimentExecutionError as e:
            logging.error("Error during teardown:  %s" % (e.message))

    def ssh_release(self):
        # Note that the cooldown lock will
        # be released by a timer.
        self.ssh_parallel_sema.release()

    def join_all(self):
        if not len(self.tasks):
            logging.info("Synchronized nodes (no tasks)")
            return
        loop = asyncio.get_event_loop()
        join_coro = asyncio.wait(self.tasks)
        done, pending = loop.run_until_complete(join_coro)
        for task in done:
            # throw potential exceptions
            task.result()
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
            self.nodes[name] = LocalNode(el, testbed=self)
            return
        if tp == 'ssh':
            self.nodes[name] = SSHNode(el, testbed=self)
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

        logging.info("Making RPC call to planetlab")

        try:
            node_ids = server.GetSlices(auth, [slicename], ['node_ids'])[0]['node_ids']

            node_hostnames = [node['hostname'] for node in server.GetNodes(auth, node_ids, ['hostname'])]
        except Exception as e:
            raise ExperimentSetupError("PlanetLab API call failed")

        logging.info("Got response from planetlab")

        members = []
        for num, hostname in enumerate(node_hostnames):
            name = "_pl_" + slicename + "." + str(num)
            cfg = E.target(
                    {"type": "ssh", "name": name},
                    E.host(hostname), E.user(slicename))
            self.nodes[name] = SSHNode(cfg, testbed=self)
            members.append(name)
        self.groups[groupname] = members

    def _resolve_target(self, target_name):
        target_nodes = []
        unresolved_names = set(target_name.split(' '))

        while len(unresolved_names):
            n = unresolved_names.pop()
            if n in self.nodes:
                target_nodes.append(self.nodes[n])
            elif n in self.groups:
                unresolved_names.update(self.groups[n])
            else:
                raise Exception("Unknown target %s" % (n,))

        return target_nodes

    def schedule(self, target_name, tasklist_xml, tasklists_env):
        target_nodes = self._resolve_target(target_name)
        for node in target_nodes:
            coro = node.run(tasklist_xml, self, tasklists_env)
            task = asyncio.async(coro)
            self.tasks.append(task)

    def run_step(self, step_xml, tasklists_env):
        if step_xml.tag not in self._step_table:
            raise ExperimentSyntaxError("Invalid step '%s'" % (step_xml.tag,))
        step_method = self._step_table[step_xml.tag]
        step_method(self, step_xml, tasklists_env)

    def _step_synchronize(self, step_xml, tasklists_env):
        self.join_all()

    def _step_tasklist(self, step_xml, tasklists_env):
        targets_def = step_xml.get("targets")
        if targets_def is None:
            logging.warn("step has no targets, skipping")
            return
        tasklist_name = step_xml.get("tasklist")
        if tasklist_name is None:
            logging.warn("step has no tasklist, skipping")
            return
        tasklist = tasklists_env.get(tasklist_name)
        if tasklist is None:
            raise ExperimentSyntaxError("Tasklist '%s' not found" % (tasklist_name,))
        self.schedule(targets_def, tasklist, tasklists_env)

    def _step_teardown(self, step_xml, tasklists_env):
        targets_def = step_xml.get("targets")
        if targets_def is None:
            logging.warn("register-teardown has no targets, skipping")
            return
        tasklist_name = step_xml.get("tasklist")
        if tasklist_name is None:
            logging.warn("register-teardown has no tasklist, skipping")
            return
        tasklist = tasklists_env.get(tasklist_name)
        if tasklist is None:
            raise ExperimentSyntaxError("Tasklist '%s' not found" % (tasklist_name,))
        logging.info("Registering teardown for '%s' on '%s'", tasklist_name, targets_def)
        self.teardowns.append((targets_def, tasklist))

    def _step_loop_counted(self, step_xml):
        num_iter_attr = child.get("iterations")
        if num_iter_attr is None:
            logging.error("counted loop is missing attribute iterations, skipping")
            return
        try:
            num_iter = int(num_iter_attr)
        except ValueError:
            logging.error("counted loop has malformed attribute iterations (%s), skipping", num_iter_attr)
            return
        logging.info("Starting counted loop")
        for x in range(num_iter):
            run_steps(list(child))
            testbed.join_all()
        logging.info("Done with counted loop")

    _step_table = {
            'step': _step_tasklist,
            'register-teardown': _step_teardown,
            'synchronize': _step_synchronize,
            }


def find_text(node, query):
    res = node.find(query)
    if res is None:
        return None
    return res.text


def get_delay(node, prefix):
    t_relative = node.find(prefix + '_relative')
    if t_relative is not None:
        return isodate.parse_duration(t_relative.text).total_seconds()
    t_absolute = node.find(prefix + '_absolute')
    if t_absolute is not None:
        st = isodate.parse_datetime(t_absolute.text)
        diff = st - datetime.datetime.now()
        return diff.total_seconds()
    return None



class RunTaskPolicy:
    def __init__(self, node, run_xml):
        self.node = node
        self.command = run_xml.text
        self.task_name = run_xml.get('name')
        expected_status_el = run_xml.get('expected-status')
        if expected_status_el is None:
            self.expected_status = None
        else:
            try:
                self.expected_status = int(expected_status_el)
            except ValueError:
                expected_status = None
                logging.error(
                        "Invalid number '%s'",
                        expected_status_el)

    def _mklogdir(self):
        dir = os.path.join(self.node.testbed.logroot_dir, self.node.name)
        os.makedirs(dir, exist_ok=True)
        return dir

    @contextmanager
    def open_stdout(self):
        if self.node.testbed.logroot_dir is None:
            yield None
            return
        outfilename = os.path.join(
                self._mklogdir(),
                "%s.%s.out" % (self.task_name, self.node.testbed.run_counter))
        with open(outfilename, "w") as f:
            yield f

    def check_status(self, status):
        if self.expected_status is None:
            return
        if self.expected_status == status:
            return
        # XXX: better error message
        logging.error("Unexpected status")
        raise ExperimentExecutionError("Unexpected status")
    
    @contextmanager
    def open_stderr(self):
        if self.node.testbed.logroot_dir is None:
            yield None
            return
        errfilename = os.path.join(
                self._mklogdir(),
                "%s.%s.err" % (self.task_name, self.node.testbed.run_counter))
        with open(errfilename, "w") as f:
            yield f


class Node:
    def __init__(self, node_xml, testbed):
        self.testbed = testbed
        self.name = node_xml.get('name')
        self._env = {}
        for env_xml in node_xml.findall('export-env'):
            name = env_xml.get('var')
            if name is None:
                raise ExperimentSyntaxError("export-env misses 'var' attribute")
            value = env_xml.get('value')
            if value is None:
                v = os.environ.get(name)
                if v is None:
                    raise ExperimentSyntaxError("variable '%s' not found in environment of GPLMT control host" % (name,))
                value = v
            self._env[name] = value

    @property
    def env(self):
        return self._env.copy()


    @asyncio.coroutine
    def _run_list(self, tasklist_xml, testbed, tasklists_env):
        for task_xml in tasklist_xml:
            yield from self._run_task(task_xml, testbed, tasklists_env)

    @asyncio.coroutine
    def run(self, tasklist_xml, testbed, tasklists_env, memo=None, noclean=False):
        list_name = tasklist_xml.get('name', '(unnamed)')
        logging.info("running tasklist '%s'", list_name)
        # actual tasks, with declarations stripped
        actual_tasks = []
        cleanup_task = None
        cleanup_name = tasklist_xml.get('cleanup')
        if cleanup_name is not None:
            cleanup_task = tasklists_env.get(cleanup_name)
            if cleanup_task is None:
                raise ExperimentSyntaxError("cleanup task %s not found\n" % (cleanup_name,))
        error_policy = tasklist_xml.get('on-error')
        if error_policy is None:
            error_policy = 'stop-tasklist'
        timeout_str = tasklist_xml.get('timeout')
        timeout = None
        if timeout_str is not None:
            timeout = isodate.parse_duration(timeout_str).total_seconds()
        coro = self._run_list(tasklist_xml, testbed, tasklists_env)
        try:
            logging.info(
                    "Running tasklist %s with timeout of %s.",
                    list_name, timeout)
            yield from asyncio.wait_for(asyncio.async(coro), timeout)
        except asyncio.TimeoutError:
            # XXX: be more verbose!
            logging.warning(
                    "Tasklist %s on node %s timed out",
                    list_name,
                    self.name)
        except ExperimentExecutionError:
            logging.error("Tasklist execution (%s on %s) raised exception", list_name, self.name)
            if error_policy == 'panic':
                # Give up without cleaning up
                raise
            if cleanup_task is not None and not noclean:
                logging.error("Experiment execution failed, but cleaning up first")
                # Allow cleanup task to run, but without recursive cleaning.
                yield from self.run(cleanup_task, testbed, tasklists_env, noclean=True)
            if error_policy == 'stop-tasklist':
                pass
            elif error_policy == 'stop-experiment':
                raise

        if cleanup_task is not None and not noclean:
            # Allow cleanup task to run, but without recursive cleaning.
            yield from self.run(cleanup_task, testbed, tasklists_env, noclean=True)

    @asyncio.coroutine
    def _run_task_run(self, task_xml):
        pol = RunTaskPolicy(self, task_xml)

        with pol.open_stdout() as stdout, pol.open_stderr() as stderr:
            yield from self.execute(pol, stdout, stderr)

    @asyncio.coroutine
    def _run_task(self, task_xml, testbed, tasklists_env):
        name = task_xml.get('name', '(unnamed-task)')
        if task_xml.get('enabled', 'true').lower() == 'false':
            logging.info("Task %s disabled", name)
            return
        if task_xml.tag == 'run':
            yield from self._run_task_run(task_xml)
            return
        if task_xml.tag == 'get':
            source = find_text(task_xml, 'source')
            destination = find_text(task_xml, 'destination')
            yield from self.get(source, destination)
            return
        if task_xml.tag == 'put':
            source = find_text(task_xml, 'source')
            destination = find_text(task_xml, 'destination')
            yield from self.put(source, destination)
            return
        if task_xml.tag == 'sequence':
            for child_task in task:
                yield from self._run_task(child_task)
            return
        if task_xml.tag == 'parallel':
            parallel_tasks = []
            for child_task in task_xml:
                coro = self._run_task(child_task)
                task = asyncio.async(coro)
                parallel_tasks.append(task)
            done, pending = yield from asyncio.wait(parallel_tasks)
            for task in done:
                task.result()
            return


def wrap_env(cmd, env):
    """
    Wrap a shell command in a call to 'env' with
    the given environment variables.  Handles escaping.
    """
    argv = ['env']
    for k, v in env.items():
        pair = '%s=%s' % (k, v)
        argv.append(shlex.quote(pair))

    argv.append('sh')
    argv.append('-c')
    argv.append(shlex.quote(cmd))
    return " ".join(argv)



class LocalNode(Node):
    def __init__(self, node_xml, testbed):
        super().__init__(node_xml, testbed)

    @asyncio.coroutine
    def execute(self, pol, stderr, stdout):
        logging.info("Executing command '%s'", pol.command)
        proc = yield from asyncio.create_subprocess_shell(
                pol.command, stdout=stdout, stderr=stderr, env=self.env)
        ret = yield from proc.wait()
        pol.check_status(ret)

    @asyncio.coroutine
    def put(self, source, destination):
        logging.warn("Task type 'put' not available for local nodes, ignoring.")

    @asyncio.coroutine
    def get(self, source, destination):
        logging.warn("Task type 'get' not available for local nodes, ignoring.")


class SSHNode(Node):
    def __init__(self, node_xml, testbed):
        super().__init__(node_xml, testbed)
        if self.name is None:
            raise ExperimentSyntaxError("Node name must be given")
        self.host = find_text(node_xml, 'host')
        if self.host is None:
            raise ExperimentSyntaxError("SSH target requires host")
        self.user = find_text(node_xml, 'user')
        if self.user is None:
            raise ExperimentSyntaxError("SSH target requires user")
        self.port = find_text(node_xml, 'port')
        extra = find_text(node_xml, 'extra-args')
        if extra is None:
            self.extra = []
        else:
            self.extra = shlex.split(extra)

        if self.port is None:
            self.port = 22
        self.target = "%s@%s" % (self.user, self.host)


    @asyncio.coroutine
    def establish_master(self):
        control_path = self.get_control_path()
        if os.path.exists(control_path):
            logging.info("Using existing master")
            # XXX: increase semaphore
            return
        logging.info("Creating new master")
        argv = ['ssh']
        argv.extend(['-o', 'BatchMode=yes'])
        argv.extend(['-o', 'StrictHostKeyChecking=no'])
        argv.extend(['-o', 'ControlPath='+control_path])
        argv.extend(['-o', 'ControlMaster=yes'])
        # We could also specify a timeout here ...
        argv.extend(['-o', 'ControlPersist=yes'])
        argv.extend([self.target, 'true'])
        proc = yield from asyncio.create_subprocess_exec(
                *argv)
        ret = yield from proc.wait()
        if ret != 0:
            raise ExperimentExecutionError("Failed to create SSH master connection to '%s'" % (self.name,))

    def get_control_path(self):
        p = "~/.ssh/gplmt-%(host)s@%(user)s:%(port)s" % {
            "host": self.host, "user": self.user, "port": self.port
        }
        return os.path.expanduser(p)

    @asyncio.coroutine
    def execute(self, pol, stdout, stderr):
        yield from self.testbed.ssh_acquire()

        cmd = pol.command

        logging.info("Executing command '%s'", pol.command)

        # Add code to command to set environment variables
        # on the target host.
        if self.env:
            cmd = wrap_env(cmd, self.env)

        yield from self.establish_master()

        argv = ['ssh']
        # XXX: make optional
        argv.extend(['-o', 'StrictHostKeyChecking=no'])
        # XXX: make optional
        argv.extend(['-o', 'BatchMode=yes'])
        argv.extend(['-o', 'ControlMaster=no'])
        control_path = self.get_control_path()
        argv.extend(['-o', 'ControlPath='+control_path])
        argv.extend(['-p', str(self.port)])
        argv.extend(self.extra)
        argv.extend([self.target])
        argv.extend(['--', cmd])
        logging.info("SSH command '%s'", repr(argv))
        proc = yield from asyncio.create_subprocess_exec(
                *argv,
                stdout=stdout, stderr=stderr)
        ret = yield from proc.wait()
        logging.info("SSH command terminated")
        pol.check_status(ret)

        self.testbed.ssh_release()

    @asyncio.coroutine
    def scp_copy(self, scp_source, scp_destination):
        yield from self.testbed.ssh_acquire()
        yield from self.establish_master()
        argv = ['scp']
        # XXX: make optional
        argv.extend(['-o', 'StrictHostKeyChecking=no'])
        # XXX: make optional
        argv.extend(['-o', 'BatchMode=yes'])
        # XXX: make optional
        argv.extend(['-o', 'BatchMode=yes'])
        argv.extend(['-o', 'ControlMaster=no'])
        argv.extend(['-P', str(self.port)])
        argv.extend(self.extra)
        argv.extend(['--', scp_source, scp_destination])
        logging.info("SCP command '%s'", repr(argv))
        proc = yield from asyncio.create_subprocess_exec(*argv)
        ret = yield from proc.wait()
        self.testbed.ssh_release()
        if ret != 0:
            raise ExperimentExecutionError("Copy from '%s' to '%s' failed" % (scp_source, scp_destination))

    @asyncio.coroutine
    def put(self, source, destination):
        if os.path.isabs(source):
            scp_source = source
        else:
            scp_source = './' + source
        scp_destination = '%s:%s' % (self.target, destination)
        yield from self.scp_copy(scp_source, scp_destination)

    @asyncio.coroutine
    def get(self, source, destination):
        scp_source = '%s:%s' % (self.target, source)
        if os.path.isabs(source):
            scp_destination = destination
        else:
            scp_destination = './' + destination
        yield from self.scp_copy(scp_source, scp_destination)


class ExperimentSyntaxError(Exception):
    def __init__(self, message):
        self.message = message


class ExperimentExecutionError(Exception):
    def __init__(self, message):
        self.message = message


class ExperimentSetupError(Exception):
    def __init__(self, message):
        self.message = message


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


def prefix_names(el, prefix):
    for element in el.iter():
        if 'name' not in el:
            continue
        if element.tag not in ('target', 'tasklist', 'run'):
            continue
        element['name'] = prefix + element['name']


def establish_names(el):
    """Make sure that every interesting
    element has a name"""
    counter = 0
    for element in el.iter():
        if element.tag not in ('run',):
            continue
        if element.get('name') is None:
            # XXX: maybe we could use filename/line?
            # We do have .sourceline available sometimes
            element.set('name', '_anon' + str(counter))
            counter += 1


def process_includes(doc, parent_filename, env=None, memo=None):
    includes = doc.findall('//include')
    for el in includes:
        filename = el.get('file')
        if filename is None:
            raise ExperimentSyntaxError("Filename missing in include")
        # XXX: Implement defaulting, shell style.
        filename = os.path.expandvars(filename)
        # Search relative paths relative to parent document
        if not os.path.isabs(filename):
            parent_dir = os.path.dirname(os.path.realpath(parent_filename))
            filename = os.path.join(parent_dir, filename)
        filename = os.path.realpath(filename)
        if memo is not None and filename in memo:
            raise ExperimentSyntaxError("recursive include")
        xml_parser = lxml.etree.XMLParser(remove_blank_text=True)
        doc = lxml.etree.parse(filename, parser=xml_parser)
        # XXX: Check that including this element here
        # preserves document validity.
        # XXX: Handle namespace prefixing
        new_memo = {filename}
        if memo is not None:
            new_memo.update(memo)
        process_includes(doc, filename, memo=new_memo)
        replace(el, doc.getroot())
