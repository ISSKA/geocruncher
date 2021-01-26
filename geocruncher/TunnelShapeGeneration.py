import math
import numpy as np
from sympy.parsing.sympy_parser import parse_expr
from sympy import diff, symbols
import MeshTools.CGALWrappers as CGAL

def tunnel_to_meshes(functions, step, nb_vertices, xy_points, outFile):
    """Generate a mesh for a tunnel

    Args:
        functions (list((str, str, str))): the functions that define the tunnel (separated for x, y, z and for t between 0 and 1)
        step (float): size of a step between 0 and 1
        nb_vertices (int): number of vertices that define a segment
        xy_points (list((int, int, int))): points representing a segment of the tunnel on the xy plane
        outFile (str): the file to output (off file)
    """
    vertices = []
    t = symbols("t")
    nb_series = 0
    for f in functions:
        fx = parse_expr(f["x"].replace("^", "**"))
        dfx = diff(fx, t)
        fy = parse_expr(f["y"].replace("^", "**"))
        dfy = diff(fy, t)
        fz = parse_expr(f["z"].replace("^", "**"))
        dfz = diff(fz, t)
        for i in np.arange(0.0, 1.0, step):
            normal = np.array([float(dfx.subs(t, i)), float(dfy.subs(t, i)), float(dfz.subs(t, i))])
            bottom = np.array([float(fx.subs(t, i)), float(fy.subs(t, i)), float(fz.subs(t, i))])
            for p in _project_points(normal, bottom, xy_points):
                vertices.append(p)
            nb_series += 1
    triangles = _connect_vertices(nb_vertices, nb_series)
    CGAL.TSurf(vertices, np.array(triangles)).to_off(outFile)

def get_circle_segment(radius, nb_vertices):
    """Get a segment on the xy plane of a circle

    Args:
        radius (float): radius of the circle
        nb_vertices (int): number of vertices that will define the segment

    Returns:
        list((int, int, int)): the vertices that represent the segment on the xy plane
    """
    points = []
    for i in range(nb_vertices): 
        angle = (math.pi*2) * i / nb_vertices 
        points.append(np.array([radius * math.cos(angle), radius * math.sin(angle), 0]))
    return points


def _project_points(normal, center, xy_points):
    uNorm = normal / np.linalg.norm(normal)
    rotMatrix = np.array([
        [uNorm[1]**2 - uNorm[1]**2 * math.sqrt(1 - uNorm[2]**2) + math.sqrt(1 - uNorm[2]**2), uNorm[0] * uNorm[1] * (math.sqrt(1 - uNorm[2]**2) - 1), uNorm[0] * uNorm[2]],
        [uNorm[0] * uNorm[1] * (math.sqrt(1 - uNorm[2]**2) - 1), uNorm[1]**2 * math.sqrt(1 - uNorm[2]**2) + uNorm[2]**2 * math.sqrt(1 - uNorm[2]**2) - uNorm[1]**2 - uNorm[2]**2 + 1, uNorm[1] * uNorm[2]],
        [-uNorm[0] * uNorm[2], -uNorm[1] * uNorm[2], math.sqrt(1 - uNorm[2]**2)]
    ])
    verts = []
    for p in xy_points:
        verts.append((rotMatrix.dot(p) + center).tolist())
    return verts

def _connect_vertices(nb_vertices, nb_serie):
    tri = []
    for curr_serie in range(nb_serie - 1):
        for i in range(nb_vertices):
            if i != nb_vertices - 1:
                tri.append([curr_serie * nb_vertices + i, (curr_serie + 1) * nb_vertices + i, (curr_serie + 1) * nb_vertices + i + 1])
            if i != 0:
                tri.append([curr_serie * nb_vertices + i, curr_serie * nb_vertices + i - 1, (curr_serie + 1) * nb_vertices + i])
        tri.append([curr_serie * nb_vertices, (curr_serie + 1) * nb_vertices - 1, (curr_serie + 1) * nb_vertices])
        tri.append([(curr_serie + 1) * nb_vertices - 1, (curr_serie + 2) * nb_vertices - 1, (curr_serie + 1) * nb_vertices])
    return tri
