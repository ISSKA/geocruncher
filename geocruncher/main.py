# -*- coding: utf-8 -*-

import sys
import numpy as np
#from .GeologicalModel3D import GeologicalModel

def printStderr(msg):
    sys.stderr.write(msg)
    sys.stderr.flush()

def main():
    while True:
        cmd = sys.stdin.readline().strip().split(" ")
        if cmd[0] == 'SetProjectData':
            xmlFile = cmd[1]
            printStderr('Reading project XML data from ' + xmlFile + '\n')
            # TODO
        elif cmd[0] == "SetProjectDEM":
            demFile = cmd[1]
            printStderr('Setting DEM file to ' + demFile + '\n')
            # TODO
        elif cmd[0] == "ComputeImplicitModel":
            printStderr('Computing implicit model ...')
            # TODO
        elif cmd[0] == "QueryBoundariesCrossSection":
            printStderr("Query boundaries cross section ...")
        elif cmd[0] == "Shutdown":
            printStderr("Shutting down ...")
            return
        else:
            printStderr('Invalid command\n')

#    lines = '';
#    for line in sys.stdin:    
#        lines += line;

#    model = GeologicalModel.from_json(lines)

    # stolen from test-GeologicalModel3D
#    box = model.getbox()
#    diagonal = np.array([box.xmax, box.ymax])
#    origin = np.array([box.xmin, box.ymin])
#    diagonal-= origin
#    zmin, zmax = box.zmin, box.zmax

#    nu, nz = 100, 100
#    z, u = np.meshgrid(np.linspace(zmin, zmax, nz),
#                       np.linspace(0, 1, nu))
#    pts = np.hstack([origin + np.reshape(u, (-1, 1)) * diagonal,
#                     np.reshape(z, (-1, 1))])
#    ranks = np.array([model.rank(p) for p in pts])
#    print(ranks[0], ranks[1], ranks[2], ranks[3])


if __name__ == '__main__':
    main()

