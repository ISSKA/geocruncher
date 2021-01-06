import numpy as np
import scipy.integrate as integrate
import math

from sympy.parsing.sympy_parser import parse_expr
from sympy import diff, symbols, sqrt
from sympy.utilities.lambdify import lambdify

def computeBezierCoefficients(points):
    """
    Compute Bezier interpolation coefficients

    Coefficients can later be user to find interpolation between two successive points 
    using Bézier cubic curves, see: https://en.wikipedia.org/wiki/B%C3%A9zier_curve#Cubic_B%C3%A9zier_curves,
    where P0 = points[i], P1 = A[i], P2 = B[i], P3 = points[i+1]

    Based on https://towardsdatascience.com/b%C3%A9zier-interpolation-8033e9a262c2
    """
    n = len(points) - 1
    C = 4 * np.identity(n)
    np.fill_diagonal(C[1:], 1)
    np.fill_diagonal(C[:, 1:], 1)
    C[0, 0] = 2
    C[n - 1, n - 1] = 7
    C[n - 1, n - 2] = 2

    P = [2 * (2 * points[i] + points[i + 1]) for i in range(n)]
    P[0] = points[0] + 2 * points[1]
    P[n - 1] = 8 * points[n - 1] + points[n]

    A = np.linalg.solve(C, P)
    B = [0] * n
    for i in range(n - 1):
        B[i] = 2 * points[i + 1] - A[i + 1]
    B[n - 1] = (A[n - 1] + points[n]) / 2

    return A, B

def computeArcLength(fx, fy, fz, start, end):
    t = symbols("t")
    dfx = diff(parse_expr(fx.replace("^", "**")), t)
    dfy = diff(parse_expr(fy.replace("^", "**")), t)
    dfz = diff(parse_expr(fz.replace("^", "**")), t)
    func = lambdify(t, sqrt(dfx**2 + dfy**2 + dfz**2))
    return round(integrate.quad(func, start, end)[0], 2)