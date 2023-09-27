#!/usr/bin/env python
import os
import sys
import csv
import collections
import pyproj
sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
import sumolib


def generatePOIs(filename, trajectories):
    with open(filename, 'w') as f:
        sumolib.xml.writeHeader(f, root="additional")
        for k, v in trajectories.items():
            for i, p in enumerate(v):
                f.write('    <poi id="%s_%s" color="128,0,0" lon="%s" lat="%s"/>\n' % (k, i, p[0], p[1]))
        f.write("</additional>")


def writeRouteFile(filename, vehicle_routes):
    with open(filename, 'w') as f:
        sumolib.xml.writeHeader(f, root="routes")
        # f.write('    <vType id="type1" vClass="delivery" accel="0.8" decel="4.5" sigma="0.5" length="5" maxSpeed="70"/>\n')
        f.write('    <vType id="cepVehicleType0" vClass="delivery" color="1,0,0"/>\n')
        for attr, edges, stops in vehicle_routes:
            f.write('    <vehicle id="%s" type="%s" depart="%s">\n' % attr)
            f.write('        <route edges="%s"/>\n' % (" ".join([e.getID() for e in edges])))
            for s in stops:
                f.write('        <stop lane="%s" endPos="%.2f" duration="%s"/>\n' % s)
            f.write('    </vehicle>\n')
        f.write("</routes>\n")


def generateLoadingZones(net, options):
    transformer = pyproj.Transformer.from_crs("EPSG:31468", "EPSG:4326")
    with sumolib.openz(options.loading_zones, encoding="utf-8-sig") as zones, open(options.loading_zone_poi_output, 'w') as pois, open(options.loading_zone_stop_output, 'w') as stops:
        sumolib.xml.writeHeader(pois, root="additional")
        sumolib.xml.writeHeader(stops, root="additional")
        for data in csv.DictReader(zones, delimiter=";"):
            id = data["ID"]
            xgk = float(data["X_GK4"].replace(',', '.'))
            ygk = float(data["Y_GK4"].replace(',', '.'))
            lat, lon = transformer.transform(ygk, xgk)
            pois.write('    <poi id="zone_%s" color="0,128,0" lon="%s" lat="%s"/>\n' % (id, lon, lat))

            m = 1e400
            min_lane = None
            x, y = net.convertLonLat2XY(lon, lat)
            for lane, d in net.getNeighboringLanes(x, y, options.radius):
                if lane.allows("delivery") and d < m:
                    m = d
                    min_lane = lane
            if min_lane:
                stop.write('    <busStop id="zone_%s" lane="%s" endPos="%s"/>\n' % (id, lon, lat))
        pois.write("</additional>")
        stops.write("</additional>")


def getOptions():
    argParser = sumolib.options.ArgumentParser()
    argParser.add_argument("-t", "--tourlegs", default="tourLegsCharacteristics_UTM.csv.gz",
                           help="tour input data")
    argParser.add_argument("-l", "--loading-zones", default="Ladezonen_100m_Duplicates_Filtered_by_BuildingBlocks.csv.gz",
                           help="loading zones input data")
    argParser.add_argument("-n", "--network", default="net.net.xml.gz",
                           help="name of network file")
    argParser.add_argument("-o", "--output", default="tour.rou.xml",
                           help="route output file")
    argParser.add_argument("-p", "--trajectory-poi-output", default="trajectories.add.xml",
                           help="trajectory poi output file")
    argParser.add_argument("-s", "--loading-zone-stop-output", default="zones.add.xml",
                           help="loading zone output file")
    argParser.add_argument("-z", "--loading-zone-poi-output", default="zone_pois.add.xml",
                           help="loading zone poi output file")
    argParser.add_argument("-r", "--radius", type=float, default=200.,
                           help="search radius")
    return argParser.parse_args()


def addRoute(routes, veh, trajectory, stop_pos, net, radius):
    route = sumolib.route.mapTrace(trajectory, net, radius, fillGaps=2000, vClass="delivery")
    if route:
        stops = []
        for x, y, dur in stop_pos:
            m = 1e400
            min_lane = None
            last_index = 0
            for lane, d in net.getNeighboringLanes(x, y, radius):
                if lane.getEdge() in route[last_index:] and lane.allows("delivery") and d < m:
                    m = d
                    min_lane = lane
            if min_lane:
                pos, _ = min_lane.getClosestLanePosAndDist((x, y))
                stops.append((min_lane.getID(), pos, dur))
                last_index = route.index(min_lane.getEdge(), last_index)
        routes.append((veh, route, stops))
        return True
    return False


def main():
    options = getOptions()
    net = sumolib.net.readNet(options.network)
    x_off, y_off = net.getLocationOffset()
    skipped_routes= 0
    routes = []
    t = collections.defaultdict(list)
        
    with sumolib.openz(options.tourlegs) as tourlegs:
        last_id = None
        trajectory = []
        stop_pos = []
        start_time = None
        for data in csv.DictReader(tourlegs, delimiter=";"):
            id = data["vehicleDriver_Id"]
            if last_id and id != last_id:
                if not addRoute(routes, (last_id, typ, start_time), trajectory, stop_pos, net, options.radius):
                    skipped_routes += 1
                trajectory = []
                stop_pos = []
                start_time = None
            typ = data["vehicleType"]
            if start_time is None:
                start_time = float(data["startTime"].replace(',', '.'))
            startx = float(data["startLocationX_UTM"].replace(',', '.')) + x_off
            starty = float(data["startLocationY_UTM"].replace(',', '.')) + y_off
            if trajectory and (startx, starty) != trajectory[-1]:
                print("Disconnected trajectory for", id)
                trajectory.append((startx, starty))
                t[id].append(net.convertXY2LonLat(startx, starty))
            endx = float(data["endLocationX_UTM"].replace(',', '.')) + x_off
            endy = float(data["endLocationY_UTM"].replace(',', '.')) + y_off
            trajectory.append((endx, endy))
            t[id].append(net.convertXY2LonLat(endx, endy))
            duration = float(data["stopDuration"].replace(',', '.'))
            if stop_pos and stop_pos[-1][:2] == (endx, endy):
                stop_pos[-1] = (endx, endy, stop_pos[-1][2] + duration)
            else:
                stop_pos.append((endx, endy, duration))
            last_id = id
    if not addRoute(routes, (last_id, typ, start_time), trajectory, stop_pos, net, options.radius):
        skipped_routes += 1
    print("Unmatched routes: ", skipped_routes)
    writeRouteFile(options.output, routes)
    generatePOIs(options.trajectory_poi_output, t)
    generateLoadingZones(net, options)


if __name__ == "__main__":
    main()
