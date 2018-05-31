# -*- coding: utf-8 -*-
#
# This file is part of gmlib. It is free software.
# You can redistribute it and/or modify it under the terms of the GNU Affero General Public License version 3.
#

from collections import namedtuple
import json
import numpy as np
import pypotential3D as pypotential
from gmlib import topography_reader

Intersection = namedtuple('Intersection', ['point', 'rank'])
Box =  namedtuple('Box', ['xmin', 'ymin', 'zmin', 'xmax', 'ymax', 'zmax'])

GradientData = namedtuple('GradientData', ['locations', 'values'])
class PotentialData:
    @classmethod
    def from_dict(cls, dct):
        # Interface stuff memo
        # input: 'interfaces': [{'points': [{'x': 0.0, 'y': 0.0, 'z': 0.0}, {'x': 1.0, 'y': 1.0, 'z': 1.0}]}],
        # output: [array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])]
        
        def vec_to_list(vec):
            return [vec['x'], vec['y'], vec['z']]

        # The original code seems to assume that the points are a numpy array, but the list of points as a normal list/array
        def points_to_array(points):
            return np.array([vec_to_list(v) for v in points], dtype=np.double)

        def gradiant_data(gds):
            locations = []
            values = []
            for gd in gds:
                locations += gd['position']['x'], gd['position']['y'], gd['position']['z']
                values += gd['value']['x'], gd['value']['y'], gd['value']['z']
                
            return GradientData(
                np.array(locations, dtype=np.double),
                np.array(values, dtype=np.double)
            )
        
        return PotentialData(
            CovarianceModel.from_dict(dct['covarianceModel']),
            gradiant_data(dct['gradients']),
            [points_to_array(x['points']) for x in dct['interfaces']]
        )

    def __init__(self, covariance_model, gradients, interfaces):
        self.covariance_model = covariance_model
        self.gradients = gradients
        self.interfaces = interfaces

class SeriesData:
    @classmethod
    def from_dict(cls, dct):
        res = SeriesData(dct['name'])
        res.formations = dct['formations']
        res.relation = list(dct['relation'].keys())[0].lower()
        res.influenced_by_fault = dct['influencedByFaults']
        res.potential_data = PotentialData.from_dict(dct['potentialData'])
        return res

    def __init__(self, name):
        self.name = name
        self.formations = None
        self.relation = None
        self.influenced_by_fault = None
        self.potential_data = None

class Pile:
    @classmethod
    def from_dict(cls, dct):
        res = SeriesData(list(dct['reference'].keys())[0].lower())
        res.all_series = [SeriesData.from_dict(x) for x in dct['series']]
        return res
        
    def __init__(self, reference):
        assert reference=='top' or reference=='base'
        self.reference = reference
        self.all_series = None

class CovarianceModel:
    @classmethod
    def from_dict(cls, dct):
        res = CovarianceModel()
        res.anisotropy_angles = np.array([dct['anisotropy']['a1'], dct['anisotropy']['a2'], dct['anisotropy']['a3']])
        res.anisotropy_values = np.array([dct['anisotropy']['v1'], dct['anisotropy']['v2'], dct['anisotropy']['v3']])
        res.covariance_model = list(dct['covarianceModel'].keys())[0].lower()
        if res.covariance_model == 'cubic':
            res.covariance_model = 'cubique' # -_-'

        res.drift_order = dct['degreeDrift']
        res.isotropic = dct['isIsotropic']
        res.gradient_nugget = dct['nuggetGradient']
        res.gradient_variance = dct['gradient']
        res.range = dct['range']
        res.potential_nugget = dct['nuggetPotential']
        res.tangent_variance = dct['tangentVariance']
        return res

def covariance_data(potdata):
    covmodel = potdata.covariance_model
    return pypotential.CovarianceData(covmodel.gradient_variance,
                                  covmodel.range)

def gradient_data(potdata):
    graddata = potdata.gradients
    return pypotential.gradient_data(graddata.locations,
                                graddata.values)

def interface_data(potdata):
    return pypotential.interface_data(potdata.interfaces)

def drift_basis(potdata):
    drift_order = potdata.covariance_model.drift_order
    return pypotential.drift_basis(drift_order)

# FIXME this should be set elsewhere
# Version with np.array here is suboptimal
def point_between(p1, p2, field, v, precision=0.01):
    squared_precision = precision**2
#    Point = pypotential.Point
#    p1 = pypotential.Point(p1)
#    p2 = pypotential.Point(p2)
    p1 = np.asarray(p1, dtype='d')
    p2 = np.asarray(p2, dtype='d')
    assert len(p1.shape)==1 and len(p2.shape)==1
    #print('-> point between', p1, p2)
    v1, v2 = field(p1), field(p2)
    #print('field values:', v1, v2)
    # FIXME: minimum can't be found (might scan between potentials)
    if (v - v1) * (v - v2) > 0:
      return None
#    previous = Point(p1) # copy is mandatory here
    previous = np.copy(p1) # copy is mandatory here
    while True:
      # (v - v1)/(v2 - v1)<1 so p is in [p1, p2] and we have convergence
      #print('-> TEST:', p1)
      #print('-> TEST:', p2-p1)
      p = p1 + float((v - v1)/(v2 - v1)) * (p2 - p1)
#      squared_length = (p - previous).squared_length
      squared_length = np.sum((p-previous)**2)
      if (squared_length < squared_precision):
         #print('-> FOUND', p)
         return p
      vp = field(p)
      #print('field value:', vp)
#      previous = Point(p) # copy is mandatory here
      previous = np.copy(p) # copy is mandatory here
      if ((v - vp) * (v - v2) <= 0) :
         #Look for between vp and v2
         v1 = vp
         p1 = p
      elif ((v - vp)*(v - v1) <= 0):
         # Look for between v1 and vp
         v2 = vp;
         p2 = p
      else:
         assert False
         return None
    return None

def distance(p1,p2):
    x = p1[0]-p2[0]
    y = p1[1]-p2[1]
    z = p1[2]-p2[2]
    dist = np.sqrt(x**2 + y**2 +z**2)
    return dist

class GeologicalModel:

    @classmethod
    def from_geomodeller_project(cls, filename):
        print('Loading model from:', filename)
        box, pile, faults_data, topography = geomodeller_project.extract_project_data(filename)
        return cls(box, pile, faults_data, topography)

    @classmethod
    def from_json(cls, json_str):
        dct = json.loads(json_str)
        box = {}
        box['Xmin'] = dct['extent']['xMin']
        box['Xmax'] = dct['extent']['xMax']
        box['Ymin'] = dct['extent']['yMin']
        box['Ymax'] = dct['extent']['yMax']
        box['Zmin'] = dct['extent']['zMin']
        box['Zmax'] = dct['extent']['zMax']

        pile = Pile.from_dict(dct['pile'])
        faults_data = {} # TODO: add support for fault data
        topography = topography_reader.sec_extract(dct['topography'])
        
        return GeologicalModel(box, pile, faults_data, topography)

    def __init__(self, box, pile, faults_data, topography):
        self.box = box
        self.pile = pile
        self.faults_data = faults_data
        self.topography = topography
        faults = {}
        fault_drifts = {}

        for name, data in faults_data.items():
            potdata = data.potential_data
            field = pypotential.potential_field(
                   covariance_data(potdata),
                   gradient_data(potdata),
                   interface_data(potdata),
                   drift_basis(potdata))
            fault = pypotential.Fault(field)
            faults[name] = fault
            fault_drifts[name] = pypotential.make_drift(fault)

        fields=[]
        values = []
        relations = []
        for serie in pile.all_series:
            potdata = serie.potential_data
            if potdata:
               drifts = drift_basis(potdata)
               if serie.influenced_by_fault:
                   for name in serie.influenced_by_fault:
                       drifts.append(fault_drifts[name])

               field = pypotential.potential_field(
                         covariance_data(potdata),
                         gradient_data(potdata),
                         interface_data(potdata),
                         drifts)

               for interface in potdata.interfaces:
                  values.append(np.mean(field(interface)))
                  fields.append(field)
                  relations.append(serie.relation)
        self.fields = fields
        self.values = values
        self.relations = relations
        self.faults = faults
        self.fault_drifts = fault_drifts


    def nbformations(self):
        n = len(self.fields) + 1
        return n

    def nbcontacts(self):
        n = len(self.fields)
        return n

    def getbox(self):
        xmin, xmax = (self.box['Xmin'], self.box['Xmax'])
        ymin, ymax = (self.box['Ymin'], self.box['Ymax'])
        zmin, zmax = (self.box['Zmin'], self.box['Zmax'])
        return Box(xmin, ymin, zmin, xmax, ymax, zmax)

    def domain(self, x, y, z):
        return self.rank((x, y, z))

    def rank(self, p):
        if self.topography(p)>0:
           return 0
        n = len(self.fields)
        j1 = 0
        j2 = n
        # parcourir les erode decroissants
        erosion_surfaces = [i for i in range(n) if self.relations[i]=='erode']
        for i in reversed(erosion_surfaces):
           field = self.fields[i]
           vp = field(p)
           vi = self.values[i]
           if (vp > vi):
               j1 = i
               break
           j2 = i
        # parcourir les onlap croissants dans l'intervavlle j1 j2
        rank = j1
        assert j1==0 or (self.relations[j1]=='erode' and self.fields[j1](p)>self.values[j1])
        rank = j1
        for i in range(j1, j2):
           field = self.fields[i]
           vp = field(p)
           vi = self.values[i]
           # when i=j1>0 we are sure that vp<vi (previous test)
           if (vp < vi):
               break
           rank+= 1
        # print ("Which domain:", p[0], p[1], p[2], rank+1)
        return rank+1

    def intersect(self, p1, p2):
        #print('-> intersect', p1, p2)
        rank = 0
        p = point_between(p1, p2, self.topography, 0)
        if p is not None:
           return Intersection(p, 0)
        #print('            no topo')
        found = False
        # test fault potential fields
        for fi, fault_name in enumerate(self.fault_drifts):
           drift = self.fault_drifts[fault_name]
           p = point_between(p1, p2, drift, 0)
           if p is not None:
               return Intersection(p, fi + 1)
        # test potential fields
        #print('            no faults')
        n = len(self.fields)
        for i in range(n):
         p = point_between(p1, p2, self.fields[i], self.values[i])
         if p is not None:
           if self.is_valid(p, i):
               #print('            Found:', n, p, 'shape:', p.shape)
               return Intersection(p, rank + 1)
        #print('            Nothing!')
        return None

    def is_valid(self, p, rank):
        n = len(self.fields)
        for i in range(rank + 1,n):
           Ri = self.relations[i]
           if (Ri == 'erode'):
               field = self.fields[i]
               vp = field(p)
               vi = self.values[i]
               if (vp > vi):
                  return False
        R = self.relations[rank]
        if (R == 'onlap'):
           for i in reversed(range(rank)):
               field = self.fields[i]
               vp = field(p)
               vi = self.values[i]
               if (vp < vi):
                  return False
               Ri = self.relations[i]
               if (Ri == 'erode') :
                  break
        return True
