from __future__ import print_function
import os
import sys

python = os.environ.get("PYTHON", "python")
sys.path.append(os.path.join(os.environ["SUMO_HOME"], 'tools'))
tscRoot = os.environ.get("TSC_HOME", os.path.join(os.environ["SIP_HOME"]))
sys.path.append(tscRoot)
tscData = os.environ.get("TSC_DATA", os.path.join(os.environ["SIP_HOME"]))
testServer = os.path.join(tscData, "test_server.tsccfg")

def get_python_tool(rel_path, config=testServer):
    call = '"' + python + '" "' + os.path.join(tscRoot, rel_path) + '"'
    if config:
        return call + ' -c "%s"' % config
    return call
