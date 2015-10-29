Frequently Asked Questions
==========================

My commands on the remote server are not executed
-------------------------------------------------

Two things commonly go wrong here:

1. There is a stale SSH master connection in `~/.ssh/`.  Try deleting it.
2. You did not add your key to the ssh agent.  Use `ssh-add`.

GPLMT is giving me an incomprehensible syntax error
---------------------------------------------------

Try checking the experiment definition file against the formal grammar manually.

This can be done with

.. code-block:: bash

  $ xmllint --relaxng contrib/gplmt.rng --noout my_experiment.xml


