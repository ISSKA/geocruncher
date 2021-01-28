import json
import numpy as np

class MapSlice:

    def output(xCoord, yCoord, nPoints, ranks, evaluate_z):
        def computeRank(a, b):
            return ranks([a, b, evaluate_z([a, b])])

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

    def output(xCoord, yCoord, zCoord, nPoints, ranks, imgSize):
        def computeRank(a, z):
            if not isOnYAxis:
                y = slope * (a - xCoord[0]) + yCoord[0]
                return ranks([a, y, z])
            else:
                return ranks([xCoord[0], a, z])

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
        else:
            ySliceRange = np.linspace(yCoord[0], yCoord[1], nPoints)
            z, y = np.meshgrid(zSliceRange, ySliceRange)

        # Main computation loop
        rankMatrix = list((map(computeRankMatrix, (np.arange(0, nPoints)))))
        return rankMatrix


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
