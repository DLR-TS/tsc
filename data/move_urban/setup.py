#!/usr/bin/env python
from __future__ import print_function
import os, sys, shutil, subprocess, glob
sys.path += [os.path.join(os.environ["SUMO_HOME"], 'tools')]
import sumolib

here = sys.argv[2]
templates = os.path.dirname(here)
prefix = os.path.join(here, "spandau")
boundary = "13.1907,52.529,13.3053,52.566"
output_net = prefix + ".net.xml"

copies = ["berlin_net/vtypes.xml", "berlin_net/net.net.xml.gz",
          "berlin_net/landmarks.csv.gz", "berlin_net/bidi.taz.xml",
          "berlin_net/suburb.taz.xml", "berlin_net/districts.taz.xml",
          "berlin_net/pt*.xml"]

# copy selected files from berlin scenario
for source in copies:
    for sourcePath in glob.glob(os.path.join(templates, source)):
        if os.path.exists(sourcePath):
            sourceFile = os.path.basename(sourcePath)
            print("copying %s" % sourceFile)
            shutil.copyfile(sourcePath, os.path.join(here, sourceFile))
        else:
            print("skipping non existent %s" % sourceFile)

# generate the new net based on the boundaries
subprocess.call([sumolib.checkBinary("netconvert"), "-s", os.path.join(here, "net.net.xml.gz"),
                 "--keep-edges.in-geo-boundary", boundary, "--no-internal-links", "false",
                 "--crossings.guess", "-o", output_net])

# filter the relevant information from the copied files
edges = set()
with open(prefix + ".txt", "w") as edge_out:
    for edge in sumolib.output.parse_fast(output_net, 'edge', ['id']):
        if edge.id[0] != ':':
            edge_out.write(edge.id + "\n")
            edges.add(edge.id)

with open(prefix + '_bidi.taz.xml', 'w') as bidi:
    bidi.write('<tazs>\n')
    for taz in sumolib.output.parse(os.path.join(here, 'bidi.taz.xml'), 'taz'):
        if taz.id in edges:
            taz.edges = " ".join([e for e in taz.edges.split() if e in edges])
            bidi.write(taz.toXML("    "))
    bidi.write('</tazs>\n')

with open(prefix + '_vtypes.xml', 'w') as vtypeOut:
    vtypeOut.write('<routes>\n')
    for vType in sumolib.output.parse(os.path.join(here, 'vtypes.xml'), 'vType'):
        vType.speedDev = 0.1
        vtypeOut.write(vType.toXML("    "))
    vtypeOut.write('</routes>\n')
