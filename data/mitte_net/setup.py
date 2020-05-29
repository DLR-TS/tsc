#!/usr/bin/env python
from __future__ import print_function
import os, sys, shutil, subprocess
sys.path += [os.path.join(os.environ["SUMO_HOME"], 'tools')]
import sumolib

here = sys.argv[2]
templates = os.path.dirname(here)
prefix = os.path.join(here, "mitte")
boundary = "13.374361,52.506304,13.474692,52.530199"
output_net = os.path.join(here, "mitte.net.xml")

copies = ["berlin_net/vtypes.xml", "berlin_net/net.net.xml",
          "berlin_net/landmarks.csv", "berlin_net/bidi.taz.xml",
          "berlin_net/suburb.taz.xml", "berlin_net/districts.taz.xml"]

# copy selected files from berlin scenario
for source in copies:
    sourcePath = os.path.join(templates, source)
    if os.path.exists(sourcePath):
        print("copying %s" % source)
        shutil.copyfile(sourcePath, os.path.join(here, os.path.basename(source)))
    else:
        print("skipping non existent %s" % source)

# generate the new net based on the boundaries
subprocess.call([sumolib.checkBinary("netconvert"), "-s", os.path.join(here, "net.net.xml"),
                     "--keep-edges.in-geo-boundary", boundary,
                     "-o", output_net])
           
# filtered the relevant information from the copied files
edges = set()
with open(os.path.join(here, "mitte.txt"), "w") as mitte_out:
    for edge in sumolib.output.parse_fast(os.path.join(here, "mitte.net.xml"), 'edge', ['id']):
        if edge.id[0] != ':':
            mitte_out.write(edge.id + "\n")
            edges.add(edge.id)

with open(os.path.join(here, 'mitte_bidi.taz.xml'), 'w') as bidi:
    bidi.write('<tazs>\n')
    for taz in sumolib.output.parse(os.path.join(here, 'bidi.taz.xml'), 'taz'):
        if taz.id in edges:
            taz.edges = " ".join([e for e in taz.edges.split() if e in edges])
            bidi.write(taz.toXML("    "))
    bidi.write('</tazs>\n')

with open(os.path.join(here, 'mitte_vtypes.xml'), 'w') as vtypeOut:
    vtypeOut.write('<routes>\n')
    for vType in sumolib.output.parse(os.path.join(here, 'vtypes.xml'), 'vType'):
        vType.speedDev = 0.1
        vtypeOut.write(vType.toXML("    "))
    vtypeOut.write('</routes>\n')