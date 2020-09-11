from geocruncher.ComputeIntersections import Slice, MapSlice


# TODO probably also add a test here for the new slice fuction -> or integrate into the existing one?

def test_sliceAroundYAxisTestPointsRegularly():
    tested_points = []

    def fakeRank(l):
        tested_points.append(l)
        return 0

    Slice.output([0, 0], [10, 29], [0, 19], [20, 20], fakeRank)
    for y in range(10, 30):
        for z in range(0, 20):
            assert [float(0), float(y), float(z)] in tested_points


def test_sliceForSlopOfOneTestPointsRegularly():
    tested_points = []

    def fakeRank(l):
        tested_points.append(l)
        return 0

    Slice.output([0, 19], [10, 29], [0, 19], [20, 20], fakeRank)
    for xy in range(0, 20):
        for z in range(0, 20):
            assert [float(xy), float(10 + xy), float(z)] in tested_points


def test_sliceForSlopeOfZeroTestPointsRegularly():
    tested_points = []

    def fakeRank(l):
        tested_points.append(l)
        return 0

    Slice.output([0, 19], [10, 10], [0, 19], [20, 20], fakeRank)
    for x in range(0, 20):
        for z in range(0, 20):
            assert [float(x), float(10), float(z)] in tested_points


def test_mapSliceTestPointsRegularlyForFlatGround():
    tested_points = []

    def fakeRank(l):
        tested_points.append(l)
        return 0

    def fakeCalculateZ(xy):
        return 10

    MapSlice.output([0, 19], [10, 29], 20, fakeRank, fakeCalculateZ)
    for x in range(0, 20):
        for y in range(10, 30):
            assert [float(x), float(y), float(10)] in tested_points


def test_mapSliceTestPointsRegularlyForDescendingGroundX():
    tested_points = []

    def fakeRank(l):
        tested_points.append(l)
        return 0

    def fakeCalculateZ(xy):
        return 20 - xy[0]

    MapSlice.output([0, 19], [10, 29], 20, fakeRank, fakeCalculateZ)
    for x in range(0, 20):
        for y in range(10, 30):
            assert [float(x), float(y), float(20 - x)] in tested_points
