# -*- coding: utf-8 -*-
#
# This file is part of gmlib. It is free software.
# You can redistribute it and/or modify it under the terms of the GNU Affero General Public License version 3.
#


import os
import numpy as np
import myxmltools as mx
import topography_reader
import xml.etree.ElementTree as ET

from geomodeller_data import (NotImplemented, GradientData, PotentialData,
                              FaultData, SeriesData, Pile, CovarianceModel)

def read_box(xml_root, ns):
    extent = xml_root.find('geo:Extent3DOfProject', ns)
    extentbox = extent.find('geo:ExtentBox3D', ns)
    extent3D = extentbox.find('geo:Extent3D', ns)
    xy = extent3D.find('geo:ExtentXY', ns)
    limits = {}
    for s, val in xy.items():
        limits[s] = float(val)
    z = extent3D.find('geo:ExtentZ', ns)
    for s, val in z.items():
        limits[s] = float(val)
    return limits

def read_formation_colors(xml_root, ns):
    formations = xml_root.find('geo:Formations', ns)
    colors = {}
    if formations:
        for formation in formations.findall('geo:Formation', ns):
            formation_name = formation.attrib['Name']
            graphic = formation.find('geo:Graphic', ns)
            if graphic:
                shading = graphic.find('geo:ColorShading', ns)
                color = tuple(int(shading.attrib[name])/255. # convert to float RGB
                            for name in ('Red', 'Green', 'Blue'))
                colors[formation_name] = color
    return colors

def read_topography_info(xml_root, ns):
    sections = xml_root.find('geo:Sections', ns)
    topographies = []
    if sections:
        for section in sections.findall('geo:Section', ns):
            if 'IsTopography' in section.keys():
                if section.attrib['IsTopography']=='true':
                    shape = section.find('geo:Shape3DOfSection', ns)
                    topographies.append((section.attrib['Name'],
                                         shape.attrib['FileName']))
    assert len(topographies)==1
    return topographies[0]

def read_data(xml_root, ns):
    data = xml_root.findall('geo:Data', ns)
    return [d.attrib['Name'] for d in data]

def read_potential_data(xml_root, ns):
    field = xml_root.find('geo:PotentialField', ns)
    if field is None:
        return None
    glocs = []
    gvals = []
    pts = []
    interfaces = []
    covariance_model = CovarianceModel(field.find('geo:covariance', ns))
    constraints = field.find('geo:Constraints', ns)
    if constraints:
        if any(constraint.attrib['value']!='0' for constraint in constraints):
            mess = 'inequality constraints are not handled for now'
            raise NotImplemented(mess)
    gradients = field.find('geo:Gradients', ns)
    if gradients is not None:
        for gradient in gradients.iterfind('geo:Gradient', ns):
            V = tuple(np.double(gradient.attrib[s]) for s in ('Gx', 'Gy', 'Gz'))
            gvals.append(V)
            P = tuple(np.double(gradient.attrib[s]) for s in ('XGr', 'YGr', 'ZGr'))
            glocs.append(P)
    points = field.find('geo:Points', ns)
    if points is not None:
        for point in points:
            P = tuple(np.double(point.find('gml:' + s, ns).text)
                                                        for s in ('X', 'Y', 'Z'))
            pts.append(P)
    interface_points = field.find('geo:InterfacePoints', ns)
    for interface in interface_points:
        attr_as_int = lambda s: int(interface.attrib[s])
        interfaces.append((attr_as_int('pnt'), attr_as_int('npnt')))
    array_of_double = lambda v: np.array(v, dtype=np.double)
    potdata = PotentialData()
    potdata.covariance_model = covariance_model
    potdata.gradients = GradientData(array_of_double(glocs),
                                     array_of_double(gvals))
    pts = array_of_double(pts)
    potdata.interfaces = [pts[start:start+nb] for start, nb in interfaces]
    return potdata

def read_faults_data(root, ns):
    faults_data = {}
    faults = root.find('geo:Faults', ns)
    if faults:
        for fault in faults.findall('geo:Fault', ns):
            data = FaultData(fault.attrib['Name'])
            geology = fault.find('geo:FaultGeology', ns).attrib
            if int(geology['FAULT_TYPE'])==1:
                data.lateral_extent = np.double(geology['LATERAL_EXTENT'])
                data.vertical_extent = np.double(geology['VERTICAL_EXTENT'])
                data.influence_radius = np.double(geology['RADIUS_OF_INFLUENCE'])
            for other in fault.iterfind('geo:StopsOnFault', ns):
                data.stops_on.append(other.attrib['Name'])
            faults_data[data.name] = data
        model = root.find('geo:GeologicalModel', ns)
        modelfaults = model.find('geo:ModelFaults', ns)
        if modelfaults:
            faultpotentials = modelfaults.findall('geo:PotentialFault', ns)
            for fault in faultpotentials:
                data = read_data(fault, ns)
                assert len(data)==1
                name = data[0]
                potdata = read_potential_data(fault, ns)
                faults_data[name].potential_data = potdata
    deleted_faults = [name for name, data in faults_data.items()
                                                if data.potential_data is None]
    for name in deleted_faults:
        print('WARNING: Fault', name,
              'has no potential data and is removed from project!')
        del faults_data[name]
    return faults_data

def read_pile(root, ns):
    model = root.find('geo:GeologicalModel', ns)
    column = model.find('geo:ProjectStratigraphicColumn', ns)
 #   modelseries = model.find('geo:ModelStratigraphicColumn', ns)
 #   for serie in modelseries:
 #       modelseries.find('geo:Data',ns)
 #       name = serie.attrib['Name']
 #       print (name)

    reference = {'true': 'base', 'false':'top'}[column.attrib['IsBase']]
    pile = Pile(reference)
    all_series = []
    for serie in column:
        # read data
        name = serie.attrib['name']
        serie_data = SeriesData(name)
        serie_data.relation = {'1': 'onlap', '2': 'erode'}[serie.attrib['relation']]
        serie_data.formations = read_data(serie, ns)
        all_influencing_faults = serie.findall('geo:InfluencedByFault', ns)
        influenced_by_fault = [f.attrib['Name'] for f in all_influencing_faults]
        if influenced_by_fault:
            serie_data.influenced_by_fault = influenced_by_fault
        serie_data.potential_data = read_potential_data(serie, ns)
        assert (serie_data.potential_data is None or
         len(serie_data.potential_data.interfaces)==len(serie_data.formations))
        all_series.append(serie_data)
    pile.all_series = all_series
    return pile

def extract_project_data(filepath):
    if os.path.islink(filepath):
        filepath = os.readlink(filepath)
    filepath = os.path.realpath(filepath)
    tree, ns = mx.parse_and_get_ns(filepath)
    root = tree.getroot()
    ns['geo'] = mx.extract_namespace(ns['geo'])
    ns['gml'] = mx.extract_namespace(ns['gml'])
    box = read_box(root, ns)
    faults_data = read_faults_data(root, ns)
    pile = read_pile(root, ns)
    name, filename = read_topography_info(root, ns)
    project_directory = os.path.split(filepath)[0]
    topography = topography_reader.sec_extract(os.path.join(project_directory, filename))
    formation_colors = read_formation_colors(root, ns)
    return box, pile, faults_data, topography, formation_colors

def extract_project_data_noTopography(filepath):
    if os.path.islink(filepath):
        filepath = os.readlink(filepath)
    filepath = os.path.realpath(filepath)
    tree, ns = mx.parse_and_get_ns(filepath)
    root = tree.getroot()
    ns['geo'] = mx.extract_namespace(ns['geo'])
    ns['gml'] = mx.extract_namespace(ns['gml'])
    box = read_box(root, ns)
    faults_data = read_faults_data(root, ns)
    pile = read_pile(root, ns)
    #name, filename = read_topography_info(root, ns)
    project_directory = os.path.split(filepath)[0]
    formation_colors = read_formation_colors(root, ns)
    return box, pile, faults_data, formation_colors
    
def make_center(aSerie,xmin,xmax,ymin,ymax,zmin,zmax):
    cx = (xmin+xmax)/2
    cy = (ymin+ymax)/2
    cz = (zmin+zmax)/2
    Themax = xmax - xmin
    pts = aSerie.potential_data.interfaces.points
    #interfaces
    for p in pts:
        x = 0.5 + (p[0] -cx)/Themax
        y = 0.5 + (p[1] -cy)/Themax
        z = 0.5 + (p[2] -cz)/Themax
        p[0] = x
        p[1] = y
        p[2] = z

    gpts = aSerie.potential_data.gradients.locations
    #gradients
    for p in gpts:
        x = 0.5 + (p[0] -cx)/Themax
        y = 0.5 + (p[1] -cy)/Themax
        z = 0.5 + (p[2] -cz)/Themax
        p[0] = x
        p[1] = y
        p[2] = z

    cov = aSerie.potential_data.covariance_model
    cov.range = cov.range/Themax

if __name__=='__main__':
    import sys
    from matplotlib import pyplot as plt
    if len(sys.argv)>1:
        filename = sys.argv[1]
        if os.path.exists(filename):
            assert not os.path.islink(filename)
            data = extract_project_data(filename)
            box, pile, faults_data, topography, fcolors = data
            nx, ny = 200, 200
            xmin, xmax = box['Xmin'], box['Xmax']
            ymin, ymax = box['Ymin'], box['Ymax']
            xy = np.meshgrid(np.linspace(xmin, xmax, nx),
                             np.linspace(ymin, ymax, ny), indexing='ij')
            x, y = (a.ravel() for a in xy)
            z = np.array([topography.evaluate_z((xi, yi)) for xi, yi in zip(x, y)])
            z.shape = nx, ny
            plt.gca().set_aspect('equal')
            box = (xmin, xmax, ymin, ymax)
            plt.imshow(np.transpose(z)[::-1], extent=box)
