import os
import subprocess
import tscdefs

os.chdir("data")
subprocess.call(tscdefs.get_python_tool("install_scenario_templates.py") + ['--clean', '-v', '-p', os.path.join(tscdefs.tscRoot, "data")])