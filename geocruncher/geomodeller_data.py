# -*- coding: utf-8 -*-
"""
Created on Mon Apr 16 09:58:12 2018

@author: lopez
"""

from collections import namedtuple
import numpy as np

class NotImplemented(Exception):
    pass

GradientData = namedtuple('GradientData', ['locations', 'values'])

class PotentialData:
    pass

class FaultData:
    def __init__(self, name):
        self.name = name
        self.infinite = True
        self.influence_radius = None
        self.lateral_extent = None
        self.vertical_extent = None
        self.stops_on = []
        self.potential_data = None

class SeriesData:
    def __init__(self, name):
        self.name = name
        self.formations = None
        self.relation = None
        self.influenced_by_fault = None
        self.potential_data = None

class Pile:
    def __init__(self, reference):
        assert reference=='top' or reference=='base'
        self.reference = reference
        self.all_series = None
    def __repr__(self):
        lines = []
        lines.append('pile (reference ' + self.reference + ')')
        for serie in self.all_series[::-1]:
            lines.append(serie.name + ' (' + serie.relation + ') ')
            for formation in serie.formations[::-1]:
                lines.append(' '*2 + formation)
        return '\n'.join(lines)

class CovarianceModel:
    def __init__(self, xml_node):
        d = xml_node.attrib # attributes dictionnary
        self.anisotropy_angles = np.array(
            [np.double(d[s]) for s in ['anisotropyA1', 'anisotropyA2', 'anisotropyA3']]
        )
        self.anisotropy_values = np.array(
            [np.double(d[s]) for s in ['anisotropyV1', 'anisotropyV2', 'anisotropyV3']]
        )
        # Type de covariance (cf. Potentiel.cdl)
        self.covariance_model = ({
            0: 'gauss', 1:'cubique', 2:'h4log', 3:'h3', 4:'penta'
        }[int(d['covarianceModel'])])
        self.drift_order = int(d['degreDrift'])
        self.isotropic = {'true':True, 'false':False}[d['isotropic']]
        self.gradient_nugget = float(d['nuggetGradient'])
        self.gradient_variance = float(d['gradient'])
        self.range = float(d['range'])
        self.potential_nugget = float(d['nuggetPotentiel'])
        self.tangent_variance = float(d['tangentVariance'])
