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
import time
import sys
import subprocess
import re
from concurrent.futures import FIRST_COMPLETED
from lxml.builder import E
from contextlib import contextmanager
from dateutil.parser import parse

import src.helper as helper
from src.error import ExperimentSyntaxError, ExperimentExecutionError, ExperimentSetupError, StopExperimentException

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
        if self.steps is None:
            raise ExperimentSyntaxError("Element 'steps' missing.  Did you try to execute an extension library?")
        self.tasklists_env = {}

        for x in experiment_xml.xpath("/experiment/tasklists/tasklist[@name]"):
            self.tasklists_env[x.get('name')] = x

    @classmethod
    def from_file(cls, filename, settings):
        try:
            rng_file = settings.rng
            relaxng_doc = lxml.etree.parse(rng_file)
            relaxng = lxml.etree.RelaxNG(relaxng_doc)
            xml_parser = lxml.etree.XMLParser(remove_blank_text=True)
            document = lxml.etree.parse(filename, parser=xml_parser)
            if not relaxng.validate(document):
                print("Could not validate experiment file.")
                print("Please check your experiment description file following the given schema in: ", rng_file)
                print("If the given rng-file is not the one you want, please define your own using the --rng option.")
                sys.exit(1)
            # XXX: Maybe we want to keep the comments?
            # XXX: If that is then case, our processing logic needs to be more careful.
            lxml.etree.strip_elements(document, [lxml.etree.Comment])
        except OSError:
            raise ExperimentSetupError("Could not read experiment file\n")

        root = document.getroot()

        if root.tag != "experiment":
            print("Fatal: Root element must be 'experiment', not '%s'" % (root.tag,))
            sys.exit(1)

        establish_names(document)
        process_includes(document, parent_filename=filename)
        return Experiment(document, settings)

    @asyncio.coroutine
    def _run(self):
        testbed = Testbed(self.targets, self.settings)

        try:
            for step in self.steps:
                yield from testbed.run_step(step, self.tasklists_env)
            yield from testbed.join()
        except ExperimentSyntaxError as e:
            logging.error("Syntax error: %s", e.message)
        except StopExperimentException as e:
            logging.error("Stop requested (%s)", e.scope)

        yield from testbed.run_teardowns(self.tasklists_env)

        # Take care of stuff that was aborted or background tasks
        yield from testbed.cancel_pending()

    def run_synchronous(self):
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self._run())
        finally:
            # Necessary due to http://bugs.python.org/issue23548
            loop.close()


@asyncio.coroutine
def run_delayed(coro, delay):
    yield from asyncio.sleep(delay)
    res = yield from coro
    return res


class ExecutionContext:
    def __init__(self, testbed):
        self.testbed = testbed
        self.tasks = []
        self.var = {}


    @asyncio.coroutine
    def cancel_pending(self):
        """Cancel all pending tasks"""
        if not self.tasks:
            return
        for p in self.tasks:
            p.cancel()
        yield asyncio.wait(self.tasks)

    @asyncio.coroutine
    def join(self, targets=None):
        """ Block on pending tasks until
        complete or requested to stop by an exception"""
        if not len(self.tasks):
            logging.info("Synchronized nodes (no tasks)")
            return
        while self.tasks:
            try:
                done, ts = yield from asyncio.wait(self.tasks, return_when=FIRST_COMPLETED)
                self.tasks = list(ts)
                del ts
                logging.info('%s tasks done, %s task pending', len(done), len(self.tasks))
                for task in done:
                    # throw potential exceptions
                    task.result()
            except StopExperimentException as e:
                logging.info("got stop experiment exception")
                if e.scope in ('stop-tasklist', 'stop-step'):
                    logging.info("stopped execution (%s)", e.scope)
                elif e.scope == 'stop-experiment':
                    logging.info("stopping experiment")
                    raise
            # We can break if no pending
            # tasks belong to the targets we join on.
            if targets is not None:
                done = True
                for p in self.tasks:
                    if p.gplmt_node in targets:
                        done = False
                if done:
                    break
            # We can also stop if we only wait on things from
            # background tasks.
            done = True
            for p in self.tasks:
                if not p.gplmt_background:
                    done = False
            if done:
                break
        logging.info("Synchronized nodes")

    def schedule_tasklist(self, target_name, tasklist_xml, tasklists_env, background, delay=None, var_env={}, stop_time=None):
        target_nodes = self.testbed._resolve_target(target_name)
        for node in target_nodes:
            coro = node.run_tasklist(tasklist_xml, tasklists_env, var_env, stop_time)
            if delay is not None and delay > 0:
                coro = run_delayed(coro, delay)
            task = asyncio.async(coro)
            task.gplmt_background = background
            task.gplmt_node = node
            self.tasks.append(task)

    def schedule_loop_counted(self, loop_xml, tasklists_env, repetitions, var_env):
        coro = self.run_loop_counted(loop_xml, tasklists_env, repetitions, var_env)
        task = asyncio.async(coro)
        task.gplmt_background = False
        task.gplmt_node = []
        self.tasks.append(task)

    def schedule_loop_until(self, loop_xml, tasklists_env, deadline, var_env):
        coro = self.run_loop_until(loop_xml, tasklists_env, deadline, var_env)
        task = asyncio.async(coro)
        task.gplmt_background = False
        task.gplmt_node = []
        self.tasks.append(task)

    def schedule_loop_listing(self, loop_xml, tasklists_env, listing, listParam, var_env):
        coro = self.run_loop_listing(loop_xml, tasklists_env, listing, listParam, var_env)
        task = asyncio.async(coro)
        task.gplmt_background = False
        task.gplmt_node = []
        self.tasks.append(task)        

    @asyncio.coroutine
    def run_loop_counted(self, loop_xml, tasklists_env, repetitions, var_env):
        nested_ec = ExecutionContext(self.testbed)
        for x in range(repetitions):
            for step in list(loop_xml):
                yield from nested_ec.run_step(step, tasklists_env, var_env)
            yield from nested_ec.join()

    @asyncio.coroutine
    def run_loop_until(self, loop_xml, tasklists_env, deadline, var_env):
        nested_ec = ExecutionContext(self.testbed)
        while time.time() < deadline:
            for step in list(loop_xml):
                yield from nested_ec.run_step(step, tasklists_env, var_env)
            yield from nested_ec.join()

    @asyncio.coroutine
    def run_loop_listing(self, loop_xml, tasklists_env, listing, listParam, var_env):
        nested_ec = ExecutionContext(self.testbed)
        
        if ":" in listing:
            rangeGiven = listing.split(":")
            if len(rangeGiven) == 2 and helper.isInt(rangeGiven[0]) and helper.isInt(rangeGiven[1]):
                loopList = range(int(rangeGiven[0]), int(rangeGiven[1])+1)
                loopList = map(str, loopList)                
            else:
                raise ExperimentSyntaxError("Invalid Range declaration '%s'" % (loop_xml.tag,))
        else:
            loopList = listing.split(" ")
        for x in loopList:
            loop_env = {}
            loop_env[listParam] = x
            composedEnv = {}
            composedEnv.update(var_env)
            composedEnv.update(loop_env)
            nested_ec.var = composedEnv
            for step in list(loop_xml):
                yield from nested_ec.run_step(step, tasklists_env, composedEnv)
            yield from nested_ec.join()


    @asyncio.coroutine
    def run_step(self, step_xml, tasklists_env, var_env={}):
        if step_xml.tag not in self._step_table:
            raise ExperimentSyntaxError("Invalid step '%s'" % (step_xml.tag,))
        step_method = self._step_table[step_xml.tag]
        yield from step_method(self, step_xml, tasklists_env, var_env)

    @asyncio.coroutine
    def _step_synchronize(self, step_xml, tasklists_env, var_env={}):
        targets = None
        targets_str = step_xml.get('targets')
        if targets_str is not None:
            targets = self.testbed._resolve_target(targets_str)
        yield from self.join(targets)

    @asyncio.coroutine
    def _step_tasklist(self, step_xml, tasklists_env, var_env={}):
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
        background = False
        bg_str = step_xml.get('background')
        if bg_str is not None and bg_str.lower() == 'true':
            background = True
        delay = get_delay_attr(step_xml, 'start')
        stop = get_delay_attr(step_xml, 'stop')
        logging.info("delay for step with tl %s is %s", tasklist_name, delay)

        composedEnv = {}
        composedEnv.update(var_env)
        composedEnv.update(helper.exportEnv(step_xml))
        
        self.schedule_tasklist(targets_def, tasklist, tasklists_env, background, delay, composedEnv, stop)

    @asyncio.coroutine
    def _step_teardown(self, step_xml, tasklists_env, var_env):
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

        composedEnv = {}
        composedEnv.update(var_env)
        composedEnv.update(helper.exportEnv(step_xml))

        self.testbed.teardowns.append((targets_def, tasklist, composedEnv))

    @asyncio.coroutine
    def _step_loop(self, step_xml, tasklists_env, var_env={}):
        num_repeat_str = step_xml.get("repeat")
        if num_repeat_str is not None:
            try:
                num_repeat = int(num_repeat_str)
            except ValueError:
                logging.error("counted loop has malformed attribute iterations (%s), skipping", num_repeat_str)
                return
            self.schedule_loop_counted(step_xml, tasklists_env, num_repeat, var_env)
            return
        duration = step_xml.get("duration")
        if duration is not None:
            deadline = time.time() + isodate.parse_duration(duration).total_seconds()
            self.schedule_loop_until(step_xml, tasklists_env, deadline, var_env)
            return
        listing = step_xml.get("list")
        listParam = step_xml.get("param")
        if listing is not None and listParam is not None:
            self.schedule_loop_listing(step_xml, tasklists_env, listing, listParam, var_env)
            return
        if listing is None and listParam is not None:
            raise Exception("missing list definition")
        if listParam is None and listing is not None:
            raise Exception("missing parameter definition")
        until = step_xml.get("until")
        if until is not None:
            deadline = parse(until)
            deadline = time.mktime(deadline.timetuple())
            self.schedule_loop_until(step_xml, tasklists_env, deadline, var_env)
            return
        raise Exception("not implemented")

    _step_table = {
            'step': _step_tasklist,
            'register-teardown': _step_teardown,
            'synchronize': _step_synchronize,
            'loop': _step_loop,
    }



class Testbed:
    def __init__(self, targets_xml, settings):
        self.batch = settings.batch
        self.ssh_cooldown = settings.ssh_cooldown
        self.logroot_dir = settings.logroot_dir
        self.nodes = {}
        self.groups = {}
        self.settings = settings
        for el in targets_xml:
            self._process_declaration(el)

        self.ec = ExecutionContext(self)

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

    @asyncio.coroutine
    def run_teardowns(self, tasklists_env):
        try:
            for target, tasklist, teardown_env in self.teardowns:
                # run teardowns in the root execution context of
                # the testbed
                self.ec.schedule_tasklist(target, tasklist, tasklists_env, background=False, var_env=teardown_env)
                yield from self.join()
        except ExperimentExecutionError as e:
            logging.error("Error during teardown:  %s" % (e.message))

    def ssh_release(self):
        # Note that the cooldown lock will
        # be released by a timer.
        self.ssh_parallel_sema.release()

    @asyncio.coroutine
    def cancel_pending(self):
        yield from self.ec.cancel_pending()

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
            # XXX: pass environment of group down to the peers of the group
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

    @asyncio.coroutine
    def run_step(self, step_xml, tasklists_env, var_env={}):
        yield from self.ec.run_step(step_xml, tasklists_env, {})

    def join(self, targets=None):
        yield from self.ec.join(targets)


def find_text(node, query):
    res = node.find(query)
    if res is None:
        return None
    return res.text


def get_delay_attr(node, prefix):
    t_relative = node.get(prefix + '_relative')
    if t_relative is not None:
        return isodate.parse_duration(t_relative).total_seconds()
    t_absolute = node.get(prefix + '_absolute')
    if t_absolute is not None:
        st = parse(t_absolute)
        st = time.mktime(st.timetuple())
        diff = st - time.time()
        return diff
    return None


class ExpectSuccessPolicy:
    def __init__(self, command):
        self.command = command

    def check_status(self, status):
        if status != 0:
            raise ExperimentExecutionError("Unexpected status '%s'" % (status,))


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
                # XXX: also include tasklist name
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
        self._env = helper.exportEnv(node_xml)

    @property
    def env(self):
        return self._env.copy()


    @asyncio.coroutine
    def _run_list(self, tasklist_xml, testbed, tasklists_env, var_env):
        for task_xml in tasklist_xml:
            yield from self._run_task(task_xml, testbed, tasklists_env, var_env)

    @asyncio.coroutine
    def run_cleanup(self, tasklist_xml, tasklists_env, var_env):
        cleanup_task = None
        cleanup_name = tasklist_xml.get('cleanup')
        if cleanup_name is not None:
            cleanup_task = tasklists_env.get(cleanup_name)
            if cleanup_task is None:
                raise ExperimentSyntaxError("cleanup task %s not found\n" % (cleanup_name,))
        if cleanup_task is None:
            return
        #coro = self._run_list(cleanup_task, self.testbed, tasklists_env, var_env)
        coro = self.run_tasklist(cleanup_task, tasklists_env, var_env, None)
        try:
            yield from asyncio.async(coro)
        except asyncio.TimeoutError:
            # XXX: be more verbose!
            logging.warning(
                    "Cleanup tasklist %s on node %s timed out",
                    cleanup_name,
                    self.name)
        except StopExperimentException as e:
            logging.warning(
                    "Cleanup tasklist %s on node %s stopped (%s)",
                    cleanup_name,
                    self.name,
                    e.scope)
        except ExperimentExecutionError as e:
            logging.warning(
                    "Cleanup tasklist %s on node %s failed (%s)",
                    cleanup_name,
                    self.name,
                    e.message)


    @asyncio.coroutine
    def run_tasklist(self, tasklist_xml, tasklists_env, var_env, stop_time):
        list_name = tasklist_xml.get('name', '(unnamed)')
        logging.info("running tasklist '%s'", list_name)
        # actual tasks, with declarations stripped
        error_policy = tasklist_xml.get('on-error')
        if error_policy is None:
            error_policy = 'stop-tasklist'
        timeout_str = tasklist_xml.get('timeout')
        timeout = stop_time
        if timeout_str is not None:
            timeout_tl = isodate.parse_duration(timeout_str).total_seconds()
            if timeout is None:
                timeout = timeout_tl
            else:
                times = [timeout_tl, timeout]
                timeout = min(times)

        coro = self._run_list(tasklist_xml, self.testbed, tasklists_env, var_env)
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
            # XXX: cleanup!
        except StopExperimentException as e:
            if e.scope == 'stop-experiment':
                raise
            # otherwise, we ignore the exception
        except ExperimentExecutionError as e:
            logging.error("Tasklist execution (%s on %s) raised exception (%s)", list_name, self.name, e.message)
            if error_policy in ('stop-experiment', 'stop-step', 'stop-tasklist'):
                yield from self.run_cleanup(tasklist_xml, tasklists_env, var_env)
                raise StopExperimentException(error_policy)
            else:
                raise ExperimentSyntaxError("Unexpected error policy '%s'" % (error_policy,))
        yield from self.run_cleanup(tasklist_xml, tasklists_env, var_env)

    @asyncio.coroutine
    def _run_task_run(self, task_xml, var_env):
        pol = RunTaskPolicy(self, task_xml)

        with pol.open_stdout() as stdout, pol.open_stderr() as stderr:
            yield from self.execute(pol, stdout, stderr, var_env)

    @asyncio.coroutine
    def _run_task(self, task_xml, testbed, tasklists_env, var_env):
        name = task_xml.get('name', '(unnamed-task)')
        if task_xml.get('enabled', 'true').lower() == 'false':
            logging.info("Task %s disabled", name)
            return
        if task_xml.tag == 'run':
            yield from self._run_task_run(task_xml, var_env)
            return
        if task_xml.tag == 'get':
            source = find_text(task_xml, 'source')
            destination = find_text(task_xml, 'destination')
            # XXX: Just replace all environment variables
            source = source.replace("$GPLMT_TARGET", self.name)
            destination = destination.replace("$GPLMT_TARGET", self.name)
            yield from self.get(source, destination)
            return
        if task_xml.tag == 'put':
            source = find_text(task_xml, 'source')
            destination = find_text(task_xml, 'destination')
            kp_str = task_xml.attrib.get("keep")
            # XXX: Just replace all environment variables
            source = source.replace("$GPLMT_TARGET", self.name)
            destination = destination.replace("$GPLMT_TARGET", self.name)

            if kp_str is None or kp_str.lower() == 'false':
                #Check for invalid characters, whitelisting
                valid = re.compile("^([\.a-zA-Z][\-\.a-zA-Z]+)$")
                if valid.match(destination):
                    composedEnv = []
                    tasklist = lxml.etree.Element("tasklist", name="cleanup")#on error?
                    child1 = lxml.etree.SubElement(tasklist, "seq")
                    child2 = lxml.etree.SubElement(child1, "run", name="_anon2")
                    child2.text = ("rm " + destination)
                    self.testbed.teardowns.append((self.name, tasklist, composedEnv))
                else:
                    logging.warning("no automated removal, invalid characters in destination: %s", destination)

            yield from self.put(source, destination)
            return
        if task_xml.tag in ('sequence', 'seq'):
            for child_task in task_xml:
                yield from self._run_task(child_task, testbed, tasklists_env, var_env)
            return
        if task_xml.tag == 'fail':
            raise ExperimentExecutionError("user-requested fail")
        if task_xml.tag == 'call':
            tl = task_xml.get('tasklist')
            if tl is None:
                raise ExperimentSyntaxError("no tasklist name in 'call'")
            tasklist_xml = tasklists_env.get(tl)
            if tasklist_xml is None:
                raise ExperimentSyntaxError("Tasklist '%s' not defined" % (tl,))
            yield from self.run_tasklist(tasklist_xml, tasklists_env, var_env)
        if task_xml.tag in ('par', 'parallel'):
            parallel_tasks = []
            for child_task in task_xml:
                coro = self._run_task(child_task, testbed, tasklists_env, var_env)
                task = asyncio.async(coro)
                parallel_tasks.append(task)
            done, pending = yield from asyncio.wait(parallel_tasks)
            for task in done:
                task.result()
            return


class LocalNode(Node):
    def __init__(self, node_xml, testbed):
        super().__init__(node_xml, testbed)

    @asyncio.coroutine
    def execute(self, pol, stderr, stdout, var_env = {}):
        logging.info("Locally executing command '%s'", pol.command)
        env = self.env
        env.update(var_env)
        proc = yield from asyncio.create_subprocess_shell(
                pol.command, stdout=stdout, stderr=stderr, env=env, start_new_session=True)
        try:
            ret = yield from proc.wait()
            pol.check_status(ret)
        except asyncio.CancelledError as e:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                logging.info("Local command terminated due to timeout or stop_time.")
            

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
        # XXX: maybe check that the master process is actually running
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
        # FIXME: other directory (e.g. ~/.config/gplmt)?
        p = "~/.ssh/gplmt-%(host)s@%(user)s:%(port)s" % {
            "host": self.host, "user": self.user, "port": self.port
        }
        return os.path.expanduser(p)

    @asyncio.coroutine
    def execute(self, pol, stdout=None, stderr=None, var_env = {}):
        yield from self.testbed.ssh_acquire()

        cmd = pol.command

        logging.info("Executing command '%s' on '%s'", pol.command, self.name)

        # Add code to command to set environment variables
        # on the target host.
        env = self.env
        env.update(var_env)

        if env:
            cmd = helper.wrap_env(cmd, env)

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
        logging.info("waiting ...")
        try:
            ret = yield from proc.wait()
            logging.info("SSH command terminated with status %s", ret)
            pol.check_status(ret)
        except asyncio.CancelledError as e:
            proc.terminate()
            logging.info("SSH command terminated due to timeout or stop_time.")
        finally:
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
        pol = ExpectSuccessPolicy("mkdir -p $(dirname $(readlink -fm %s))" % (shlex.quote(destination)))
        yield from self.execute(pol)
        yield from self.scp_copy(scp_source, scp_destination)

    @asyncio.coroutine
    def get(self, source, destination):
        scp_source = '%s:%s' % (self.target, source)
        if os.path.isabs(source):
            scp_destination = destination
        else:
            scp_destination = './' + destination
        # Ensure that target directory exists
        os.makedirs(os.path.dirname(os.path.realpath(destination)), exist_ok=True)
        yield from self.scp_copy(scp_source, scp_destination)


def establish_names(el):
    """Make sure that should have a name has a unique name"""
    counter = 0
    for element in el.iter():
        if element.tag not in ('run',):
            continue
        if element.get('name') is None:
            # XXX: maybe we could use filename/line?
            # We do have .sourceline available sometimes
            element.set('name', '_anon' + str(counter))
            counter += 1
    # XXX: check for uniqueness


def augment_experiment(experiment, extension, prefix=None):
    # XXX: prefixing is not complete,
    # all references to tasklists / targets within the
    # extension experiment should also be prefixed.

    res = experiment.xpath('/experiment/targets')
    if not res:
        raise ExperimentSyntaxError("Element 'targets' missing in experiment")
    targets = res[0]
    res = extension.xpath('/experiment/targets')
    if not res:
        raise ExperimentSyntaxError("Element 'targets' missing in experiment")
    ext_targets = res[0]
    if prefix is not None:
        for t in ext_targets:
            t.set('name', "{0}.{1}".format(prefix, t.get('name', '_unknown')))
    targets.extend(list(ext_targets))

    del targets, ext_targets

    res = experiment.xpath('/experiment/tasklists')
    if not res:
        raise ExperimentSyntaxError("Element 'tasklists' missing in experiment")
    tasklists = res[0]
    res = extension.xpath('/experiment/tasklists')
    if not res:
        raise ExperimentSyntaxError("Element 'tasklists' missing in experiment")
    ext_tasklists = res[0]
    if prefix is not None:
        for t in ext_tasklists:
            t.set('name', "{0}.{1}".format(prefix, t.get('name', '_unknown')))
    tasklists.extend(list(ext_tasklists))

    if extension.find('/experiment/steps'):
        logging.warn("Extension tasklist has 'steps'.  These steps will not be executed")



def process_includes(experiment_xml, parent_filename, env=None, memo=None):
    includes = experiment_xml.xpath('/experiment/include')
    for el in includes:
        filename = el.get('file')
        if filename is None:
            raise ExperimentSyntaxError("Attribute 'file' missing in include")
        # XXX: Implement defaulting, shell style?
        filename = os.path.expandvars(filename)
        # Search relative paths relative to parent document
        if not os.path.isabs(filename):
            parent_dir = os.path.dirname(os.path.realpath(parent_filename))
            filename = os.path.join(parent_dir, filename)
        filename = os.path.realpath(filename)
        if memo is not None and filename in memo:
            raise ExperimentSyntaxError("recursive include detected")
        xml_parser = lxml.etree.XMLParser(remove_blank_text=True)
        # XXX: we only try one filename, but we may want to specify include
        # locations, like compilers do.
        extension_xml = lxml.etree.parse(filename, parser=xml_parser)
        # XXX: Maybe we want to keep the comments?
        # XXX: If that is then case, our processing logic needs to be more careful.
        lxml.etree.strip_elements(extension_xml, [lxml.etree.Comment])
        # XXX: some validation wouldn't hurt here
        new_memo = {filename}
        if memo is not None:
            new_memo.update(memo)
        establish_names(extension_xml)
        process_includes(extension_xml, filename, memo=new_memo)
        prefix = el.get('prefix')
        augment_experiment(experiment_xml, extension_xml, prefix)
