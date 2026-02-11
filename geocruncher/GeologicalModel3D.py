#
# This file is part of gmlib. It is free software.
# You can redistribute it and/or modify it under the terms of the GNU Affero General Public License version 3.
#

import numpy as np

from forgeo.gmlib.GeologicalModel3D import (
    Intersection,
    PileInfo,
    Box,
    CRSInfo,
    SeriesInfo,
)
from forgeo.gmlib import geomodeller_project
from forgeo.gmlib import pypotential3D as pypotential
from forgeo.gmlib.common import CovarianceData
from forgeo.gmlib.geomodeller_data import GradientData
from forgeo.gmlib.pypotential3D import (
    ConstantElevationSurface,
    ElevationRaster,
    ImplicitTopography,
    Polyline,
    VerticalSection,
)
from forgeo.gmlib.topography_reader import ImplicitDTM, ImplicitHorizontalPlane
from forgeo.gmlib.utils.tools import BBox3

scalardt = pypotential.scalar_type()


# FIMXE: to be put elsewhere
def image_ratio(section, nu):
    assert section.umax > section.umin
    nv = int(((section.vmax - section.vmin) / (section.umax - section.umin)) * nu)
    assert (
        nv > 0
    ), f"z ratio is to small: {(section.vmax - section.vmin) / (section.umax - section.umin)}"
    return nu, nv


def covariance_data(potdata):
    covmodel = potdata.covariance_model
    return CovarianceData(
        covmodel.gradient_variance,
        covmodel.range,
        covmodel.gradient_nugget,
        covmodel.potential_nugget,
    )


def gradient_data(potdata):
    graddata = potdata.gradients
    return pypotential.gradient_data(graddata.locations, graddata.values)


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
    p1 = np.asarray(p1, dtype=scalardt)
    p2 = np.asarray(p2, dtype=scalardt)
    assert len(p1.shape) == 1
    assert len(p2.shape) == 1
    # print('-> point between', p1, p2)
    v1, v2 = field(p1), field(p2)
    if v1 == v:
        return p1
    if v2 == v:
        return p2
    # print('field values:', v1, v2, 'looking for', v)
    # FIXME: minimum can't be found (might scan between potentials)
    if (v - v1) * (v - v2) > 0:
        return None
    #    previous = Point(p1) # copy is mandatory here
    previous = np.copy(p1)  # copy is mandatory here
    while True:
        # (v - v1)/(v2 - v1)<1 so p is in [p1, p2] and we have convergence
        # print('-> TEST:', p1)
        # print('-> TEST:', v1, v2, p2- p1)
        # if v1==v:
        # return p1
        # if v2==v:
        # return p2
        # if v1==v2==v:
        # return None
        p = p1 + float((v - v1) / (v2 - v1)) * (p2 - p1)
        #      squared_length = (p - previous).squared_length
        squared_length = np.sum((p - previous) ** 2)
        if squared_length < squared_precision:
            # print('-> FOUND', p)
            return p
        vp = field(p)
        # print('field value:', vp)
        #      previous = Point(p) # copy is mandatory here
        previous = np.copy(p)  # copy is mandatory here
        if (v - vp) * (v - v2) <= 0:
            # Look for between vp and v2
            v1 = vp
            p1 = p
        elif (v - vp) * (v - v1) <= 0:
            # Look for between v1 and vp
            v2 = vp
            p2 = p
        else:
            raise AssertionError()
            return None
    return None


def make_potential(potdata, drifts=None):
    params = (
        covariance_data(potdata),
        gradient_data(potdata),
        interface_data(potdata),
        drifts or drift_basis(potdata),
    )
    field = pypotential.potential_field(*params)
    return field


def fault_potential(data):
    potdata = data.potential_data
    assert len(potdata.interfaces) == 1, "inconsistent fault potential field"
    return make_potential(potdata)


def finite_fault(data):
    assert not data.infinite
    potdata = data.potential_data
    assert len(potdata.interfaces) == 1, "inconsistent fault potential field"
    points = np.reshape(potdata.interfaces[0], (-1, 3))
    center = None
    if data.center_type == "mean_center":
        center = np.mean(points, axis=0)
    elif data.center_type == "databox_center":
        center = np.array(
            [0.5 * (points[:, axis].min() + points[:, axis].max()) for axis in range(3)]
        )
    else:
        assert type(data.center_type) is tuple, "unknown fault center type" + str(
            data.center_type
        )
        center = np.array(data.center_type)
    center = np.asarray(center, dtype=scalardt)
    assert center is not None
    field = fault_potential(data)
    # The following is as in GeoModeller: might be improved?
    # it is based on the idea that the fault geometry is close
    # to a (planar!) disk
    g = pypotential.gradient(field)(center)
    g.shape = (3,)
    assert np.linalg.norm(g) > 0
    g /= np.linalg.norm(g)
    u = v = None
    if g[0] == g[1] == 0:  # tangent plane is horizontal
        u = np.array([1, 0, 0], dtype=scalardt)  # somewhat arbitrary
    else:
        vertical = np.array([0, 0, 1], dtype=scalardt)
        u = np.cross(vertical, g)
        u /= np.linalg.norm(u)
    v = np.cross(u, g)  # the basis is not direct!
    v /= np.linalg.norm(v)
    g *= data.influence_radius
    u *= data.lateral_extent
    v *= data.vertical_extent
    ellipsoid = pypotential.Ellipsoid(
        pypotential.Point(*center),
        (pypotential.Vector(*g), pypotential.Vector(*u), pypotential.Vector(*v)),
    )
    return field, ellipsoid


def recast(data):
    box, pile, faults_data, topography, formations = data
    box_center = np.array(
        [0.5 * (box[s + "min"] + box[s + "max"]) for s in ("X", "Y", "Z")],
        dtype=scalardt,
    )
    L = max([box[s + "max"] - box[s + "min"] for s in ("X", "Y", "Z")])
    assert L > 0

    def recast_axis(i, x):
        return (x - box_center[i]) / L

    def recast_z(z):
        return recast_axis(2, z)

    def recast_P(P):
        return (np.asarray(P, dtype=scalardt) - box_center) / L

    if type(topography) is ImplicitHorizontalPlane:
        topography = ImplicitHorizontalPlane(recast_z(topography.z))
    else:
        assert type(topography) is ImplicitDTM
        topography = ImplicitDTM(
            recast_P(topography.origin), topography.steps / L, recast_z(zmap)
        )
    new_box = {}
    for i, s in enumerate(("X", "Y", "Z")):
        new_box[s + "min"] = recast_axis(i, box[s + "min"])
        new_box[s + "max"] = recast_axis(i, box[s + "max"])

    def rescale_potential_data(handle):
        if handle.potential_data is not None:
            potdata = handle.potential_data
            potdata.interfaces = [
                recast_P(interface) for interface in potdata.interfaces
            ]
            gradients = potdata.gradients
            gradients = GradientData(
                recast_P(gradients.locations),
                gradients.values,  # * L, # FIXME: scale effect *L
            )
            potdata.covariance_model.range /= L

    for serie in pile.all_series:
        if serie.potential_data is not None:
            rescale_potential_data(serie)
    for _name, fault in faults_data.items():
        rescale_potential_data(fault)
    return box, pile, faults_data, topography, formations


def compute_fault_stops_on(model):
    relations = {}
    for fault, data in model.faults_data.items():
        assert len(data.potential_data.interfaces) == 1
        points = data.potential_data.interfaces[0]
        limits = []
        for limit in data.stops_on:
            # the potential field associated to the limit
            # is used to determine where lie the points defining the fault
            v = np.mean(model.faults[limit](points))
            assert v != 0, f"inconsitent limit potential in {fault} stops on {limit}"
            limits.append((limit, -1 if v < 0 else 1))
        relations[fault] = limits
    return relations


class GeologicalModel:

    def __init__(self, data):
        self.box = data["box"]
        self.crs = CRSInfo(*data["crs"])
        self.pile = data["pile"]
        assert self.pile.reference in ("top", "base")
        self.faults_data = data["faults_data"]
        self.topography = data["topography"]
        formations = data["formations"]
        faults = {}
        fault_ellipsoids = {}
        fault_drifts = {}
        faults_data = data["faults_data"]
        for name, data in faults_data.items():
            field = None
            ellipsoid = None
            if data.infinite:
                field = fault_potential(data)
            else:
                field, ellipsoid = finite_fault(data)
            faults[name] = pypotential.Fault(field)
            if ellipsoid is not None:
                faults[name].stops_on(ellipsoid)
                fault_ellipsoids[name] = ellipsoid
        for name, data in faults_data.items():
            fault = faults[name]
            filtered_limits = []
            for limit_name in data.stops_on:
                if limit_name not in faults:
                    pass
                else:
                    filtered_limits.append(limit_name)
            data.stops_on = filtered_limits
            for limit_name in data.stops_on:
                fault.stops_on(faults[limit_name])
        for name, fault in faults.items():
            if name in fault_ellipsoids:
                fault_drifts[name] = pypotential.make_finite_drift(
                    fault, fault_ellipsoids[name]
                )
            else:
                fault_drifts[name] = pypotential.make_drift(fault)
        fields = []
        values = []
        relations = []
        formation_names = [f.name for f in formations]
        pile_formations = []
        series_info = {}

        def register_pile_formation(formation):
            assert formation in formation_names, (
                "Unknown formation " + formation + " in stratigraphic column!"
            )
            pile_formations.append(formation)

        found_dummy_formation = False
        pile = self.pile
        for Sk, serie in enumerate(pile.all_series):
            potdata = serie.potential_data
            if potdata:
                active_faults = {}
                drifts = drift_basis(potdata)
                if serie.influenced_by_fault:
                    for name in serie.influenced_by_fault:
                        try:
                            drifts.append(fault_drifts[name])
                            active_faults[name] = len(drifts) - 1
                        except KeyError:
                            pass
                field = make_potential(potdata, drifts)
                interfaces = []
                for i, interface in enumerate(potdata.interfaces):
                    if len(interface) == 0:
                        pass
                    else:
                        mean_field_value = np.mean(field(interface))
                        values.append(mean_field_value)
                        formation = serie.formations[i]
                        interfaces.append(
                            (pile.reference + "-" + formation, mean_field_value)
                        )
                        fields.append(field)
                        register_pile_formation(formation)
                        relations.append(serie.relation)
                series_info[serie.name] = SeriesInfo(
                    field, drifts, active_faults, interfaces
                )
            else:

                def register_single_formation():
                    assert len(serie.formations) == 1
                    # print('registering dummy formation', serie.formations)
                    register_pile_formation(serie.formations[0])

                if (pile.reference == "base" and Sk == 0) or (
                    pile.reference == "top" and Sk == len(pile.all_series) - 1
                ):
                    register_single_formation()
                    found_dummy_formation = True
                else:
                    pass
        if not found_dummy_formation:
            dummy_formations = [f for f in formations if f.is_dummy]
            # when importing a GeoModeller project the DefaultCover dummy formation is not exported
            if len(dummy_formations) == 0:
                assert pile.reference in {"top", "base"}, "Unknown pile reference"
                dummy = geomodeller_project.Formation(
                    name="Default" + {"top": "Cover", "base": "Base"}[pile.reference],
                    color=(0.3,) * 3,
                    is_dummy=True,
                )
                formations.append(dummy)
                dummy_formations = [dummy]
            assert len(dummy_formations) == 1, "A dummy formation is needed!"
            if pile.reference == "base":
                pile_formations.insert(0, dummy_formations[0].name)
            else:
                pile_formations.append(dummy_formations[0].name)
        assert len(fields) == len(relations)
        assert len(fields) + 1 == len(pile_formations)
        self.fields = fields
        self.formations = formations
        self.formation_colors = {f.name: f.color for f in formations}
        self.pile_formations = pile_formations
        self.series_info = series_info
        self.values = values
        self.relations = relations
        self.faults = faults
        self.fault_ellipsoids = fault_ellipsoids
        self.fault_drifts = fault_drifts
        self.fault_stops_on = compute_fault_stops_on(self)

    def collect_pile_information(self):
        relations = list(self.relations)
        if self.pile.reference == "base":
            relations.insert(0, "onlap")
        else:
            relations.append("onlap")
        return [
            PileInfo(formation, self.formation_colors[formation], relation)
            for formation, relation in zip(self.pile_formations, relations)
        ]

    def nbformations(self):
        return len(self.pile_formations)

    def nbcontacts(self):
        # FIXME: this should have to be define rigorously...
        return len(self.fields)

    def getbox(self):
        xmin, xmax = (self.box["Xmin"], self.box["Xmax"])
        ymin, ymax = (self.box["Ymin"], self.box["Ymax"])
        zmin, zmax = (self.box["Zmin"], self.box["Zmax"])
        return Box(xmin, ymin, zmin, xmax, ymax, zmax)

    def bbox(self):
        xmin, xmax = (self.box["Xmin"], self.box["Xmax"])
        ymin, ymax = (self.box["Ymin"], self.box["Ymax"])
        zmin, zmax = (self.box["Zmin"], self.box["Zmax"])
        return BBox3(xmin, xmax, ymin, ymax, zmin, zmax)

    def domain(self, x, y, z):
        return self.rank((x, y, z))

    def rank_without_topography(self, p):
        n = len(self.fields)
        j1 = 0
        j2 = n
        # parcourir les erode decroissants
        erosion_surfaces = [i for i in range(n) if self.relations[i] == "erode"]
        for i in reversed(erosion_surfaces):
            field = self.fields[i]
            vp = field(p)
            vi = self.values[i]
            if vp > vi:
                j1 = i
                break
            j2 = i
        # parcourir les onlap croissants dans l'intervalle j1 j2
        rank = j1
        assert j1 == 0 or (
            self.relations[j1] == "erode" and self.fields[j1](p) > self.values[j1]
        )
        rank = j1
        for i in range(j1, j2):
            field = self.fields[i]
            vp = field(p)
            vi = self.values[i]
            # when i=j1>0 we are sure that vp<vi (previous test)
            if vp < vi:
                break
            rank += 1
        # print ("Which domain:", p[0], p[1], p[2], rank+1)
        return rank + 1

    def rank(self, p, consider_topography=True):
        if consider_topography and self.topography(p) > 0:
            return 0
        return self.rank_without_topography(p)

    def intersect(
        self,
        p1,
        p2,
        consider_formations=True,
        consider_faults=False,
        consider_topography=True,
        precision=0.01,
    ):
        # print('-> intersect', p1, p2)
        p = point_between(p1, p2, self.topography, 0, precision)
        if p is not None:
            return Intersection(p, self.topography)
        # print('            no topo')
        # test fault potential fields
        if consider_faults:
            for name, fault in self.faults.items():
                p = point_between(p1, p2, fault, 0, precision)
                if p is not None:
                    if self.is_fault_point_valid(p, name, consider_topography):
                        return Intersection(p, fault, fault=name)
        # test potential fields
        # print('            no faults')
        if consider_formations:
            n = len(self.fields)
            for i in range(n):
                p = point_between(p1, p2, self.fields[i], self.values[i], precision)
                if p is not None:
                    if self.is_valid(p, i, consider_topography):
                        # print('            Found:', n, p, 'shape:', p.shape)
                        return Intersection(p, self.fields[i], self.values[i])
            # print('            Nothing!')
        return None

    def is_valid(self, p, rank, with_topography=True):
        if with_topography and self.topography(p) > 0:
            return False
        n = len(self.fields)
        for i in range(rank + 1, n):
            Ri = self.relations[i]
            if Ri == "erode":
                field = self.fields[i]
                vp = field(p)
                vi = self.values[i]
                if vp > vi:
                    return False
        R = self.relations[rank]
        if R == "onlap":
            for i in reversed(range(rank)):
                field = self.fields[i]
                vp = field(p)
                vi = self.values[i]
                if vp < vi:
                    return False
                Ri = self.relations[i]
                if Ri == "erode":
                    break
        return True

    def is_fault_point_valid(self, p, fault, with_topography=True):
        if with_topography and self.topography(p) > 0:
            return False
        if self.is_finite_fault(fault) and self.fault_ellipsoids[fault](p) >= 1:
            return False
        for limit_info in self.fault_stops_on[fault]:
            limit, side = limit_info
            if self.faults[limit](p) * side < 0:
                return False
        return True

    def rank_colors(self):
        for formation in self.pile_formation:
            result.append(self.formation_colors[formation])
        return result

    def stats(self):
        result = []
        minimum_distances = []

        def register(name, data):
            ng = data.nb_gradients
            nc = data.nb_contact_points
            result.append(
                f"{name} has {ng:d} gradients values "
                f"and {nc:d} contact points which make {ng + 3 * nc} dof"
            )
            mdg, mdc = data.minimum_distances()
            result.append(f"\tminimum distances {mdg:f} {mdc:f}")
            minimum_distances.append((mdg, mdc))

        for serie, info in self.series_info.items():
            if info.field is None:
                result.append(serie + "has no potential field")
            else:
                register(f"serie {serie}", info.field.data())
        for fault, info in self.faults.items():
            register(f"fault {fault}", info.potential_field.data())
        md = np.array(minimum_distances)
        mdg = md[:, 0]
        mdc = md[:, 1]
        if np.any(mdg >= 0):
            result.append(
                f"Minimum distance between gradients: {np.min(mdg[mdg >= 0]):f}"
            )
        if np.any(mdg < 0):
            result.append(
                f"There are {np.sum(mdg < 0):d} series with a single gradient data!"
            )
        if np.any(mdg == 0):  # This shall not happen (kriging matrix would be singular)
            result.append(
                f"There are {np.sum(mdg == 0):d} with confunded gradient data!"
            )
        if np.any(mdc >= 0):
            result.append(
                f"Minimum distance between contacts: {np.min(mdc[mdc >= 0]):f}"
            )
        if np.any(mdc < 0):
            result.append(
                f"There are {np.sum(mdc < 0):d} series with a single contact data!"
            )
        if np.any(mdc == 0):  # This shall not happen (kriging matrix would be singular)
            result.append(
                f"There are {np.sum(mdc == 0):d} series with a condunded contact data!"
            )
        return "\n".join(result)

    def diagonal_section(self, flip=False):
        box = self.getbox()
        if flip:
            diagonal = Polyline([[box.xmin, box.ymax, 0], [box.xmax, box.ymin, 0]])
        else:
            diagonal = Polyline([[box.xmin, box.ymin, 0], [box.xmax, box.ymax, 0]])
        return VerticalSection(diagonal, box.zmin, box.zmax)

    def x_section(self, x=None, flip=False):
        box = self.getbox()
        x = x or 0.5 * (box.xmin + box.xmax)
        if flip:
            path = Polyline([[x, box.ymax, 0], [x, box.ymin, 0]])
        else:
            path = Polyline([[x, box.ymin, 0], [x, box.ymax, 0]])
        return VerticalSection(path, box.zmin, box.zmax)

    def y_section(self, y=None, flip=False):
        box = self.getbox()
        y = y or 0.5 * (box.ymin + box.ymax)
        if flip:
            path = Polyline([[box.xmax, y, 0], [box.xmin, y, 0]])
        else:
            path = Polyline([[box.xmin, y, 0], [box.xmax, y, 0]])
        return VerticalSection(path, box.zmin, box.zmax)

    def ranks_to_rgb_picture(self, ranks, atmopshere_color=(0, 0, 0)):
        picture = np.zeros((*ranks.shape, 3), dtype=np.uint8)
        pile = self.collect_pile_information()
        rank_color = [atmopshere_color] + [
            [int(col * 255) for col in formation.color] for formation in pile
        ]
        assert np.all(
            (ranks >= 0) & (ranks < len(rank_color))
        ), "Inconsistency in domain indexing!"
        for fi, color in enumerate(rank_color):
            picture[ranks == fi] = color
        return picture

    def is_finite_fault(self, name):
        return name in self.fault_ellipsoids

    @property
    def has_finite_faults(self):
        return any(name in self.fault_ellipsoids for name in self.faults)

    def rgb_picture(
        self,
        section,
        width,
        height=None,
        atmopshere_color=(0, 0, 0),
        return_ranks=False,
    ):
        if height is None:
            width, height = image_ratio(section, width)
        ranks = np.array([self.rank(p) for p in section.grid(width, height)])
        ranks.shape = width, height
        ranks = np.transpose(ranks)[::-1]
        picture = self.ranks_to_rgb_picture(ranks, atmopshere_color)
        if return_ranks:
            return picture, ranks
        return picture

    def topography_as_elevation_surface(self):
        topo = self.topography
        if hasattr(topo, "origin"):
            zmap = np.transpose(topo.z)[::-1]
            return ElevationRaster(topo.origin, topo.steps, zmap)
        return ConstantElevationSurface(topo.z)

    def implicit_topography(self):
        return ImplicitTopography(self.topography_as_elevation_surface())
