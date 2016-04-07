
import os
import lxml.etree
import shlex

from error import ExperimentSyntaxError

def exportEnv(structure):
    envVar = {}
    for env_xml in structure.findall('export-env'):
        name = env_xml.get('var')
        if name is None:
            raise ExperimentSyntaxError("export-env misses 'var' attribute")
        value = env_xml.get('value')
        if value is None:
            v = os.environ.get(name)
            if v is None:
                raise ExperimentSyntaxError("variable '%s' not found in environment of GPLMT control host" % (name,))
            value = v
        envVar[name] = value

    return envVar

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

def isInt(value):
  try:
    int(value)
    return True
  except ValueError:
    return False
