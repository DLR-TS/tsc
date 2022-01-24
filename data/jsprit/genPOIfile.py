from datetime import datetime
import utm
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.path as path
import os, sys
import numpy as np
#import mpu

class Trajectory(object):
    """defines trajectory as data containter for points, speeds, etc. Additionally, some operations with trajectories
    are implemented as well."""
    
    def __init__(self, objectID, times, lat, lon):
        """constructor"""
        self._id = objectID                       # ID
        self._tsList = times                      # time stamps
        self._latList = lat                      # lat coordinates
        self._lonList = lon                      # lon coordinates
        self._duration= -1
        self._dists= []
        self._speeds= []
        self._noMove= []
        self._splitStart= []
        self._splitEnd= []
        self._realstart= -1
        self._realend= -1
        
    def setID(self, newID):
        self._id= newID
    
    def setDuration(self, d):
        self._duration= d
    
    def addDistance(self, dist):
        if dist < 0.001:            
            self._noMove.append(len(self._dists))
            if len(self._noMove) >100: #50
                if self._noMove[0] in self._splitStart:
                    self._splitEnd[-1]= self._noMove[-1]
                else:
                    self._splitStart.append(self._noMove[0])
                    self._splitEnd.append(self._noMove[-1])
                #print "split", self._splitStart, self._splitEnd
            elif self._noMove[-1] == len(self._tsList):
                # am ende die nullen wegschneiden
                self._realend= self._noMove[0]
                if self._id == "9682_2017-05-07_023159":
                    print("Cut end from 9682")
        else:
            #am anfang die nullen wegschneiden
            if self._realstart == -1 and len(self._noMove) >0:
                self._realstart == self._noMove[-1]
            self._noMove= []
        self._dists.append(dist)
        
    def addTimestamp(self, time):
        if time > self._tsList[-1]:
            self._tsList.append(time)
        else:
            print("Fehler ", time)
    
    def addXPosition(self, x):
        self._latList.append(x)

    def addYPosition(self, y):
        self._lonList.append(y)  
    
    def getLength(self):
        return len(self._tsList)

    def getID(self):
        return self._id      
        
    def getLat(self):
        return self._latList
    
    def getLon(self):
        return self._lonList
        
    def getTimeStamps(self):
        return self._tsList
        
    def getSpeeds(self):
        if len(self._speeds()) <=0: 
            calculateSpeeds
        return self._speeds
        
    def getDuration(self):
        return self._duration
      
    def getTotalDist(self):
        total= 0
        for d in self._dists:
            if d > -1: 
                total += d
            else:
                return -1
        #if total> 35:
        #    print self._duration ,len(self._dists), total, self._id
        return total
        
    def getNoMoveLen(self):
        return len(self._noMove)
        
    def getNoMove(self):
        return self._noMove
    
    def calculateSpeeds(self):
        speeds= []
        i=0
        for dist in self._dists:
            speed= (dist / self._tsList[i] - self._tsList[i+1]) 
            i +=1
            speeds.append(speed)
        self._speeds = speeds
        return speeds
        
    def splitNoMove(self):
        if self._realend > -1:
            self._tsList = self._tsList[:self._realend]
            self._dists= self._dists[:self._realend]
            self._speeds= self._speeds[:self._realend]
            self._latList = self._latList[:self._realend]
            self._lonList = self._lonList [:self._realend]
            if self._realend < self._splitEnd[0]:
                self._splitEnd[0]= self._realend
            self._realend= -1
        if self._realstart > -1:
            self._tsList = self._tsList[self._realstart :]
            self._dists= self._dists[self._realstart :]
            self._speeds= self._speeds[self._realstart :]
            self._latList = self._latList[self._realstart :]
            self._lonList = self._lonList [self._realstart :]
            if len(self._splitStart) >0:
                self._splitStart= self._splitStart[0] -self._realstart
            if len(self._splitEnd) >0:
                self._splitEnd= self._splitEnd[0] -self._realstart
            self._realstart[0]= -1
        
        if len(self._splitStart) >0:
            if self._splitStart[0] < 1:
                print("Beginning no move")
                #new trajectory for the ending
                newID2= self._id.split("_")[0] + '_'+self._tsList[-1].strftime("%Y-%m-%d_%H%M%S")
                newT2= Trajectory(newID2, self._tsList[self._splitEnd[0]:], self._latList[self._splitEnd[0]:], self._lonList[self._splitEnd[0]:])
                return  -1, newT2
            else:
                #print "Split", self._splitStart, self._splitEnd
                #new trajectory for the begining 
                newID= self._id.split("_")[0] + '_'+self._tsList[-1].strftime("%Y-%m-%d_%H%M%S")
                newT= Trajectory(newID, self._tsList[0:self._splitStart[0]], self._latList[0:self._splitStart[0]], self._lonList[0:self._splitStart[0]])

                #new trajectory for the ending
                newID2= self._id.split("_")[0] + '_'+self._tsList[-1].strftime("%Y-%m-%d_%H%M%S")
                newT2= Trajectory(newID2, self._tsList[self._splitEnd[0]:], self._latList[self._splitEnd[0]:], self._lonList[self._splitEnd[0]:])
                return newT, newT2
        return -1, -1
    

def importTrajectoriesFromConvexis(filename):
    """Reads trajectories from convexis csv file 
    In:
    - name of the csv file
    Out:
    - array of trajectories
    """
    #csv format "id","st_x","st_y","timestmp"
    try: f = open(filename, 'r')
    except: sys.exit("File cannot be read!")
    
    print("Importing trajectories from csv file %s..." % filename)
    
    trajectories = {}
    tIDs= {}
    routeTimes= []
    for line in f:
        line = line.strip("\n")
        temp = line.split(',')
        objectID= temp[0]
        objectID= objectID.strip('"')
        if objectID and objectID !='fk_vehicle_id':
            if objectID in trajectories.keys():
                newtime= datetime.strptime((temp[3].strip('"')),"%Y-%m-%d %H:%M:%S")#.strftime('%S')
                t=trajectories[objectID] 
                time= t._tsList
                timeDelta= (newtime- time[-1]).total_seconds() #timeDelta= (datetime.datetime.strptime(newtime, "%Y-%m-%d %H:%M:%S")- datetime.datetime.strptime(time[-1], "%Y-%m-%d %H:%M:%S")).total_seconds()
                if  timeDelta > 0 and timeDelta <10 : 
                    #print timeDelta, objectID
                    t.addTimestamp(newtime)
                    t.addXPosition(float(temp[2].strip('"')))
                    t.addYPosition(float(temp[1].strip('"')))
                    trajectories[objectID] = t
                elif timeDelta >=10:
                    oldT= trajectories[objectID]
                    newID= objectID + '_'+time[-1].strftime("%Y-%m-%d_%H%M%S")
                    oldT.setID(newID)
                    trajectories[newID]= oldT 
                    #d= (datetime.datetime.strptime((temp[3].strip('"')),"%Y-%m-%d %H:%M:%S"))
                    tsList= [(datetime.strptime((temp[3].strip('"')),"%Y-%m-%d %H:%M:%S"))]#.strftime('%S')]
                    xList= [float(temp[2].strip('"'))]
                    yList= [float(temp[1].strip('"'))]
                    #objectID += str(tsList[0])
                    t = Trajectory(objectID, tsList, xList, yList)
                    trajectories[objectID]= t  
                    #print 'new trajectorie'
                # elif timeDelta== 0: 
                    # print 'values are identical' #todo vehicle ids are staying the same over time
                # else: 
                    # print 'negative', newtime, time[-1]

            else:   
                tsList= [(datetime.strptime((temp[3].strip('"')),"%Y-%m-%d %H:%M:%S"))]#.strftime('%S')]
                x, y, zone, letter = utm.from_latlon(float(temp[2].strip('"')), float(temp[1].strip('"')))
                xList= [x]
                yList= [y]
                t = Trajectory(objectID, tsList, xList, yList)
                trajectories[objectID]= t 
    print(len(trajectories.keys()))
    return trajectories.values()
    
def calculateRouteTimes(filename, trajectories):
    print('Calculate route times')
    durations=[]
    f = open(filename, 'w') 
    for t in trajectories: 
        start= t._tsList[0]
        end= t._tsList[-1]
        duration= (end- start).total_seconds()
        d= end- start
        t.setDuration(d)
        f.write('%s:%s'% (t._id,d))
        if duration > 4000 or duration < 10:
            pass #print t.getID(), duration
        else:
            durations.append(duration)

        f.write('\n')
    f.close()
    
    #histogramm
    outputFile= 'ev_routetimes_histogramm.png' 
    fig, ax = plt.subplots()
    plt.title('Duration of the emergency vehicle drives (2018)')
    x= []
    #print len(durations)
    for i in durations:
        x.append(i/60)

    num_bins = 60
    n, bins, patches = ax.hist(x, num_bins, density=1)
    plt.axvspan(0, 8, facecolor='#2ca02c', alpha=0.2)
    plt.axvspan(8, 15, facecolor='yellow', alpha=0.2)
    plt.axvspan(15, 60, facecolor='#d62728', alpha=0.2)
    plt.xlabel('Time (min)')
    plt.ylabel('Probability of emergency operations')
    plt.savefig(outputFile)
    plt.close(fig)
    
    #comulative
    outputFile= 'ev_routetimes_comulative.png' 
    fig, ax = plt.subplots()
    plt.title('Duration of the emergency vehicle drives (2018)')
    n, bins, patches = ax.hist(x, num_bins, histtype='step',cumulative=True, density=1)
    plt.axvspan(0, 8, facecolor='#2ca02c', alpha=0.2)
    plt.axvspan(8, 15, facecolor='yellow', alpha=0.2)
    plt.axvspan(15, 60, facecolor='#d62728', alpha=0.2)
    plt.xlabel('Time (min)')
    plt.ylabel('Likelihood of reaching the destiny')
    plt.savefig(outputFile)
    plt.close(fig)
        
    
    
    #boxplot
    outputFile= 'ev_routetimes_boxplots.png' 
    fig, ax = plt.subplots()
    plt.title('Duration of the emergency vehicle drives (2018)')
    ax.boxplot(durations)
    plt.savefig(outputFile)
    plt.close(fig)   

def generatePOIs(filename, trajectories, position):
    f = open(filename, 'w') 
    for t in trajectories:
        f.write('<poi id=\"' + str(t.getID()) +'\" color=\"0,0,128\" layer=\"-1.00\" lat=\"' + str(t.getLat()[position]) + '\" lon=\"' + str(t.getLon()[position])+'\"/>\n')
 
def generateODMatrix(filename, trajectories):
    f = open(filename, 'w') 
    f.write('TrajectoryID;StartLat;StartLon;EndLat;EndLon;Duration;\n')
    for t in trajectories:   
        if t.getDuration().total_seconds() > 60 and t.getDuration().total_seconds() < 4000:
            f.write( str(t.getID()) +';' + str(t.getLat()[0]) + ';' + str(t.getLon()[0])+ ';' + str(t.getLat()[-1]) + ';' + str(t.getLon()[-1])+';' + str(t.getDuration()) + ';\n')
     

    
def convertTraces(filename, trajectories):
    print('Convert Traces')
    f = open(filename, 'w')
    for t in trajectories: 
        f.write('%s:'% (t._id))
        for i in range(t.getLength()):
            f.write('%s,%s '% (t._lonList[i], t._latList[i]))
        f.write('\n')
        
def setCalDuration(t):
    start= t._tsList[0]
    end= t._tsList[-1]
    duration= (end- start).total_seconds()
    d= end- start
    t.setDuration(d)
 
def calculateDistances(trajectories):
    totals= []
    durations= []
    dist= 0
    durationsN= []
    totalsN= []
    tkeys= []
    countMove= []
    splittedT= []
    for t in trajectories:
        for i in range(len(t.getLat()) -1):
            dist= 0
            try:
                dist = mpu.haversine_distance((t.getLat()[i], t.getLon()[i]), (t.getLat()[i+1], t.getLon()[i+1]))
                #if t.getID() == "9599_2016-07-11_112725":
                #   print dist, t._dists
                if dist > 1.5:
                    print("Kann nicht sein " + t.getID() + ' ' +  str(dist))
                    dist =-1
                t.addDistance(dist)
            except ValueError:
                dist =-1
                print("Wrong Value" ) 

        #handle split trajectories
        new1, new2= t.splitNoMove()
        if new2 != -1:
            setCalDuration(new2)
            splittedT.append(new2)
            if new1 != -1:
                setCalDuration(new1)
                splittedT.append(new1)
        else:
            setCalDuration(t)
            splittedT.append(t)
        # set real end and begining
        
        
    for t in splittedT:  
        #copy from above 
        for i in range(len(t.getLat()) -1):
            dist= 0
            try:
                dist = mpu.haversine_distance((t.getLat()[i], t.getLon()[i]), (t.getLat()[i+1], t.getLon()[i+1]))
                #if t.getID() == "9599_2016-07-11_112725":
                #   print dist, t._dists
                if dist > 1.5:
                    #print "Kann nicht sein " + t.getID() + ' ' +  str(dist)
                    dist =-1
                t.addDistance(dist)
            except ValueError:
                dist =-1
                print("Wrong Value" ) 
                
        #end copy
        countMove.append(t.getNoMoveLen())
        #print t.getDuration()
        time= t.getDuration().total_seconds()/60
        dist= t.getTotalDist()
    
        if time > 1 and time < 60 and dist > 1:
            totals.append(t.getTotalDist())
            durations.append(time)
            tkeys.append(t.getID())
            #get night drives only
            if len(t.getID().split("_")) >1:
                timestring= t.getID().split("_")[2]
                if int(timestring) < 40000:
                    durationsN.append(time)
                    totalsN.append(t.getTotalDist())
                    if time > 30 and dist <10:
                        print( "Lange Nacht: ", t.getID(), time)#, dist, t._dists
                    
        if t.getID() == "1137_2016-07-22_182457":
            print(t.getDuration(), t._dists, len(t._dists))
    #plot
    outputFile= 'ev_routetimes_distances.png' 
    fig, ax = plt.subplots()
    plt.title('Duration and distances of the emergency vehicle trips')
    ax.plot(durations, totals, '.')
    ax.plot([0,30], [0, 25], 'r-', label= "Average speed of 50 km/h")
    ax.plot([0,50], [0, 25], '--', label= "Average speed of 30 km/h")
    plt.xlabel('Time (min)')
    plt.ylabel('Distance (km)')
    plt.legend(loc='lower right', shadow=True, fontsize='large')
    plt.savefig(outputFile)
    plt.close(fig)   
    
        #plot
    outputFile= 'ev_routetimes_distances_deutsch.png' 
    fig, ax = plt.subplots()
    plt.title('Dauer und Distanz der Einsatzfahrten')
    ax.plot(durations, totals, '.')
    ax.plot([0,30], [0, 25], 'r-', label= "Durchschnitssgeschwindigkeit von 50 km/h")
    ax.plot([0,50], [0, 25], '--', label= "Durchschnitssgeschwindigkeit von 30 km/h")
    plt.xlabel('Zeit (min)')
    plt.ylabel('Distanz (km)')
    plt.legend(loc='upper right', shadow=True, fontsize='large')
    plt.savefig(outputFile)
    plt.close(fig)  


    #plot nur nachtfahrten
    outputFile= 'ev_routetimes_distances_nachts_deutsch.png' 
    fig, ax = plt.subplots()
    plt.title('Dauer und Distanz der Einsatzfahrten (Nachts)')    
    ax.plot(durationsN, totalsN, '.')
    ax.plot([0,30], [0, 25], 'r-', label= "Durchschnitssgeschwindigkeit von 50 km/h")
    ax.plot([0,50], [0, 25], '--', label= "Durchschnitssgeschwindigkeit von 30 km/h")
    plt.xlabel('Zeit (min)')
    plt.ylabel('Distanz (km)')
    plt.legend(loc='upper right', shadow=True, fontsize='large')
    plt.savefig(outputFile)
    plt.close(fig)     
    
    f = open('dauer_dist.csv', 'w') 
    i=0
    f.write('id,vehicleid,zeit,distanz\n')
    for d in durations: 
        f.write('%s,%s,%s,%s' %(tkeys[i], tkeys[i].split('_')[0],d,totals[i]))
        f.write('\n')
        i+= 1
    f.close() 
    
    print(np.mean(durations))
    print(np.mean(totals))
    print((np.mean(totals)/np.mean(durations))*60)
    under8=0.
    for d in totals:
        if d <= 8:
            under8+=1
    print(under8/len(totals)    )
    
    return splittedT
   

    
        
def writeTrips(filename, trajectories): 
    #i=0
    for t in trajectories:
        #i+=1
        #if t.getID() == "9599_2016-07-11_112725":

        f = open( "trips\\" +t.getID()+ "_" + filename, 'w')
        f.write("<additional xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" xsi:noNamespaceSchemaLocation=\"http://sumo.dlr.de/xsd/additional_file.xsd\"><location convBoundary=\"1215.37,480.71,36294.87,30350.79\" origBoundary=\"9.866920,52.146541,10.806219,52.446520\" projParameter=\"+proj=utm +zone=32 +ellps=WGS84 +datum=WGS84 +units=m +no_defs\"/>")
        for i in range(len(t.getLat())):
            f.write('<poi id=\"' + str(t.getID())+ str(i) +'\" color=\"0,0,128\" layer=\"-1.00\" lat=\"' + str(t.getLat()[i]) + '\" lon=\"' + str(t.getLon()[i])+'\"/>\n')    
        f.write("</additional>")
        f.close()

def writeNewRouteData(filename, trajectories):
    f = open(filename, 'w') 
    for t in trajectories: 
        start= t._tsList[0]
        end= t._tsList[-1]
        id= t._id.split('_')[0]# timeString.split(':')[0])
        f.write('%s_%s'% (id,end))
        f.write('\n')
    f.close()   

def writeNewRouteDurationData(filename, trajectories):
    f = open(filename, 'w') 
    for t in trajectories: 
        start= t._tsList[0]
        end= t._tsList[-1]
        duration= t.getDuration()
        id= t._id.split('_')[0]# timeString.split(':')[0])
        f.write('%s,%s,%s,%s'% (id,start, end, duration))
        f.write('\n')
    f.close()      
    
def writeCSV(trajectories, filename):
    f2= open(filename, 'w') 
    f2.write('TrajectoryID,Timestamp,Long,Lat')
    f2.write('\n')
    idMap= {}      
    
    f = open('start_end_'+filename, 'w') 
    f.write('TrajectoryID,VehicleID,Time,Duration,Distance')
    f.write('\n')
    for t in trajectories:
        duration= t.getDuration().total_seconds()/60
        distance= t.getTotalDist()
        vehicleID=  t._id.split('_')[0]
        if distance > 1. and duration > 1.:
            if len(t.getID().split("_")) > 1: #todo eine trajetory pro id fehlt
                f.write('%s,%s,%s,%s,%s' %(t.getID(),vehicleID, int(t.getID().split("_")[2]), duration,distance))
                f.write('\n')
                
                #file2
                i= 0
                longs= t.getLon()
                lats= t.getLat()
                id=  t._id.split('_')[0]
                index=0
                if id in idMap:
                    index= idMap[id]
                    index += 1
                    idMap[id]= index
                else:
                    idMap[id]= 0
                tid= str(id)+ '_'+ str(index)
                
                for ts in t.getTimeStamps():
                    f2.write('%s,%s,%s,%s' %(tid,ts, longs[i], lats[i]))
                    f2.write('\n')
                    i +=1     
    f.close()    
    f2.close()     

trajectories= importTrajectoriesFromConvexis("new2018.csv") #new.csv") #("convexis2016-juli_gesamt.csv")
calculateRouteTimes("new2.csv", trajectories)#("routeTimes2016-juli_gesamt.csv", trajectories)
convertTraces("traces_2018_new.csv", trajectories)
generatePOIs("start.poi.xml", trajectories, 0)
generatePOIs("end.poi.xml", trajectories, -1)
trajectories= calculateDistances(trajectories)
writeCSV(trajectories, "trajectroies_processed.csv")
calculateRouteTimes("new2.csv", trajectories)#("routeTimes2016-juli_gesamt.csv", trajectories)
generateODMatrix("odpari.csv", trajectories)
convertTraces("traces_2018_new.csv", trajectories)
writeTrips("trip.poi.xml", trajectories)
writeNewRouteDurationData("StartEndRoutes.csv", trajectories) #"newRoutesEnds.csv", trajectories)
