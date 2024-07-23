import math

import numpy as np
import pyvista as pv
import meshio
from io import StringIO


from .profiler.profiler import get_current_profiler
from .off import read_off

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
        get_current_profiler().profile('map_grid')

        rankMatrix = list((map(computeRankMatrix, (np.arange(0, nPoints)))))
        get_current_profiler().profile('map_ranks')
        return rankMatrix


class Slice:
    @staticmethod
    def output(xCoord, yCoord, zCoord, nPoints, ranks, imgSize, isBase, data, gwb_meshes: dict[str, list[str]], maxDistProj):
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
        drillholesLine, springsPoint, matrixGwb = {}, {}, []

        # impact of setup code above is insignificant, so we don't profile it in any specific step

        if not isOnYAxis:
            slope = (yCoord[0] - yCoord[1]) / (xCoord[0] - xCoord[1])
            xSliceRange = np.linspace(xCoord[0], xCoord[1], nPoints)
            z, x = np.meshgrid(zSliceRange, xSliceRange)
            if "springs" in data or "drillholes" in data or gwb_meshes:
                # we add a constant y to every 2d point
                y = [slope * (p - xCoord[0]) + yCoord[0] for p in x]
                xyz = np.stack((x, y, z), axis=-1)
                xyz.shape = (-1, 3)
                drillholesLine, springsPoint, matrixGwb = Slice.ouputHydroLayer(np.array([xCoord[0], yCoord[0], zCoord[0]]), np.array(
                    [xCoord[1], yCoord[1], zCoord[1]]), xyz, data["springs"], data["drillholes"], gwb_meshes, maxDistProj)
        else:
            ySliceRange = np.linspace(yCoord[0], yCoord[1], nPoints)
            z, y = np.meshgrid(zSliceRange, ySliceRange)
            if "springs" in data or "drillholes" in data or gwb_meshes:
                # we add a constant x to every 2d point
                xyz = np.stack((np.ones_like(y) * xCoord[0], y, z), axis=-1)
                xyz.shape = (-1, 3)
                drillholesLine, springsPoint, matrixGwb = Slice.ouputHydroLayer(np.array([xCoord[0], yCoord[0], zCoord[0]]), np.array(
                    [xCoord[1], yCoord[1], zCoord[1]]), xyz, data["springs"], data["drillholes"], gwb_meshes, maxDistProj)

        # Main computation loop
        rankMatrix = list((map(computeRankMatrix, (np.arange(0, nPoints)))))
        get_current_profiler().profile('sections_ranks')
        return rankMatrix, drillholesLine, springsPoint, matrixGwb

    @staticmethod
    def ouputHydroLayer(lowerLeft, upperRight, rankMatrix, springMap, drillholeMap, gwb_meshes: dict[str, list[str]], maxDistProj):
        def projPointOnPlane(p0, p1, p2, q):
            # https://stackoverflow.com/a/8944143
            n = np.cross(np.subtract(p1, p0), np.subtract(p2, p0))  # normal of plane
            n = n / np.linalg.norm(n)
            q_proj = np.subtract(q, np.dot(np.subtract(q, p0), n) * n)
            if np.linalg.norm(np.subtract(q, q_proj)) < maxDistProj:
                return (transformValue(p0, q_proj), True)
            else:
                return (transformValue(p0, q_proj), False)

        def transformValue(p0, q):
            # transform point in 2d; x, y
            return [math.sqrt(math.pow(q[0] - p0[0], 2) + math.pow(q[1] - p0[1], 2)), q[2]]

        # we need a third point to create a plane
        # and we know that the up point of cs are juste higher z and there is not vertical angle
        thirdPoint = np.array([lowerLeft[0], lowerLeft[1], upperRight[2]])
        matrixGwb = []
        drillholesLine = {}
        springsPoint = {}
        get_current_profiler().profile('hydro_setup')
        for dId, line in drillholeMap.items():
            s_proj, s_valid = projPointOnPlane(lowerLeft, upperRight, thirdPoint, np.array([line["start"]["x"], line["start"]["y"], line["start"]["z"]]))
            e_proj, e_valid = projPointOnPlane(lowerLeft, upperRight, thirdPoint, np.array([line["end"]["x"], line["end"]["y"], line["end"]["z"]]))
            if s_valid or e_valid:
                proj_line = [s_proj, e_proj]
                drillholesLine[dId] = proj_line
        get_current_profiler().profile('hydro_project_drillholes')
        for sId, p in springMap.items():
            p_proj, valid = projPointOnPlane(lowerLeft, upperRight, thirdPoint, np.array([p["x"], p["y"], p["z"]]))
            if valid:
                springsPoint[sId] = p_proj
        get_current_profiler().profile('hydro_project_springs')
        # read all mesh files an test for every point if inside of gwb or not
        for gwb_id, meshes in gwb_meshes.items():
            for mesh_str in meshes:
                mesh = pv.from_meshio(read_off(mesh_str)).extract_geometry()
                points = pv.PolyData(rankMatrix)
                inside_points = points.select_enclosed_points(
                    mesh, tolerance=0.00001)
                # 0 if not in gwb else gwb_id
                matrixGwb.append(inside_points["SelectedPoints"] * int(gwb_id))
        get_current_profiler().profile('hydro_test_inside_gwbs')
        # combine all gwb values into one matrix
        matrixGwbCombine = []
        if len(matrixGwb) > 0:
            for idx, val in enumerate(matrixGwb[0]):
                values = [values[idx] for values in matrixGwb if values[idx] > 0]
                matrixGwbCombine.append(int(values[0]) if len(values) > 0 else 0)  # we need to cast to int from int8 to be able to serialise in json
        get_current_profiler().profile('hydro_combine_gwbs')
        return drillholesLine, springsPoint, matrixGwbCombine


class FaultIntersection:

    @staticmethod
    def vertical_grid(A, B, nu, nv):
        """
        :param A: *lower left* corner (3D)
        :param B: *upper right* corner (3D)
        :param nu: number of points along horizontal axis
        :param nv: number of points along vertival axis
        """
        points = np.repeat(A[None, :], nu, axis=0)
        points = np.repeat(points[None, :], nv, axis=0)
        AB = B - A
        points[..., :2] += (np.linspace(0, 1, nu)[:, None]*AB[:2])[None, :]
        points[..., 2] += (np.linspace(0, 1, nv)*AB[2])[:, None]
        points.shape = -1, 3  # to have the same point order
        return points

    @staticmethod
    def new_vertical_grid(xCoord, yCoord, zCoord, nPoints):
        # TODO: modify input data to correspond to new format
        return FaultIntersection.vertical_grid(
            np.array([xCoord[0], yCoord[0], zCoord[0]], dtype="d"), # maybe dtype="d" (double precision) is too much
            np.array([xCoord[1], yCoord[1], zCoord[1]], dtype="d"),
            nPoints, nPoints,
        )

    @staticmethod
    def output(xCoord, yCoord, zCoord, nPoints, model):
        points = FaultIntersection.new_vertical_grid(xCoord, yCoord, zCoord, nPoints)
        get_current_profiler().profile('sections_grid')
        output = {}
        for name, fault in model.faults.items():
            coloredPoints = np.array(np.array_split(fault(points), nPoints))
            output[name] = coloredPoints.tolist()
        get_current_profiler().profile('sections_tesselate')
        return output

class MapFaultIntersection:

    @staticmethod
    def output(xCoord, yCoord, nPoints, model):
        xMapRange = np.linspace(xCoord[0], xCoord[1], nPoints)
        yMapRange = np.linspace(yCoord[0], yCoord[1], nPoints)
        x, y = np.meshgrid(xMapRange, yMapRange)
        el = np.array([x.flatten(), y.flatten()]).T
        points = list(map(lambda s: [s[0], s[1], model.topography.evaluate_z([s[0], s[1]])], el))
        get_current_profiler().profile('map_grid')
        output = {}
        for name, fault in model.faults.items():
            coloredPoints = np.array(np.array_split(fault(points), nPoints))
            output[name] = coloredPoints.tolist()
        get_current_profiler().profile('map_tesselate')
        return output
