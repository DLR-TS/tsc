import os
import subprocess
import tscdefs

subprocess.call(tscdefs.get_python_tool("install_scenario_templates.py") + ['--clean', '--suburb-taz', '',  '-v', '-p', os.path.join(tscdefs.tscRoot, 'data')])
