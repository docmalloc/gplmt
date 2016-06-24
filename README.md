What is GPLMT?
===============

Conducting experiments in federated, distributed, and heterogeneous testbeds is a challenging task for researchers. Researchers have to take care of the whole experiment life cycle, ensure the reproducibility of each run, and the comparability of the results. We present GPLMT, a flexible and lightweight framework for managing testbeds and the experiment life cycle. GPLMT provides an intuitive way to formalize experiments. The resulting experiment description is portable across varying experimentation platforms. GPLMT enables researchers to manage and control networked testbeds and resources, and conduct experiments on large-scale, heterogeneous, and distributed testbeds. We state the requirements and the design of GPLMT, describe the challenges of developing and using such a tool, and present selected user studies along with their experience of using GPLMT in varying scenarios.

Read more: http://arxiv.org/abs/1601.03984

Documentation:
==============

The latest version of the documentation is available from 
[readthedocs](http://gplmt.readthedocs.org/en/latest/).


Features:
=============

- Support for public key and SSH agent authentication
- PlanetLab API integration to retrieve node list
- SFTPand SCP support to copy data from and to nodes
- Extensible task list
- Task list validation against XML Schema
- Extensible logging functionality

Content
=============

gplmt/
source code

contrib/
schema for experiment definition language and other miscellaneous files

docs/
documentation file, e.g. user guide

examples/
example experiment definitions


Dependencies:
=============

These are the direct dependencies for running gplmt:

- Python >= 3.4
- lxml >= 3.4.4
- isodate >= 0.5.4

The version numbers represent the versions we used to develop gplmt.

Coding Style:
=============

PEP8 with 120 character limit.

    pep8 --max-line-length=120


How to install?
===============

Python
--------

Please check your OS documention or http://www.python.org/ how to setup
Python

To install the required python modules, we recommend to use the pip 
installer:

http://www.pip-installer.org/en/latest/index.html

lxml >= 3.4.4
--------

On GNU/Linux use: sudo pip3 install lxml
Or check https://pypi.python.org/pypi/lxml

isodate >= 0.5.4
--------

On GNU/Linux use: sudo pip3 install isodate
Or check https://pypi.python.org/pypi/isodate

