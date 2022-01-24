#!/usr/bin/env python
#import seaborn as sns
#import pandas as pd
import pyproj # Import the pyproj module 
import sys
sys.path.append("d:\\sumo\\tools")
import sumolib
import utm


class Trajectory(object):
    """defines trajectory as data containter for points, speeds, etc. Additionally, some operations with trajectories
    are implemented as well."""
    
    def __init__(self, objectID, lat, lon):
        """constructor"""
        self._id = objectID                       # ID
        self._latList = [lat]                      # lat coordinates
        self._lonList = [lon]                      # lon coordinates
        self._duration= -1
        self._dists= []
        
    def setID(self, newID):
        self._id= newID
    
    def setDuration(self, d):
        self._duration= d
    
        
    
    def addlatPosition(self, x):
        self._latList.append(x)

    def addlonPosition(self, y):
        self._lonList.append(y)  
    

    def getID(self):
        return self._id      
        
    def getDuration(self):
        return self._duration
     
    def getLat(self):
        return self._latList
    
    def getLon(self):
        return self._lonList    

def geo2edge(net, lat, lon): 
    radius = 20.
    x, y = net.convertLonLat2XY(lon, lat)
    edges = net.getNeighboringEdges(x, y, radius)
    print(edges)
    # pick the closest edge
    closestEdge= False
    if len(edges) > 0:
        #distancesAndEdges = sorted([(dist, edge) for edge, dist in edges])
        #dist, closestEdge = distancesAndEdges[0]
        closestEdge= edges[0][0].getID()
        print(closestEdge)
    return closestEdge
    
    
def generatePOIs(filename, trajectories):
    f = open(filename, 'w') 
    f.write("<additional xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:noNamespaceSchemaLocation=\"http://sumo.dlr.de/xsd/additional_file.xsd\">\n")
    f.write("<location convBoundary=\"1215.37,480.71,36294.87,30350.79\" origBoundary=\"9.866920,52.146541,10.806219,52.446520\" projParameter=\"+proj=utm +zone=33 +ellps=WGS84 +datum=WGS84 +units=m +no_defs\"/>\n")
    i= 0
    for k in trajectories.keys():
        t=trajectories[k]
        position= 0
        f.write('<poi id=\"' + str(t.getID())+ "_" +str(i) +'\" color=\"128,0,0\" layer=\"-1.00\" lat=\"' + str(t.getLat()[position]) + '\" lon=\"' + str(t.getLon()[position])+'\"/>\n')
        position +=1
        f.write('<poi id=\"' + str(t.getID())+ "_" +str(i) +'end\" color=\"128,0,128\" layer=\"-1.00\" lat=\"' + str(t.getLat()[position]) + '\" lon=\"' + str(t.getLon()[position])+'\"/>\n')
        i+= 1
    f.write("</additional>")
    f.close()
    
def writeTrips(filename, trajectories): 
    #i=0
    #print(len(trajectories))
    for k in trajectories.keys():
        #i+=1
        #if t.getID() == "9599_2016-07-11_112725":
        #print(len(t.getLat()))
        f = open( "trips\\" +trajectories[k].getID()+ "_" + filename, 'w')
        f.write("<additional xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:noNamespaceSchemaLocation=\"http://sumo.dlr.de/xsd/additional_file.xsd\">\n")
        f.write("<location convBoundary=\"1215.37,480.71,36294.87,30350.79\" origBoundary=\"9.866920,52.146541,10.806219,52.446520\" projParameter=\"+proj=utm +zone=33 +ellps=WGS84 +datum=WGS84 +units=m +no_defs\"/>")
        for i in range(len(trajectories[k].getLat())):
            f.write('<poi id=\"' + str(trajectories[k].getID())+ str(i) +'\" color=\"0,0,128\" layer=\"-1.00\" lat=\"' + str(trajectories[k].getLat()[i]) + '\" lon=\"' + str(trajectories[k].getLon()[i])+'\"/>\n')    
        f.write("</additional>")
        f.close()


def writeRouteFile(filename, trajectories):
    f = open(filename, 'w') 
    f.write("<routes>\n")
    f.write("    <vType id=\"type1\" accel=\"0.8\" decel=\"4.5\" sigma=\"0.5\" length=\"5\" maxSpeed=\"70\"/>\n")
    for k in trajectories.keys():
        t= trajectories[k]
        if len(t.getLat()) > 1:
            f.write("    <vehicle id=\""+k + "\" type=\"type1\" depart=\"0\" color=\"1,0,0\">\n")
            edges=[]
            stoplist= []
            for i in range(len(t.getLat())):
                edge= geo2edge(net, t.getLat()[i], t.getLon()[i])
                print(edge)
                if edge:
                    edges.append(edge)
            if len(edges) > 0:
                f.write("      <route edges=\"")
                oldEdge= ""
                for e in edges:
                    if e== oldEdge:
                        stoplist.append(e)
                    else:
                        oldEdge= e
                        f.write(str(e) + " ")
                f.write("\"/>\n")
                #f.write("      <stop lane=\"end_0\" endPos=\"10\" until=\"50\"/>\n")
            f.write("    </vehicle>\n")
    f.write("</routes>\n")
    print(edges)
    f.close()
    
def writeTrajectories(filename, trajectories):
    f = open(filename, 'w') 
    print(len(trajectories))
    for t in trajectories: 
        for i in range(len(t.getLat())):
            f.write("%s;%s;\n" %(t.getLat()[i], t.getLon()[i]))
            #print(i)
    f.close()
    
def writeTraces(filename, trajectories):
    f = open(filename, 'w') 
    print(len(trajectories))
    for k in trajectories.keys(): 
        f.write("%s:" %(trajectories[k].getID()))
        for i in range(len(trajectories[k].getLat())):
            f.write("%s,%s " %( trajectories[k].getLon()[i], trajectories[k].getLat()[i]))
            #print(i)
        f.write("\n")
    f.close()    
    
# Define a filename.
filename = "tourLegsCharacteristics.csv" #"single_test.txt"# 
#filename = "tourCharacteristics.csv" #"single_test.txt"#
ofilename= "tour.xml"
input= open(filename, 'r')
#skip first line
input.readline()
# Show the file contents line by line.
# We added the comma to print single newlines and not double newlines.
# This is because the lines contain the newline character '\n'.
edges= []

net = sumolib.net.readNet('mitte_net_withoutrail4.net.xml')
#net = sumolib.net.readNet('pre_net.net.xml.gz')
t= {}
trajectoryIDs= []
    
while True:
    data=str(input.readline())
    if not data:
        break

    data=data.split(';')
    id= data[0]
    #start = data[5].split(':')

    startx= float(data[5].replace(',', '.'))# legs 5 +6 
    starty= float(data[6].replace(',', '.'))
    
    lat, lon =utm.to_latlon(startx, starty, 33, 'U')
    id= data[3]
    if id in trajectoryIDs:
        #print("old")
        pass
        
    else:
        trajectory= Trajectory(id, lat,lon)
        trajectoryIDs.append(id)
        #print(id)
    #print(lat, lon)
    #print(startx, starty)
    #startx= float((start[0][2:]).replace(',', '.'))
    #starty= float((start[1][2:]).replace(',', '.'))
    edge= geo2edge(net, lat, lon)
    if edge:
        edges.append(edge)#startx, starty))
    #lat, lon= pyproj.transform(gk4, wgs84, startx, starty) 
    #end= data[7]
    #print(startx, starty)
    #print(lat, lon)
    #sumolib.route.mapTrace()
    #p = pyproj.Proj(init='EPSG:2398') 
    #lon, lat = p(startx, starty, inverse=True)
    #print(lat, lon)
    #end = data[8].split(':')
    #print(end)
    endx= float(data[8].replace(',', '.'))
    endy= float(data[9].replace(',', '.'))
    lat, lon =utm.to_latlon(endx, endy, 33, 'U')
    trajectory.addlatPosition(lat)
    trajectory.addlonPosition(lon)
    t[id]= trajectory

input.close()
#writeTrajectories("trajectories.csv",t)
writeTraces("traces.txt", t)
writeRouteFile("route.xml", t)



print(len(t))
writeTrips("poi.xml", t)
generatePOIs("alltrips.xml", t)