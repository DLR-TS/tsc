#!/usr/bin/env python
from __future__ import print_function
import os, sys, shutil, glob

here = sys.argv[2]
templates = os.path.dirname(here)

# copy all files from mitte_net scenario
for source in glob.glob(os.path.join(templates, "mitte_net", "*")):
    print("copying", os.path.basename(source))
    shutil.copyfile(source, os.path.join(here, os.path.basename(source)))
