import json
import math

import numpy as np
import pyvista as pv
import sys
import os

class MapSlice:

    def output(xCoord, yCoord, nPoints, ranks, evaluate_z, isBase):
        def computeRank(a, b):
            return ranks([a, b, evaluate_z([a, b])]) - 1 if isBase else ranks([a, b, evaluate_z([a, b])])

        def computeRankMatrix(index):
            return np.array(list(map(computeRank, x[index], y[index]))).transpose().tolist()

        # x,y,z Coordinates expressed in real coordinates
        xMapRange = np.linspace(xCoord[0], xCoord[1], nPoints)
        yMapRange = np.linspace(yCoord[0], yCoord[1], nPoints)

        # x, z = np.ogrid[xCoord[0]:xCoord[1]:nPoints , zCoord[0]:zCoord[1]:nPoints]
        y, x = np.meshgrid(yMapRange, xMapRange)

        rankMatrix = list((map(computeRankMatrix, (np.arange(0, nPoints)))))
        return rankMatrix


class Slice:

    def output(xCoord, yCoord, zCoord, nPoints, ranks, imgSize, isBase, data, meshes_files):
        def computeRank(a, z):
            if not isOnYAxis:
                y = slope * (a - xCoord[0]) + yCoord[0]
                return ranks([a, y, z]) - 1 if isBase else ranks([a, y, z])
            else:
                return ranks([xCoord[0], a, z]) - 1 if isBase else ranks([xCoord[0], a, z])

        def computeRankMatrix(index):
            if not isOnYAxis:
                return np.array(list(map(computeRank, x[index], z[index]))).transpose().tolist()
            else:
                return np.array(list(map(computeRank, y[index], z[index]))).transpose().tolist()

        zSliceRange = np.linspace(zCoord[0], zCoord[1], nPoints)

        isOnYAxis = xCoord[0] == xCoord[1]
        if not isOnYAxis:
            slope = (yCoord[0] - yCoord[1]) / (xCoord[0] - xCoord[1])
            xSliceRange = np.linspace(xCoord[0], xCoord[1], nPoints)
            z, x = np.meshgrid(zSliceRange, xSliceRange)
            if "springs" in data or "drillholes" in data:
                xyz = np.stack((x, np.ones_like(x) * yCoord[0], z), axis=-1)
                xyz.shape = (-1, 3)
                Slice.ouputHydroLayer(np.array([xCoord[0], yCoord[0], zCoord[0]]), np.array([xCoord[1], yCoord[1], zCoord[1]]), xyz, [], data["springs"], data["drillholes"], meshes_files)
        else:
            ySliceRange = np.linspace(yCoord[0], yCoord[1], nPoints)
            z, y = np.meshgrid(zSliceRange, ySliceRange)
            if "springs" in data or "drillholes" in data:
                xyz = np.stack((np.ones_like(y) * xCoord[0], y, z), axis=-1)
                xyz.shape = (-1, 3)
                Slice.ouputHydroLayer(np.array([xCoord[0], yCoord[0], zCoord[0]]), np.array([xCoord[1], yCoord[1], zCoord[1]]), xyz, [], data["springs"], data["drillholes"], meshes_files)



        # Main computation loop
        rankMatrix = list((map(computeRankMatrix, (np.arange(0, nPoints)))))
        return rankMatrix

    def ouputHydroLayer(lowerLeft, upperRight, rankMatrix, rankResult, springMap, drillholeMap, gwbMeshFiles):
        def projPointOnPlane(p0, p1, p2, q):
            n = np.cross(np.subtract(p1, p0), np.subtract(p2, p0))  # normal of plane
            n = n / np.linalg.norm(n)
            q_proj = np.subtract(q, np.dot(np.subtract(q, p0), n) * n)
            print(q_proj, file=sys.stderr)
            sys.stderr.flush()
            return transformValue(p0, p1, q_proj)

        def transformValue(p0, p1, q):
            w = math.sqrt(math.pow(p1[0] - p0[0], 2) + math.pow(p1[1] - p0[1], 2))
            h = p1[2] - p0[2]
            return [math.sqrt(math.pow(q[0] - p0[0], 2) + math.pow(q[1] - p0[1], 2)) / w, q[2] / h]

        thirdPoint = np.array([lowerLeft[0], lowerLeft[1], upperRight[2]])
        for dId, line in drillholeMap.items():
            s_proj = projPointOnPlane(lowerLeft, upperRight, thirdPoint, np.array([line["start"]["x"], line["start"]["y"], line["start"]["z"]]))
            e_proj = projPointOnPlane(lowerLeft, upperRight, thirdPoint, np.array([line["end"]["x"], line["end"]["y"], line["end"]["z"]]))
            proj_line = [s_proj, e_proj]
            print(proj_line, file=sys.stderr)
            sys.stderr.flush()
        for sId, p in springMap.items():
            sys.stderr.write("sIspring \r\n")
            p_proj = projPointOnPlane(lowerLeft, upperRight, thirdPoint, np.array([p["x"], p["y"], p["z"]]))
            print(p_proj, file=sys.stderr)
            sys.stderr.flush()
        for gwb_Mesh in gwbMeshFiles:
            sys.stderr.write("mesh \r\n")
            gwb_id = int(gwb_Mesh.split("_")[1])
            mesh = pv.read(gwb_Mesh)
            mesh = mesh.extract_geometry()
            points = pv.PolyData(rankMatrix)
            insidePoints = points.select_enclosed_points(mesh, tolerance=0.0001)
            print(len(rankMatrix), file=sys.stderr)
            print(len([p for p in insidePoints["SelectedPoints"] if p != 0]), file=sys.stderr)
            sys.stderr.flush()


class FaultIntersection:

    def output(xCoord, yCoord, zCoord, nPoints, model):
        zSliceRange = np.linspace(zCoord[0], zCoord[1], nPoints)
        isOnYAxis = xCoord[0] == xCoord[1]
        if not isOnYAxis:
            slope = (yCoord[0] - yCoord[1]) / (xCoord[0] - xCoord[1])
            xSliceRange = np.linspace(xCoord[0], xCoord[1], nPoints)
            x, z = np.meshgrid(xSliceRange, zSliceRange)
            el = np.array([x.flatten(), z.flatten()]).T
            points = list(map(lambda s: [s[0], slope * (s[0] - xCoord[0]) + yCoord[0], s[1]], el))
        else:
            ySliceRange = np.linspace(yCoord[0], yCoord[1], nPoints)
            y, z = np.meshgrid(ySliceRange, zSliceRange)
            el = np.array([y.flatten(), z.flatten()]).T
            points = list(map(lambda s: [xCoord[0], s[0], s[1]], el))
        output = {}
        for name, fault in model.faults.items():
            coloredPoints = np.array(np.array_split(fault(points), nPoints))
            output[name] = coloredPoints.tolist()
        return output

class MapFaultIntersection:

    def output(xCoord, yCoord, nPoints, model):
        xMapRange = np.linspace(xCoord[0], xCoord[1], nPoints)
        yMapRange = np.linspace(yCoord[0], yCoord[1], nPoints)
        x, y = np.meshgrid(xMapRange, yMapRange)
        el = np.array([x.flatten(), y.flatten()]).T
        points = list(map(lambda s: [s[0], s[1], model.topography.evaluate_z([s[0], s[1]])], el))
        output = {}
        for name, fault in model.faults.items():
            coloredPoints = np.array(np.array_split(fault(points), nPoints))
            output[name] = coloredPoints.tolist()
        return output
