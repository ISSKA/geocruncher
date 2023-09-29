import math
import numpy as np
from sympy.parsing.sympy_parser import parse_expr
from sympy import diff, symbols
import scipy.integrate as integrate
from .MeshGeneration import generate_off
from .profiler import get_current_profiler

def tunnel_to_meshes(functions, step, xy_points, idxStart, tStart, idxEnd, tEnd, outFile):
    """Generate a mesh for a tunnel

    Args:
        functions (list((str, str, str))): the functions that define the tunnel (separated for x, y, z and for t between 0 and 1)
        step (float): size of a step between 0 and 1
        xy_points (list((int, int, int))): points representing a segment of the tunnel on the xy plane
        outFile (str): the file to output (off file)
    """
    vertices = []
    t = symbols("t")
    nb_series = 0
    # NOTE: the 3 above lines are timed with the next profile on first loop iteration, but not subsequent
    # to avoid that, we would need to profile right here. but since these 3 lines are insignificant, we don't
    for j in np.arange(idxStart if idxStart != -1 else 0, idxEnd + 1 if idxEnd != -1 else len(functions)):
        f = functions[j]
        fx = parse_expr(f["x"].replace("^", "**"))
        dfx = diff(fx, t)
        fy = parse_expr(f["y"].replace("^", "**"))
        dfy = diff(fy, t)
        fz = parse_expr(f["z"].replace("^", "**"))
        dfz = diff(fz, t)
        get_current_profiler().profile("sympy_parse_diff_function")
        for i in np.arange(tStart if j == idxStart else 0.0, tEnd if j == idxEnd else 1.0, step):
            normal = np.array([float(dfx.subs(t, i)), float(dfy.subs(t, i)), float(dfz.subs(t, i))])
            bottom = np.array([float(fx.subs(t, i)), float(fy.subs(t, i)), float(fz.subs(t, i))])
            get_current_profiler().profile("interpolate_function")
            for p in _project_points(normal, bottom, xy_points):
                vertices.append(p)
            nb_series += 1
            get_current_profiler().profile("project_points")
    triangles = _connect_vertices(len(xy_points), nb_series)
    get_current_profiler().profile("connect_vertices")
    off_mesh = generate_off(vertices, np.array(triangles))
    get_current_profiler().profile("generate_off")
    with open(outFile,'w',encoding='utf8') as f:
        f.write(off_mesh)
    get_current_profiler().profile("write_output")
    return vertices

def get_circle_segment(radius, nb_vertices):
    """Get a segment on the xy plane of a circle

    Args:
        radius (float): radius of the circle
        nb_vertices (int): number of vertices that will define the segment

    Returns:
        list((int, int, int)): the vertices that represent the segment on the xy plane
    """
    points = []
    for i in reversed(range(nb_vertices)):
        angle = (math.pi*2) * i / nb_vertices 
        points.append(np.array([-(radius * math.sin(angle) + radius), -(radius * math.cos(angle)), 0]))
    return points

def get_rectangle_segment(width, height, nb_vertices):
    """Get a segment on the xy plane of a rectangle

    Args:
        width (float): the width of the rectangle
        height (float): the height of the rectangle
        nb_vertices (int): number of vertices that will define the segment

    Returns:
        list((int, int, int)): the vertices that represent the segment on the xy plane
    """
    length = 2 * width + 2 * height
    points = []
    current_state = -1
    for i in range(nb_vertices): 
        distance = length * i / nb_vertices
        if distance < height:
            if current_state == -1:
                points.append(np.array([0, width/2, 0]))
                current_state += 1
            else:
                points.append(np.array([-distance, width / 2, 0]))
        elif distance < height + width:
            if current_state == 0:
                points.append(np.array([-height, width/2, 0]))
                current_state += 1
            else:
                points.append(np.array([-height, -(distance - height - width / 2), 0]))
        elif distance < 2 * height + width:
            if current_state == 1:
                points.append(np.array([-height, -width/2, 0]))
                current_state += 1
            else:
                points.append(np.array([-(2 * height + width - distance), -width / 2, 0]))
        else:
            if current_state == 2:
                points.append(np.array([0, -width/2, 0]))
                current_state += 1
            else:
                points.append(np.array([0, -(2 * height + 3 * width / 2 - distance), 0]))
    return points

def get_elliptic_segment(width, height, nb_vertices):
    """Get a segment on the xy plane of an elliptic curve

    Args:
        width (float): the width of the rectangle
        height (float): the height of the rectangle
        nb_vertices (int): number of vertices that will define the segment

    Returns:
        list((int, int, int)): the vertices that represent the segment on the xy plane
    """
    a = width / 2
    b = height
    ellipse_length = 2 * integrate.quad(lambda t: math.sqrt(a**2 * math.cos(t)**2 + b**2 * math.sin(t)**2), 0, np.pi / 2)[0]
    nb_vertices_ellipse = int((ellipse_length * nb_vertices) / (width + ellipse_length))
    nb_vertices_width = nb_vertices - nb_vertices_ellipse
    points = []
    for i in range(nb_vertices_width):
        distance = width * i / nb_vertices_width
        points.append(np.array([0, width / 2 - distance, 0]))
    for t in np.linspace(-np.pi / 2, np.pi / 2, nb_vertices_ellipse):
        points.append(np.array([-b * math.cos(t), -a * math.sin(t), 0]))
    return points

def _project_points(normal, bottom, xy_points):
    ANGLE_EPSILON = 0.01
    # axis vectors
    z = np.array([0, 0, 1])
    x = np.array([1, 0, 0])

    u = normalize(normal)
    axis = np.cross(u, z)
    angle = math.acos(-np.dot(u, z))
    verts = []
    if angle > ANGLE_EPSILON:
        to_plane_rotation = _rotation_matrix(normalize(axis), angle)
        diff_axis = to_plane_rotation.dot(z)
        diff_axis[2] = 0
        angle2 = math.acos(np.dot(normalize(diff_axis), x))
        cond = angle2 > ANGLE_EPSILON
        rotation_matrix = None
        if normal[1] < 0:
            angle2 *= -1
            cond = -angle2 > ANGLE_EPSILON
        if cond:
            in_plane_rotation = _rotation_matrix(u, angle2)
            rotation_matrix = np.matmul(in_plane_rotation, to_plane_rotation)
        else:
            rotation_matrix = to_plane_rotation
        for p in xy_points:
            verts.append((rotation_matrix.dot(p) + bottom).tolist())
    else:
        for p in xy_points:
            verts.append((p + bottom).tolist())
    return verts

def _rotation_matrix(ax, t):
    x, y, z = ax
    return np.array([
        [math.cos(t) + x**2 * (1 - math.cos(t)), x * y * (1 - math.cos(t)) - z * math.sin(t), x * z * (1 - math.cos(t)) + y * math.sin(t)],
        [y * x * (1 - math.cos(t)) + z * math.sin(t), math.cos(t) + y**2 * (1 - math.cos(t)), y * z * (1 - math.cos(t)) - x * math.sin(t)],
        [z * x * (1 - math.cos(t)) - y * math.sin(t), z * y * (1 - math.cos(t)) + x * math.sin(t), math.cos(t) + z**2 * (1 - math.cos(t))]
    ])

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


def normalize(v):
    return v / np.linalg.norm(v)
