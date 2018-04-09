# -*- coding: utf-8 -*-
#
# This file is part of gmlib. It is free software.
# You can redistribute it and/or modify it under the terms of the GNU Affero General Public License version 3.
#

import os
import numpy as np
from io import StringIO

class ImplicitHorizontalPlane:

    def __init__(self, zvalue):
        self.z = float(zvalue)

    def evaluate_z(self, P):
        return self.z

    def __call__(self, P):
        return P[2] - self.z

class ImplicitDTM:

    def __init__(self, origin, steps, zmap):
        self.origin = np.array(origin, dtype='d')
        assert self.origin.shape==(2,)
        self.steps = np.array(steps, copy=True, dtype='d')
        self.invsteps = np.array([(1./ds) for ds in steps], dtype='d')
        assert self.invsteps.shape==(2,)
        self.z = np.array(zmap, copy=True, dtype='d')

    def evaluate_z(self, P):
        P = np.asarray(P, dtype='d')
        DX = P - self.origin
        DX*= self.invsteps
        DX[DX<0] = 0
        i, j = DX
        zmap = self.z
        nx, ny = zmap.shape
        if i>nx-1:
            i = nx-1
        if j>ny-1:
            j = ny-1
        ii, ij = int(i), int(j)
        i-=ii
        j-=ij
        if j==0:
            if i==0:
                return zmap[ii, ij]
            else:
                zl, zr = zmap[ii:ii+2, ij]
                return (1-i)*zl + i*zr
        else:
            if i==0:
                zl, zr = zmap[ii, ij:ij+2]
                return (1-j)*zl + j*zr
            zl, zr = zmap[ii, ij:ij+2]
            z = (1-i)*(1-j)*zl
            z+= (1-i)*j*zr
            zl, zr = zmap[ii+1, ij:ij+2]
            z+= i*(1-j)*zl
            z+= i*j*zr
            return z
        assert(False)

    def __call__(self, P):
        return P[2] - self.evaluate_z(P[:2])

def extract_plane(f):
    # we already have read the code character (first character on the line)
    l = f.readline().strip().split()
    point = tuple(float(s) for s in l[:3])
    normal = tuple(float(s) for s in l[3:6])
#    ux = tuple(float(s) for s in l[6:9])
#    uy = tuple(float(s) for s in l[9:]:)
    return point, normal

def extract_mnt(f, decimals=8):
    # we already have read the code character (first character on the line)
    l = f.readline().strip().split()
    nx, ny = (int(s) for s in l[6:8])
    assert int(l[8]) + 2 == nx and int(l[9]) + 2 == ny
    zmap = []
    line = l[10:]
    while line:
        zmap.append(np.array([float(s) for s in line]))
        line = f.readline().strip().split()
    zmap = np.array(zmap)
    x, y, z = (zmap[:, k::3] for k in range(3))
    def clean(a):
        a = np.delete(a, [1, nx-2], axis=0)
        a = np.delete(a, [1, ny-2], axis=1)
        return a
    x, y, z = (clean(a) for a in (x, y, z))
    dx = np.unique(np.round(x[1:,:] - x[:-1, :], decimals))
    assert dx.shape==(1,)
    dy = np.unique(np.round(y[:,1:] - y[:, :-1], decimals))
    assert dy.shape==(1,)
    xmin, ymin = x.min(), y.min()
    return (xmin, ymin), (float(dx), float(dy)), z

def sec_extract(sec):
    # Original code uses file, but for minimum changing we use StringIO
    f = StringIO(sec)
    line = f.readline()
    while not line.startswith('Surfaces'):
        line = f.readline()
    code = int(f.read(1))
    if code==1:
        point, normal = extract_plane(f)
        assert normal[0] == 0 and normal[1]==0
        return ImplicitHorizontalPlane(point[2])
    elif code==9:
        return ImplicitDTM(*extract_mnt(f))
