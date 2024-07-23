"""
    Read code adapted from MeshIO
    Sadly, MeshIO usese `np.fromfile`, which makes it impossible to read a mesh from an in-memory buffer
    The code is therefore modified to not use BufferIOs
"""

import numpy as np

from meshio._exceptions import ReadError
from meshio._mesh import CellBlock, Mesh


def read_off(string: str) -> Mesh:
    # assert that the first line reads `OFF`
    lines = string.splitlines()

    if lines[0].strip() != 'OFF':
        raise ReadError("Expected the first line to be `OFF`.")

    # fast forward to the next significant line
    i = 1
    while True:
        line = lines[i].strip()
        if line and line[0] != '#':
            break
        i += 1

    # This next line contains:
    # <number of vertices> <number of faces> <number of edges>
    num_verts, num_faces, _ = lines[i].split(" ")
    num_verts = int(num_verts)
    num_faces = int(num_faces)

    vert_lines_end = i + 1 + num_verts
    vert_lines = lines[i + 1:vert_lines_end]

    verts = np.array([[float(x) for x in line.split(" ")]
                     for line in vert_lines], dtype=float)

    face_lines = lines[vert_lines_end:vert_lines_end + num_faces]

    faces = np.array([[int(x) for x in line.split(" ")]
                      for line in face_lines], dtype=int)
    if not np.all(faces[:, 0] == 3):
        raise ReadError("Can only read triangular faces")
    cells = [CellBlock("triangle", faces[:, 1:])]

    return Mesh(verts, cells)


def generate_off(verts, faces, precision=3):
    """Generates a valid OFF string from the given verts and faces.

    Parameters:
        verts: (V, 3) array
            Spatial coordinates for V unique mesh vertices. Coordinate order
            must be (x, y, z).
        faces: (F, N) array
            Define F unique faces of N size via referencing vertex indices from ``verts``.
        precision: int
            How many decimals to keep when writing vertex position. Defaults to 3.

    Returns:
        str: A valid OFF string.
    """
    # Implementation reference: https://en.wikipedia.org/wiki/OFF_(file_format)#Composition
    num_verts = len(verts)
    num_faces = len(faces)
    v = '\n'.join([' '.join([str(round(float(position), precision))
                             for position in vertex]) for vertex in verts])
    f = '\n'.join([' '.join([str(len(face)), *(str(int(index))
                                               for index in face)]) for face in faces])

    return f"OFF\n{num_verts} {num_faces} 0\n{v}\n{f}\n"
