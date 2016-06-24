Introduction
============

What is GPLMT?
--------------

GPLMT is an interpreter for experiment definitions.  An experiment
definition is an XML file that formally describes how tasks (such as executing commands
or transfering files) should be executed on nodes in a testbed.

The language of experiment definitions is easy to learn, and makes
it possible to design and execute repeatable, modular experiments without
the need to write boilerplate code.

Experiments are controlled centerally by one host that executes an experiment
definition, called the GPLMT Execution Host.

GPLMT supports testbeds with nodes that are accessible via
the SSH protocol and offer a POSIX-compliant shell.


Installing GPLMT
----------------

TODO: package should use standard python packaging


Using GPLMT
-----------

Experiments are run with the `gplmt-light.py` program.  The experiment
description file that is to be executed is passed as a filename on the `gplmt-light.py` command line.

For the following experiment description (which can be found
in the GPLMT distribution alongside many other examples in `/examples/hello_world.xml`

.. code-block:: xml
  :name: hello_world
  :caption: hello_world.xml

  <?xml version="1.0" encoding="utf-8"?>
  <experiment>
    <description>Hello World in GPLMT</description>

    <targets>
      <target name="local" type="local" />
    </targets>

    <tasklists>
      <tasklist name="hello-world">
	<run>echo Hello World</run>
      </tasklist>
    </tasklists>

    <steps>
      <step tasklist="hello-world" targets="local" />
    </steps>
  </experiment>

running

.. code-block:: bash

  gplmt-light.py hello_world.xml


should print *Hello World* on your terminal, among many log messages.

Refer to the output of `gplmt-light.py --help` or the reference manual
for optional parameters.


The Anatomy of Experiments
--------------------------

Every experiment definition consists of three mayor parts:

1. Target definitions.  A target is a set of one or more hosts in a testbed
   that are accessible via the SSH protocol and run a POSIX-compliant shell.
   Targets must have a name that is unique within one experiment definition.
2. Tasklist definitions.  A tasklist describes the execution of tasks on one
   host of the testbed.  The tasklist definition is independent from the target
   that it will run on.  Primitive tasks are the execution of arbitrary shell
   commands and file transfers from and to the GPLMT Execution Host (called
   `put` and `get` respectively).  Primitive tasks can be composed in parallel
   or in sequence inside tasklists.
3. The execution plan (also called the `steps` of the experiment)
   brings tasklists and targets together by specifying which tasklists
   should be run on which targets as part of the experiment.
   Per default, all steps of the execution plan are executed in parallel,
   unless the user specifies synchronization points to sequence execution.

.. There should be more on execution plans ...


Additionally, an experiment definition can include the targets and tasklists of other
experiment definitions.  The names of targets and tasklists included from
another experiment definition are prefixed with a user-defined name,
so that names stay unique within an experiment.

Experiment definitions do not need to have a unique name, since experiments
are identified by their file name.  It is convenient though to include a short
textual description of each experiment's purpose in the experiment definition.

Defining Targets
----------------

Targets are defined in the mandatory `targets` element of the experiment description:

.. code-block:: xml

  <?xml version="1.0" encoding="utf-8"?>
  <experiment>
    <!-- ... -->
    <targets>
      <target name="my-target" type="...">
        <!-- Depending on the type, different elements go here -->
      </target>
      <!-- ... -->
    </targets>
    <!-- ... -->
  </experiment>

The name of a target must be unique within the experiment.


Local Targets
~~~~~~~~~~~~~

If the type of the target is given as `local`, the target is the GPLMT Exexution Host.
Even if there is always only one GPLMT Execution Host, multiple local targets can
be defined.

Duplicate local targets are treated seperately when it comes to synchronization statements.
Also, different environment parameters (See *Exporting Variables*) can be defined
for different local targets.

SSH Targets
~~~~~~~~~~~

SSH targets are remote hosts that are controllable via the SSH protocol:


.. code-block:: xml

  <target name="my-ssh-target" type="ssh">
    <user>exampleuser</user>
    <host>node1.example.com</host>
    <!-- The port is optional and defaults to 22 -->
    <port>12345</port>
  </target>

TODO: Describe advanced options.

Planetlab Targets
~~~~~~~~~~~~~~~~~

Planetlab targets make it possible to schedule tasks on a planetlab slice.


Group Targets
~~~~~~~~~~~~~~~~~

Group targets give a name to a set of other targets.  The members
of a group can be target definitions or target references.


.. code-block:: xml

  <target name="my-group-target" type="group">
    <target name="mylocal" type="local" />
    <target ref="my-ssh-target" />
  </target>

Exporting Variables
~~~~~~~~~~~~~~~~~~~

Similarly to how shell variables can be passed to child processes
if they are marked with `export`, GPLMT can export variables to commands
that are run.

One mechanism to pass variables is to define them per-target.

.. code-block:: xml

  <target name="my-export-target" type="...">
    <export-env var="V1" />
    <export-env var="V2" value="quux" />
    <!-- ... type-specific elements -->
  </target>

In the example above, when commands are executed on `my-export-target`,
the environment will contain `V1` and `V2`, where `V1` is set
to the value of `V` on the GPLMT execution host, and `V2` is set to the constant `"foo"`.


Defining Tasklists
------------------

Tasklists must have a unique name, just as targets.

A Tasklist consists of a a composition element (`seq` or `par`).

A composition element consists of a primitive task (`run`, `put`, `get`) or further composition elements.


Running Commands
~~~~~~~~~~~~~~~~

Commands are interpreted by a shell on the target host.

Per default, the termination of a command is always interpreted as success,
regarless of the status of the process that was executed.  With the `expected-status`
attribute, it is possible trigger an error if the command exits with a different status.

.. code-block:: xml
  
  <run expected-status="0">some-program --with-argument=$FOO</run>



File Transfers
~~~~~~~~~~~~~~

.. code-block:: xml
  
  <put source="local-filename" destination="remote-filename" />

.. code-block:: xml
  
  <get source="remote-filename" destination="local-filename" />

All parent directories will be created if they do not exist yet.

Calling other tasklists
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: xml
  
  <call tasklist="some-tasklist" />

Parallel and Sequential Composition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: xml
  
  <par>
    <!-- Sequence of other tasks -->
  </par>

.. code-block:: xml
  
  <seq>
    <!-- Sequence of other tasks -->
  </seq>

Cleanups and Error Handling
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tasklists can specify other tasklists as a cleanup tasklist. Cleanup tasklists
are always executed, even if the execution of another tasklist fails.

What happens when a tasklist fails can be changed by specifying the `on-error` attribute.
The possible values are:

* `stop-tasklist`.  This is the default.  Execution of the current tasklist will stop.
  If the current tasklist was executed with a `call` task, the caller tasklist will continue execution.
* `stop-experiment`.  The whole experiment will be stopped.
* `stop-step`.  The whole step will be aborted.  The difference to `stop-tasklist` is that
  all callers of the tasklist are stopped as well.

Defining the Execution Plan
---------------------------

An execution plan is the combination of targets and tasklists within the step definition.

.. code-block:: xml

  <steps>
    <step tasklist="hello-world" targets="local" />
  </steps>

The execution of tasklist `hello-world` is bound to target `local`.

Steps can be organized to be executed in parallel by simply writing them one after another.

.. code-block:: xml

  <steps>
    <step tasklist="hello-world" targets="local" />
    <!-- and the same in parallel -->
    <step tasklist="hello-world" targets="local" />
  </steps>

A sequential execution can be enforced by using `synchronized` (see later).
Further, `loops` are supported, as well as `background` and `teardown` steps.

Synchronization
~~~~~~~~~~~~~~~

Looping
~~~~~~~

Background Steps
~~~~~~~~~~~~~~~~

Teardown Steps
~~~~~~~~~~~~~~

