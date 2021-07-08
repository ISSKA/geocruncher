import pytest

import numpy as np
from geocruncher.tunnel_shape_generation import _project_points
from random import uniform, randint

def _make_straight_segment(length, nb_vertices):
    points = []
    for i in range(nb_vertices):
        distance = length * i / nb_vertices
        points.append(np.array([0, distance - length/2, 0]))
    return points

def test_bottomPointsShouldHaveSameZ():
    for _ in range(100):
        length = uniform(1, 200)
        nb_vertices = randint(5, 35)
        xy_points = _make_straight_segment(length, nb_vertices)
        normal = [uniform(-10, 10), uniform(-10, 10), uniform(0, 10)]
        bottom = [uniform(-10, 10), uniform(-10, 10), uniform(-10, 10)]

        verts = _project_points(normal, bottom, xy_points)
        zc = [v[2] for v in verts]
        d = max(zc) - min(zc)
        assert np.std(zc) === 0, "Test failed for: the following setup: " + str({"difference": str(d), "length": str(
            length), "nb_vertices": str(nb_vertices), "xy_points": str(xy_points), "normal": normal, "bottom": bottom, "verts": str(verts)})
