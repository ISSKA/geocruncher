#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>
#include <pybind11/operators.h>
#include <pybind11/iostream.h>

#include <memory>

#include <KarstNSim/vec.h>
#include <KarstNSim/basics.h>
#include <KarstNSim/geostats.h>
#include <KarstNSim/run_code.h>
#include "KarstNSim/karstic_network.h" // KarsticNetwork + depends on graph.h
#include "KarstNSim/geology.h"         // GeologicalParameters, KeyPoint, CostTerm, KeyPointType
#include "KarstNSim/ghost_rocks.h"     // Ghost-rock helpers (used indirectly)
#include "KarstNSim/randomgenerator.h" // RNG initialization

// Lifetime ownership helpers (see note in module body). We place them in an anonymous namespace
// at translation unit scope so they are available inside the binding lambdas.
namespace {
    std::vector<std::unique_ptr<KarstNSim::Surface>> g_owned_surfaces; // individual surfaces kept alive
    std::vector<std::unique_ptr<std::vector<KarstNSim::Surface>>> g_owned_surface_vectors; // vectors kept alive
}

namespace py = pybind11;

using namespace KarstNSim;

PYBIND11_MODULE(pykarstnsim_core, m)
{
    m.doc() = "KarstNSim Python bindings";
    // Lifetime safety note: the original API stores raw pointers to surfaces/vectors provided by
    // the caller. Python temporaries would dangle; safe_* wrapper methods below copy & retain.

    // Vector3
    py::class_<Vector3>(m, "Vector3", R"doc(3D vector with float components (x, y, z). Utility type for geometry and sampling.)doc")
        .def(py::init<>(), R"doc(Default constructor. Initializes components to 0.)doc")
        .def(py::init<float, float, float>(), py::arg("x"), py::arg("y"), py::arg("z"), R"doc(Construct with explicit x, y, z values.)doc")
        .def_readwrite("x", &Vector3::x, R"doc(X component.)doc")
        .def_readwrite("y", &Vector3::y, R"doc(Y component.)doc")
        .def_readwrite("z", &Vector3::z, R"doc(Z component.)doc")
        .def("__repr__", [](const Vector3 &v)
             { return "Vector3(" + std::to_string(v.x) + ", " + std::to_string(v.y) + ", " + std::to_string(v.z) + ")"; });

    // Segment (needed for Line API exposure if required)
    py::class_<Segment>(m, "Segment", R"doc(Line segment defined by two 3D points (start, end).)doc")
        .def(py::init<const Vector3 &, const Vector3 &>(), py::arg("start"), py::arg("end"), R"doc(Construct segment from two endpoints.)doc")
        .def("start", &Segment::start, R"doc(Return start point (Vector3).)doc")
        .def("end", &Segment::end, R"doc(Return end point (Vector3).)doc");

    // Line
    py::class_<Line>(m, "Line", R"doc(Polyline composed of connected segments; caches unique nodes.)doc")
        .def(py::init<>(), R"doc(Default empty line.)doc")
        .def(py::init<std::vector<Segment>>(), py::arg("segments"), R"doc(Construct from a list of segments; unique nodes list is built.)doc")
        .def("append", &Line::append, py::arg("segment"), R"doc(Append a segment to the line (no uniqueness rebuild).)doc")
        .def("size", py::overload_cast<>(&Line::size), R"doc(Number of segments (non-const overload).)doc")
        .def("get_nb_segs", py::overload_cast<>(&Line::get_nb_segs, py::const_), R"doc(Number of segments.)doc")
        .def("get_nb_unique_nodes", py::overload_cast<>(&Line::get_nb_unique_nodes, py::const_), R"doc(Number of distinct nodes (points).)doc")
        .def("get_unique_nodes", py::overload_cast<>(&Line::get_unique_nodes, py::const_), R"doc(Return vector of unique nodes.)doc")
        .def("get_seg", py::overload_cast<int>(&Line::get_seg, py::const_), py::arg("i"), R"doc(Return i-th segment.)doc")
        .def("__repr__", [](const Line &)
             { return "Line()"; });

    // Triangle (minimal; Surface uses it)
    py::class_<Triangle>(m, "Triangle", R"doc(Triangle defined by three vertex indices referencing a Surface's point list.)doc")
        .def(py::init<int, int, int>(), py::arg("a"), py::arg("b"), py::arg("c"), R"doc(Construct from three point indices.)doc")
        .def("point", &Triangle::point, py::arg("i"), R"doc(Return i-th vertex index (0..2).)doc")
        .def("contains_vertex", &Triangle::containsVertex, py::arg("vertex_index"), R"doc(Check if given point index belongs to the triangle.)doc");

    // Surface (lightweight subset)
    py::class_<Surface>(m, "Surface", R"doc(3D triangulated surface: points + filtered valid triangles (bad triangles removed on construction).)doc")
        .def(py::init<const std::string &>(), py::arg("name") = "DefaultName", R"doc(Construct empty surface with an optional name.)doc")
        .def(py::init<std::vector<Vector3>, std::vector<Triangle>, const std::string &>(),
             py::arg("points"), py::arg("triangles"), py::arg("name") = "DefaultName",
             R"doc(Construct surface from points and candidate triangles; invalid (degenerate) triangles are discarded.)doc")
        .def("get_nb_trgls", &Surface::get_nb_trgls, R"doc(Number of stored (valid) triangles.)doc")
        .def("get_nb_pts", &Surface::get_nb_pts, R"doc(Number of points.)doc")
        .def("is_empty", &Surface::is_empty, R"doc(True if no points or triangles.)doc")
        .def("get_triangle", py::overload_cast<const int &>(&Surface::get_triangle), py::arg("i"), R"doc(Return i-th triangle.)doc")
        .def("get_node", &Surface::get_node, py::arg("i"), R"doc(Return i-th point (Vector3).)doc")
        .def("get_boundbox_min", &Surface::get_boundbox_min, R"doc(Axis-aligned bounding box minimum corner.)doc")
        .def("get_boundbox_max", &Surface::get_boundbox_max, R"doc(Axis-aligned bounding box maximum corner.)doc")
        .def("get_trgl_center", &Surface::get_trgl_center, py::arg("triangle_index"), R"doc(Centroid of specified triangle.)doc")
        .def("get_nb_valid_trgls", &Surface::get_nb_valid_trgls, R"doc(Count of triangles considered valid during construction filtering.)doc")
        .def("__repr__", [](const Surface &s)
             { return "Surface(nb_pts=" + std::to_string(const_cast<Surface &>(s).get_nb_pts()) + ")"; });

    // Box (subset of API)
    py::class_<Box>(m, "Box", R"doc(3D axis-aligned (in local coordinates) grid-aligned box storing basis/end corners, step vectors and grid dimensions.)doc")
        .def(py::init<>(), R"doc(Default uninitialized box.)doc")
        .def(py::init<const Vector3 &, const Vector3 &, const Vector3 &, const Vector3 &, const int &, const int &, const int &>(),
             py::arg("basis"), py::arg("u"), py::arg("v"), py::arg("w"), py::arg("nu"), py::arg("nv"), py::arg("nw"),
             R"doc(Construct box from basis corner, three step vectors (u,v,w) and cell counts (nu,nv,nw).)doc")
        .def("contains", &Box::contains, py::arg("point"), R"doc(Test if a world-space point lies inside the box.)doc")
        .def("center", &Box::Center, R"doc(Box geometric center.)doc")
        .def("distance", &Box::Distance, py::arg("point"), R"doc(Min distance from point to box.)doc")
        .def("diagonal", &Box::Diagonal, R"doc(Diagonal vector (size)).)doc")
        .def("random_inside", &Box::RandomInside, R"doc(Generate random point uniformly inside box bounds.)doc")
        .def("vertex", &Box::Vertex, py::arg("i"), R"doc(Return vertex 0 (basis) or 1 (end).)doc")
        .def("get_basis", &Box::get_basis, R"doc(Basis (min) corner in world coordinates.)doc")
        .def("get_end", &Box::get_end, R"doc(End (max) corner in world coordinates.)doc")
        .def("get_u", &Box::get_u, R"doc(Step vector u.)doc")
        .def("get_v", &Box::get_v, R"doc(Step vector v.)doc")
        .def("get_w", &Box::get_w, R"doc(Step vector w.)doc")
        .def("get_nu", &Box::get_nu, R"doc(Grid size along u.)doc")
        .def("get_nv", &Box::get_nv, R"doc(Grid size along v.)doc")
        .def("get_nw", &Box::get_nw, R"doc(Grid size along w.)doc")
        .def("uvw2xyz", &Box::uvw2xyz, py::arg("u"), py::arg("v"), py::arg("w"), py::arg("cellcentered") = false, R"doc(Convert integer (u,v,w) indices to world coordinates. If cellcentered, indices refer to cell centers.)doc")
        .def("__repr__", [](const Box &)
             { return "Box()"; });

    // GeostatParams
    py::class_<GeostatParams>(m, "GeostatParams", R"doc(Geostatistical parameters grouping variogram models (global/inter/intra-branch) and neighborhood controls.)doc")
        .def(py::init<>(), R"doc(Default geostat params; 'is_used' flag disabled.)doc")
        .def_readwrite("is_used", &GeostatParams::is_used, R"doc(Flag: enable geostatistical simulation of conduit properties.)doc")
        .def_readwrite("simulated_property", &GeostatParams::simulated_property, R"doc(Output simulated property values along skeleton.)doc")
        .def_readwrite("simulation_distribution", &GeostatParams::simulation_distribution, R"doc(Input distribution sampled during SGS.)doc")
        .def_readwrite("global_vario_range", &GeostatParams::global_vario_range, R"doc(Global variogram range.)doc")
        .def_readwrite("global_range_of_neighborhood", &GeostatParams::global_range_of_neighborhood, R"doc(Neighborhood search range for global model.)doc")
        .def_readwrite("global_vario_sill", &GeostatParams::global_vario_sill, R"doc(Global variogram sill.)doc")
        .def_readwrite("global_vario_nugget", &GeostatParams::global_vario_nugget, R"doc(Global variogram nugget.)doc")
        .def_readwrite("global_vario_model", &GeostatParams::global_vario_model, R"doc(Global variogram model name.)doc")
        .def_readwrite("interbranch_vario_range", &GeostatParams::interbranch_vario_range, R"doc(Inter-branch variogram range.)doc")
        .def_readwrite("interbranch_range_of_neighborhood", &GeostatParams::interbranch_range_of_neighborhood, R"doc(Neighborhood range for inter-branch model.)doc")
        .def_readwrite("interbranch_vario_sill", &GeostatParams::interbranch_vario_sill, R"doc(Inter-branch variogram sill.)doc")
        .def_readwrite("interbranch_vario_nugget", &GeostatParams::interbranch_vario_nugget, R"doc(Inter-branch variogram nugget.)doc")
        .def_readwrite("interbranch_vario_model", &GeostatParams::interbranch_vario_model, R"doc(Inter-branch variogram model name.)doc")
        .def_readwrite("intrabranch_vario_range", &GeostatParams::intrabranch_vario_range, R"doc(Intra-branch variogram range.)doc")
        .def_readwrite("intrabranch_range_of_neighborhood", &GeostatParams::intrabranch_range_of_neighborhood, R"doc(Neighborhood range for intra-branch model.)doc")
        .def_readwrite("intrabranch_vario_sill", &GeostatParams::intrabranch_vario_sill, R"doc(Intra-branch variogram sill.)doc")
        .def_readwrite("intrabranch_vario_nugget", &GeostatParams::intrabranch_vario_nugget, R"doc(Intra-branch variogram nugget.)doc")
        .def_readwrite("intrabranch_vario_model", &GeostatParams::intrabranch_vario_model, R"doc(Intra-branch variogram model name.)doc")
        .def_readwrite("number_max_of_neighborhood_points", &GeostatParams::number_max_of_neighborhood_points, R"doc(Max points retained in local neighborhood system.)doc")
        .def_readwrite("nb_points_interbranch", &GeostatParams::nb_points_interbranch, R"doc(Number of points per branch for inter-branch model.)doc")
        .def_readwrite("proportion_interbranch", &GeostatParams::proportion_interbranch, R"doc(Proportion of points per branch for inter-branch model.)doc")
        .def("__repr__", [](const GeostatParams &)
             { return "GeostatParams()"; });

    // ParamsSource
    py::class_<ParamsSource>(m, "ParamsSource", R"doc(Struct holding all simulation parameters (graph construction, geological constraints, amplification, saving & geostats).)doc")
        .def(py::init<>(), R"doc(Default-initialize all parameters (matching C++ defaults).)doc")
        // Names
        .def_readwrite("karstic_network_name", &ParamsSource::karstic_network_name, R"doc(Name of simulation; prefix for outputs.)doc")
        .def_readwrite("save_repository", &ParamsSource::save_repository, R"doc(Output directory name.)doc")
        // General parameters
        .def_readwrite("domain", &ParamsSource::domain, R"doc(Background grid / spatial domain (Box).)doc")
        .def_readwrite("selected_seed", &ParamsSource::selected_seed, R"doc(Base seed for RNG.)doc")
        .def_readwrite("number_of_iterations", &ParamsSource::number_of_iterations, R"doc(Number of simulation repetitions.)doc")
        .def_readwrite("vary_seed", &ParamsSource::vary_seed, R"doc(If true, seed changes each iteration.)doc")
        .def_readwrite("topo_surface", &ParamsSource::topo_surface, R"doc(Topographic surface (Surface).)doc")
        // Sampling reuse
        .def_readwrite("use_sampling_points", &ParamsSource::use_sampling_points, R"doc(Use pre-existing sampling cloud.)doc")
        .def_readwrite("sampling_points", &ParamsSource::sampling_points, R"doc(Points used if reuse is enabled.)doc")
        // New sampling
        .def_readwrite("poisson_radius", &ParamsSource::poisson_radius, R"doc(Poisson disk radius if uniform sampling.)doc")
        .def_readwrite("use_density_property", &ParamsSource::use_density_property, R"doc(Enable spatial density property for sampling.)doc")
        .def_readwrite("k_pts", &ParamsSource::k_pts, R"doc(k value in Bridson/Dwork algorithm (candidates per sample).)doc")
        // Previous networks
        .def_readwrite("use_previous_networks", &ParamsSource::use_previous_networks, R"doc(Enable polyphasic simulation with previous networks.)doc")
        .def_readwrite("previous_networks", &ParamsSource::previous_networks, R"doc(List of prior Line objects.)doc")
        .def_readwrite("fraction_old_karst_perm", &ParamsSource::fraction_old_karst_perm, R"doc(Polyphasic cost reduction factor (Ppoly).)doc")
        .def_readwrite("sections_simulation_only", &ParamsSource::sections_simulation_only, R"doc(If true: skip network gen; only section simulation using previous network.)doc")
        // N nearest neighbor graph
        .def_readwrite("nghb_count", &ParamsSource::nghb_count, R"doc(Number of nearest neighbors per node.)doc")
        .def_readwrite("use_max_nghb_radius", &ParamsSource::use_max_nghb_radius, R"doc(Enable maximum neighbor search radius.)doc")
        .def_readwrite("nghb_radius", &ParamsSource::nghb_radius, R"doc(Max neighbor search radius if enabled.)doc")
        // Ghost-rocks
        .def_readwrite("use_ghostrocks", &ParamsSource::use_ghostrocks, R"doc(Enable ghost-rock alteration zones.)doc")
        .def_readwrite("alteration_lines", &ParamsSource::alteration_lines, R"doc(Polyline(s) defining surface alteration lines.)doc")
        .def_readwrite("interpolate_lines", &ParamsSource::interpolate_lines, R"doc(Interpolation between alteration lines (not yet implemented).)doc")
        .def_readwrite("ghostrock_max_vertical_size", &ParamsSource::ghostrock_max_vertical_size, R"doc(Max vertical size for ghost-rock regions.)doc")
        .def_readwrite("use_max_depth_constraint", &ParamsSource::use_max_depth_constraint, R"doc(Apply max depth constraint using horizon surface.)doc")
        .def_readwrite("ghost_rock_weight", &ParamsSource::ghost_rock_weight, R"doc(Weight applied to ghost-rock constraint in IKP cost.)doc")
        .def_readwrite("max_depth_horizon", &ParamsSource::max_depth_horizon, R"doc(Horizon surface imposing ghost-rock depth limit.)doc")
        .def_readwrite("ghostrock_width", &ParamsSource::ghostrock_width, R"doc(Max lateral width of ghost-rock zones.)doc")
        // Inlets / outlets / waypoints
        .def_readwrite("sinks", &ParamsSource::sinks, R"doc(List of sink (inlet) points.)doc")
        .def_readwrite("springs", &ParamsSource::springs, R"doc(List of spring (outlet) points.)doc")
        .def_readwrite("allow_single_outlet_connection", &ParamsSource::allow_single_outlet_connection, R"doc(Force each inlet to connect to a single spring.)doc")
        .def_readwrite("use_waypoints", &ParamsSource::use_waypoints, R"doc(Enable intermediate waypoint constraints.)doc")
        .def_readwrite("waypoints", &ParamsSource::waypoints, R"doc(Waypoint coordinates.)doc")
        .def_readwrite("use_springs_radius", &ParamsSource::use_springs_radius, R"doc(Enable radii usage for springs in section simulation.)doc")
        .def_readwrite("use_sinks_radius", &ParamsSource::use_sinks_radius, R"doc(Enable radii usage for sinks in section simulation.)doc")
        .def_readwrite("use_waypoints_radius", &ParamsSource::use_waypoints_radius, R"doc(Enable radii usage for waypoints in section simulation.)doc")
        .def_readwrite("waypoints_weight", &ParamsSource::waypoints_weight, R"doc(Weight of waypoint proximity constraint.)doc")
        // No-karst spheres
        .def_readwrite("use_no_karst_spheres", &ParamsSource::use_no_karst_spheres, R"doc(Enable exclusion spheres where no karst is allowed.)doc")
        .def_readwrite("sphere_centers", &ParamsSource::sphere_centers, R"doc(Centers for exclusion spheres.)doc")
        // Inception surfaces
        .def_readwrite("add_inception_surfaces", &ParamsSource::add_inception_surfaces, R"doc(Enable inception surfaces usage.)doc")
        .def_readwrite("refine_surface_sampling", &ParamsSource::refine_surface_sampling, R"doc(Sampling refinement level on surfaces.)doc")
        .def_readwrite("inception_surfaces", &ParamsSource::inception_surfaces, R"doc(List of inception surfaces.)doc")
        .def_readwrite("inception_surface_constraint_weight", &ParamsSource::inception_surface_constraint_weight, R"doc(Weight for inception surface constraint.)doc")
        .def_readwrite("max_inception_surface_distance", &ParamsSource::max_inception_surface_distance, R"doc(Max distance for inception surface influence.)doc")
        // Karstification potential
        .def_readwrite("use_karstification_potential", &ParamsSource::use_karstification_potential, R"doc(Enable karstification potential property.)doc")
        .def_readwrite("karstification_potential_weight", &ParamsSource::karstification_potential_weight, R"doc(Weight applied to potential in cost.)doc")
        // Fractures
        .def_readwrite("use_fracture_constraints", &ParamsSource::use_fracture_constraints, R"doc(Enable fracture orientation constraints.)doc")
        .def_readwrite("fracture_families_orientations", &ParamsSource::fracture_families_orientations, R"doc(List of fracture family azimuths (deg).)doc")
        .def_readwrite("fracture_families_tolerance", &ParamsSource::fracture_families_tolerance, R"doc(Angular tolerances for families (deg).)doc")
        .def_readwrite("fracture_constraint_weight", &ParamsSource::fracture_constraint_weight, R"doc(Weight applied to fracture alignment cost.)doc")
        // Water tables
        .def_readwrite("surf_wat_table", &ParamsSource::surf_wat_table, R"doc(One water table surface per spring.)doc")
        .def_readwrite("water_table_constraint_weight_vadose", &ParamsSource::water_table_constraint_weight_vadose, R"doc(Weight of water table constraint in vadose zone.)doc")
        .def_readwrite("water_table_constraint_weight_phreatic", &ParamsSource::water_table_constraint_weight_phreatic, R"doc(Weight of water table constraint in phreatic zone.)doc")
        // Other cost graph params
        .def_readwrite("gamma", &ParamsSource::gamma, R"doc(Gamma parameter (graph pruning rule).)doc")
        .def_readwrite("fraction_karst_perm", &ParamsSource::fraction_karst_perm, R"doc(Cost reduction factor Pred (cohesion).)doc")
        .def_readwrite("vadose_cohesion", &ParamsSource::vadose_cohesion, R"doc(If false, cohesion only in phreatic zone.)doc")
        .def_readwrite("multiply_costs", &ParamsSource::multiply_costs, R"doc(Use multiplicative combination of costs instead of additive.)doc")
        // Deadend amplification
        .def_readwrite("use_deadend_points", &ParamsSource::use_deadend_points, R"doc(Enable dead-end point generation for amplification.)doc")
        .def_readwrite("nb_deadend_points", &ParamsSource::nb_deadend_points, R"doc(Number of dead-end points generated.)doc")
        .def_readwrite("max_distance_of_deadend_pts", &ParamsSource::max_distance_of_deadend_pts, R"doc(Maximum distance from existing nodes for dead-end points.)doc")
        // Cycle amplification
        .def_readwrite("use_amplification", &ParamsSource::use_amplification, R"doc(Enable cycle-based amplification stage.)doc")
        .def_readwrite("max_distance_amplification", &ParamsSource::max_distance_amplification, R"doc(Max distance between random nodes forming cycle.)doc")
        .def_readwrite("min_distance_amplification", &ParamsSource::min_distance_amplification, R"doc(Min distance between random nodes forming cycle.)doc")
        .def_readwrite("nb_cycles", &ParamsSource::nb_cycles, R"doc(Number of amplification cycles.)doc")
        // Noise amplification
        .def_readwrite("use_noise", &ParamsSource::use_noise, R"doc(Include noise during amplification only.)doc")
        .def_readwrite("use_noise_on_all", &ParamsSource::use_noise_on_all, R"doc(Include noise during both simulation and amplification.)doc")
        .def_readwrite("noise_frequency", &ParamsSource::noise_frequency, R"doc(Simplex noise frequency.)doc")
        .def_readwrite("noise_octaves", &ParamsSource::noise_octaves, R"doc(Number of octaves for noise.)doc")
        .def_readwrite("noise_weight", &ParamsSource::noise_weight, R"doc(Weight contributed by noise.)doc")
        // Sections
        .def_readwrite("simulate_sections", &ParamsSource::simulate_sections, R"doc(Enable equivalent section simulation.)doc")
        .def_readwrite("geostat_params", &ParamsSource::geostat_params, R"doc(Geostatistical simulation parameters struct.)doc")
        // Save parameters
        .def_readwrite("create_vset_sampling", &ParamsSource::create_vset_sampling, R"doc(Save sampling point set.)doc")
        .def_readwrite("create_nghb_graph", &ParamsSource::create_nghb_graph, R"doc(Save nearest neighbor graph (large).)doc")
        .def_readwrite("create_nghb_graph_property", &ParamsSource::create_nghb_graph_property, R"doc(Save per-edge property (very large).)doc")
        .def_readwrite("create_solved_connectivity_matrix", &ParamsSource::create_solved_connectivity_matrix, R"doc(Save \"solved\" connectivity matrix (with resolved \"uncertain\" connections))doc")
        .def_readwrite("create_grid", &ParamsSource::create_grid, R"doc(Save grid data.)doc")
        // Properties loaded externally
        .def_readwrite("propdensity", &ParamsSource::propdensity, R"doc(Density property values from domain box.)doc")
        .def_readwrite("propikp", &ParamsSource::propikp, R"doc(Intrinsic karstification potential values.)doc")
        .def_readwrite("propspringsindex", &ParamsSource::propspringsindex, R"doc(Spring property column indices.)doc")
        .def_readwrite("propspringsradius", &ParamsSource::propspringsradius, R"doc(Spring radii.)doc")
        .def_readwrite("propspringssurfindex", &ParamsSource::propspringssurfindex, R"doc(Water table surface index per spring.)doc")
        .def_readwrite("propsinksindex", &ParamsSource::propsinksindex, R"doc(Sink property row indices.)doc")
        .def_readwrite("propsinksorder", &ParamsSource::propsinksorder, R"doc(Sink order (see 2024 paper).)doc")
        .def_readwrite("propsinksradius", &ParamsSource::propsinksradius, R"doc(Sink radii.)doc")
        .def_readwrite("waypoints_radius", &ParamsSource::waypoints_radius, R"doc(Waypoint radii.)doc")
        .def_readwrite("waypoints_impact_radius", &ParamsSource::waypoints_impact_radius, R"doc(Waypoint impact radii.)doc")
        .def_readwrite("sphere_radius", &ParamsSource::sphere_radius, R"doc(Radii of no-karst spheres.)doc")
        .def("__repr__", [](const ParamsSource &)
             { return "ParamsSource()"; });

    // ---------------------------------------------------------------------------
    // Recursive extra bindings: geological + skeleton + network level API
    // ---------------------------------------------------------------------------

    // KeyPointType enum
    py::enum_<KeyPointType>(m, "KeyPointType", R"doc(Enumeration of key point categories used to seed / constrain the karstic network.)doc")
        .value("Sink", KeyPointType::Sink, "Network inlet (sink).")
        .value("Spring", KeyPointType::Spring, "Network outlet (spring).")
        .value("Waypoint", KeyPointType::Waypoint, "Waypoint / known passage.")
        .value("Deadend", KeyPointType::Deadend, "Dead-end node added during amplification.")
        .value("sampling", KeyPointType::sampling, "Sampling cloud point.")
        .export_values();

    // KeyPoint
    py::class_<KeyPoint>(m, "KeyPoint", R"doc(Defines a key point by position, type and optional water table index (for springs).)doc")
        .def(py::init<>(), R"doc(Default uninitialized key point.)doc")
        .def(py::init<const Vector3 &, KeyPointType>(), py::arg("p"), py::arg("type"), R"doc(Construct with position and type.)doc")
        .def(py::init<const Vector3 &, KeyPointType, const int &>(), py::arg("p"), py::arg("type"), py::arg("wt_idx"), R"doc(Construct spring key point with water table index.)doc")
        .def_readwrite("p", &KeyPoint::p, R"doc(3D position.)doc")
        .def_readwrite("type", &KeyPoint::type, R"doc(Key point type.)doc")
        .def_readwrite("wt_idx", &KeyPoint::wt_idx, R"doc(Water table index (springs only).)doc")
        .def("__repr__", [](const KeyPoint &k)
             { return "KeyPoint(p=" + std::to_string(k.p.x) + "," + std::to_string(k.p.y) + "," + std::to_string(k.p.z) + ", type=" + std::to_string(static_cast<int>(k.type)) + ", wt_idx=" + std::to_string(k.wt_idx) + ")"; });

    // CostTerm
    py::class_<CostTerm>(m, "CostTerm", R"doc(Sub-cost component: enabled flag + weight in composite cost function.)doc")
        .def(py::init<>(), R"doc(Default: disabled, weight 0.)doc")
        .def(py::init<bool, float>(), py::arg("used"), py::arg("weight"), R"doc(Construct with usage flag and weight.)doc")
        .def_readwrite("used", &CostTerm::used, R"doc(Enable/disable.)doc")
        .def_readwrite("weight", &CostTerm::weight, R"doc(Relative weight.)doc");

    // PropIdx (nested helper struct used inside GeologicalParameters for property+index pairs)
    py::class_<GeologicalParameters::Propidx>(m, "PropIdx", R"doc(Pair of (prop, index) where prop is a float property value and index references a key point.)doc")
        .def(py::init<>())
        .def_readwrite("prop", &GeologicalParameters::Propidx::prop, R"doc(Float property value.)doc")
        .def_readwrite("index", &GeologicalParameters::Propidx::index, R"doc(Index referencing a key point.)doc")
        .def("__repr__", [](const GeologicalParameters::Propidx &p){ return "PropIdx(prop=" + std::to_string(p.prop) + ", index=" + std::to_string(p.index) + ")"; });

    // Sphere (used in GeologicalParameters::spheres)
    py::class_<Sphere>(m, "Sphere", R"doc(Geometric exclusion / inclusion sphere.)doc")
        .def(py::init<const Vector3 &, float>(), py::arg("center"), py::arg("radius"))
        .def_readwrite("center", &Sphere::center)
        .def_readwrite("radius", &Sphere::radius)
        .def("distance", &Sphere::Distance, py::arg("point"))
        .def("contains", &Sphere::Contains, py::arg("point"))
        .def("random_surface", &Sphere::RandomSurface)
        .def("center_point", &Sphere::Center)
        .def("radius_value", &Sphere::Radius);

    // GeologicalParameters (expose main public attributes)
    py::class_<GeologicalParameters>(m, "GeologicalParameters", R"doc(Container for geological + simulation parameters shared across graph construction and amplification.)doc")
        .def(py::init<>())
        .def_readwrite("scenename", &GeologicalParameters::scenename)
        .def_readwrite("directoryname", &GeologicalParameters::directoryname)
        .def_readwrite("use_amplification", &GeologicalParameters::use_amplification)
        .def_readwrite("max_distance_amplification", &GeologicalParameters::max_distance_amplification)
        .def_readwrite("min_distance_amplification", &GeologicalParameters::min_distance_amplification)
        .def_readwrite("nb_cycles", &GeologicalParameters::nb_cycles)
        .def_readwrite("use_noise", &GeologicalParameters::use_noise)
        .def_readwrite("use_noise_on_all", &GeologicalParameters::use_noise_on_all)
        .def_readwrite("noise_frequency", &GeologicalParameters::noise_frequency)
        .def_readwrite("noise_octaves", &GeologicalParameters::noise_octaves)
        .def_readwrite("noise_weight", &GeologicalParameters::noise_weight)
        .def_readwrite("graphPoissonRadius", &GeologicalParameters::graphPoissonRadius)
        .def_readwrite("graphNeighbourRadius", &GeologicalParameters::graphNeighbourRadius)
        .def_readwrite("maxsize", &GeologicalParameters::maxsize)
        .def_readwrite("stretch_factor", &GeologicalParameters::stretch_factor)
        .def_readwrite("graphuse_max_nghb_radius", &GeologicalParameters::graphuse_max_nghb_radius)
        .def_readwrite("graphNeighbourCount", &GeologicalParameters::graphNeighbourCount)
        .def_readwrite("nb_springs", &GeologicalParameters::nb_springs)
        .def_readwrite("nb_wt", &GeologicalParameters::nb_wt)
        .def_readwrite("nb_inception_surf", &GeologicalParameters::nb_inception_surf)
        .def_readwrite("multiply_costs", &GeologicalParameters::multiply_costs)
        .def_readwrite("allow_single_outlet", &GeologicalParameters::allow_single_outlet)
        .def_readwrite("vadose_cohesion", &GeologicalParameters::vadose_cohesion)
        .def_readwrite("sinks_index", &GeologicalParameters::sinks_index)
        .def_readwrite("fractures_orientations", &GeologicalParameters::fractures_orientations)
        .def_readwrite("fractures_tolerances", &GeologicalParameters::fractures_tolerances)
        .def_readwrite("fractures_max_lengths", &GeologicalParameters::fractures_max_lengths)
        .def_readwrite("max_dist_loops_vadose", &GeologicalParameters::max_dist_loops_vadose)
        .def_readwrite("loop_density_vadose", &GeologicalParameters::loop_density_vadose)
        .def_readwrite("max_dist_loops_phreatic", &GeologicalParameters::max_dist_loops_phreatic)
        .def_readwrite("loop_density_phreatic", &GeologicalParameters::loop_density_phreatic)
        .def_readwrite("use_ghost_rocks", &GeologicalParameters::use_ghost_rocks)
        .def_readwrite("length", &GeologicalParameters::length)
        .def_readwrite("width", &GeologicalParameters::width)
        .def_readwrite("polyline", &GeologicalParameters::polyline)
        .def_readwrite("use_max_depth_constraint", &GeologicalParameters::use_max_depth_constraint)
        .def_readwrite("distanceCost", &GeologicalParameters::distanceCost)
        .def_readwrite("fractureCost", &GeologicalParameters::fractureCost)
        .def_readwrite("horizonCost", &GeologicalParameters::horizonCost)
        .def_readwrite("waterTable1", &GeologicalParameters::waterTable1)
        .def_readwrite("waterTable2", &GeologicalParameters::waterTable2)
        .def_readwrite("karstificationCost", &GeologicalParameters::karstificationCost)
        .def_readwrite("gamma", &GeologicalParameters::gamma)
        .def_readwrite("spheres", &GeologicalParameters::spheres)
        .def_readwrite("waypoints_weight", &GeologicalParameters::waypoints_weight)
        .def_readwrite("waypointsimpactradius", &GeologicalParameters::waypointsimpactradius, R"doc(List[PropIdx]: impact radius entries for waypoints (prop = radius, index = waypoint keypoint index).)doc")
        .def_readwrite("z_list", &GeologicalParameters::z_list, R"doc(List[PropIdx]: Z coordinate entries for each spring (prop = z, index = spring keypoint index).)doc")
        .def_readwrite("propspringswtindex", &GeologicalParameters::propspringswtindex, R"doc(List[PropIdx]: Water table index for each spring (prop = wt index as float, index = spring keypoint index).)doc")
        .def("set_connectivity_matrix", [](GeologicalParameters &self, const std::vector<std::vector<int>> &matrix){
            // Resize internal Array2D to match matrix shape and copy values.
            if(matrix.empty()) return; // allow clearing by passing [] (no change)
            int rows = static_cast<int>(matrix.size());
            int cols = static_cast<int>(matrix[0].size());
            self.connectivity_matrix.resize(rows, cols, 0);
            for(int r=0;r<rows;++r){
                if(static_cast<int>(matrix[r].size()) != cols) throw std::runtime_error("Jagged connectivity matrix");
                for(int c=0;c<cols;++c){
                    self.connectivity_matrix[r][c] = matrix[r][c];
                }
            }
        }, py::arg("matrix"), R"doc(Set sink x spring connectivity matrix (list[list[int]]). Rows = sinks, Cols = springs. Values per C++ semantics (e.g. 0/1 allowed; 2 = use shortest-distance heuristic).)doc");

    // KarsticConnection (needed for KarsticNode.connections vector)
    py::class_<KarsticConnection>(m, "KarsticConnection", R"doc(Connection between skeleton nodes (destination index + final branch id).)doc")
        .def(py::init<>())
        .def_readwrite("destindex", &KarsticConnection::destindex)
        .def_readwrite("final_branch_id", &KarsticConnection::final_branch_id);

    // KarsticNode
    py::class_<KarsticNode>(m, "KarsticNode", R"doc(Node of the karstic skeleton graph: position, per-water-table costs / vadose flags, equivalent radius, branch bookkeeping.)doc")
        .def(py::init<>())
        .def_readwrite("index", &KarsticNode::index)
        .def_readwrite("p", &KarsticNode::p)
        .def_readwrite("cost", &KarsticNode::cost)
        .def_readwrite("vadose", &KarsticNode::vadose)
        .def_readwrite("eq_radius", &KarsticNode::eq_radius)
        .def_readwrite("connections", &KarsticNode::connections)
        .def_readwrite("distance", &KarsticNode::distance)
        .def_readwrite("branch_id", &KarsticNode::branch_id)
        .def_readwrite("branch_id_ascend", &KarsticNode::branch_id_ascend)
        .def("add_branch_id", &KarsticNode::add_branch_id, py::arg("new_branch_id"), R"doc(Merge new branch IDs (deduplicated).)doc");

    // KarsticSkeleton (subset of API; constructors taking GraphOperations not exposed)
    py::class_<KarsticSkeleton>(m, "KarsticSkeleton", R"doc(Simulated karst skeleton: list of KarsticNode with helper analytics.)doc")
        .def(py::init<>(), R"doc(Empty skeleton.)doc")
        .def_readwrite("nodes", &KarsticSkeleton::nodes, R"doc(List of skeleton nodes.)doc")
        .def("compute_nb_cycles", &KarsticSkeleton::compute_nb_cycles)
        .def("compute_mean_branch_length", &KarsticSkeleton::compute_mean_branch_length)
        .def("compute_mean_deviation", &KarsticSkeleton::compute_mean_deviation)
        .def("count_vadose_nodes", &KarsticSkeleton::count_vadose_nodes, py::arg("spring"))
        .def("count_average_vadose_nodes", &KarsticSkeleton::count_average_vadose_nodes);

    // KarsticNetwork binding (high-level façade)
    py::class_<KarsticNetwork>(m, "KarsticNetwork", R"doc(Façade class to configure and run KarstNSim simulations (sampling, graph, skeleton, amplification, section properties).)doc")
        // Only expose a lifetime-safe constructor: copies water_tables list into owned storage.
        .def(py::init([](const std::string &karstic_network_name, Box *box, GeologicalParameters &params,
                         const std::vector<KeyPoint> &keypoints, const std::vector<Surface> &water_tables){
                auto owned_vec = std::make_unique<std::vector<Surface>>(water_tables); // copy
                auto *raw = owned_vec.get();
                g_owned_surface_vectors.push_back(std::move(owned_vec));
                return new KarsticNetwork(karstic_network_name, box, params, keypoints, raw);
            }),
            py::arg("karstic_network_name"), py::arg("box"), py::arg("params"), py::arg("keypoints"), py::arg("water_tables"),
            R"doc(Safe constructor variant: copies provided water table surfaces so their lifetime extends for the duration of the module. Prevents dangling pointer to a temporary Python list.)doc")
        .def("set_sinks", [](KarsticNetwork &self, const std::vector<Vector3> &sinks, const std::vector<int> &indices, const std::vector<int> &order, bool use_radius, const std::vector<float> &radii)
             { self.set_sinks(&sinks, indices, order, use_radius, radii); }, py::arg("sinks"), py::arg("indices"), py::arg("order"), py::arg("use_radius"), py::arg("radii"), R"doc(Add sink key points with ordering + optional radii.)doc")
        .def("set_springs", [](KarsticNetwork &self, const std::vector<Vector3> &springs, const std::vector<int> &indices, bool allow_single_outlet, bool use_radius, const std::vector<float> &radii, const std::vector<int> &wt_indices)
             { self.set_springs(&springs, indices, allow_single_outlet, use_radius, radii, wt_indices); }, py::arg("springs"), py::arg("indices"), py::arg("allow_single_outlet"), py::arg("use_radius"), py::arg("radii"), py::arg("water_table_indices"), R"doc(Add spring key points; couples each spring to its water table index.)doc")
        .def("set_waypoints", [](KarsticNetwork &self, const std::vector<Vector3> &wpts, bool use_radius, const std::vector<float> &radii, const std::vector<float> &impact_radii, float weight)
             { self.set_waypoints(&wpts, use_radius, radii, impact_radii, weight); }, py::arg("waypoints"), py::arg("use_radius"), py::arg("radii"), py::arg("impact_radii"), py::arg("weight"), R"doc(Add waypoint key points with impact radii and global weight.)doc")
        .def("set_deadend_points", &KarsticNetwork::set_deadend_points, py::arg("nb_deadend_points"), py::arg("max_distance"))
        .def("set_previous_networks", &KarsticNetwork::set_previous_networks, py::arg("previous_lines"))
        .def("set_inception_surfaces_sampling", &KarsticNetwork::set_inception_surfaces_sampling, py::arg("network_name"), py::arg("surfaces"), py::arg("refine"), py::arg("create_vset_sampling"))
        .def("set_wt_surfaces_sampling", &KarsticNetwork::set_wt_surfaces_sampling, py::arg("network_name"), py::arg("water_table_surfaces"), py::arg("refine"))
        .def("set_topo_surface", &KarsticNetwork::set_topo_surface, py::arg("topographic_surface"))
        // Safe ownership-preserving variant: copies the surface and stores it so the pointer remains valid.
        .def("safe_set_topo_surface", [](KarsticNetwork &self, const Surface &topographic_surface){
            auto owned = std::make_unique<Surface>(topographic_surface); // copy
            Surface* raw = owned.get();
            g_owned_surfaces.push_back(std::move(owned));
            self.set_topo_surface(raw);
        }, py::arg("topographic_surface"), R"doc(Safe version of set_topo_surface that preserves lifetime of the passed Surface.)doc")
        .def("set_ghost_rocks", &KarsticNetwork::set_ghost_rocks, py::arg("grid"), py::arg("ikp"), py::arg("alteration_lines"), py::arg("interpolate_lines"), py::arg("ghostrock_max_vertical_size"), py::arg("use_max_depth_constraint"), py::arg("ghost_rock_weight"), py::arg("max_depth_horizon"), py::arg("ghostrock_width"))
        .def("set_inception_horizons_parameters", &KarsticNetwork::set_inception_horizons_parameters, py::arg("horizons"), py::arg("weight"))
        // Safe ownership-preserving variant for inception horizons vector.
        .def("safe_set_inception_horizons_parameters", [](KarsticNetwork &self, const std::vector<Surface> &horizons, float weight){
            auto owned_vec = std::make_unique<std::vector<Surface>>(horizons); // copy
            auto *raw = owned_vec.get();
            g_owned_surface_vectors.push_back(std::move(owned_vec));
            self.set_inception_horizons_parameters(raw, weight);
        }, py::arg("horizons"), py::arg("weight"), R"doc(Safe version copying the horizons vector to ensure it lives for the duration of the network.)doc")
        .def("disable_inception_horizon", &KarsticNetwork::disable_inception_horizon)
        .def("set_karstification_potential_parameters", &KarsticNetwork::set_karstification_potential_parameters, py::arg("weight"))
        .def("set_fracture_constraint_parameters", &KarsticNetwork::set_fracture_constraint_parameters, py::arg("orientations"), py::arg("tolerances"), py::arg("weight"))
        .def("disable_fractures", &KarsticNetwork::disable_fractures)
        .def("set_no_karst_spheres_parameters", &KarsticNetwork::set_no_karst_spheres_parameters, py::arg("centers"), py::arg("radii"))
        .def("set_simulation_parameters", &KarsticNetwork::set_simulation_parameters, py::arg("nghb_count"), py::arg("use_max_nghb_radius"), py::arg("nghb_radius"), py::arg("poisson_radius"), py::arg("gamma"), py::arg("multiply_costs"), py::arg("vadose_cohesion"))
        .def("set_domain_geometry", &KarsticNetwork::set_domain_geometry)
        .def("just_sampling", &KarsticNetwork::just_sampling)
    // read_connectivity_matrix removed from Python API; build connectivity in Python via params.connectivity_matrix
        // Wrap noise parameters to hide raw std::mt19937 type from Python API (uses globalRng declared in randomgenerator.h)
        .def("set_noise_parameters", [](KarsticNetwork &self, bool use_noise, bool use_noise_on_all, int frequency, int octaves, float noise_weight){
            self.set_noise_parameters(use_noise, use_noise_on_all, frequency, octaves, noise_weight, globalRng);
        },
        py::arg("use_noise"), py::arg("use_noise_on_all"), py::arg("frequency"), py::arg("octaves"), py::arg("noise_weight"),
        R"doc(Set noise parameters (rng handled internally).)doc")
        .def("create_sections", &KarsticNetwork::create_sections, py::arg("skeleton"))
        .def("run_simulation_properties", &KarsticNetwork::run_simulation_properties, py::arg("skeleton"), py::arg("alteration_lines"), py::arg("use_ghost_rocks"), py::arg("ghostrock_max_vertical_size"), py::arg("use_max_depth_constraint"), py::arg("max_depth_horizon"), py::arg("ghostrock_width"))
        .def("run_simulation", [](KarsticNetwork &self, bool sections_simulation_only, bool create_nghb_graph, bool create_nghb_graph_property, bool create_solved_connectivity_matrix, bool use_amplification, bool use_sampling_points, float fraction_karst_perm, float fraction_old_karst_perm, float max_inception_surface_distance, std::vector<Vector3> &sampling_points, bool create_vset_sampling, bool use_density_property, int k_pts, const std::vector<float> &propdensity, const std::vector<float> &propikp)
             { return self.run_simulation(sections_simulation_only, create_nghb_graph, create_nghb_graph_property, create_solved_connectivity_matrix, use_amplification, use_sampling_points,
                                          fraction_karst_perm, fraction_old_karst_perm, max_inception_surface_distance, &sampling_points, create_vset_sampling,
                                          use_density_property, k_pts, propdensity, propikp); }, py::arg("sections_simulation_only"), py::arg("create_nghb_graph"), py::arg("create_nghb_graph_property"), py::arg("create_solved_connectivity_matrix"), py::arg("use_amplification"), py::arg("use_sampling_points"), py::arg("fraction_karst_perm"), py::arg("fraction_old_karst_perm"), py::arg("max_inception_surface_distance"), py::arg("sampling_points"), py::arg("create_vset_sampling"), py::arg("use_density_property"), py::arg("k_pts"), py::arg("propdensity"), py::arg("propikp"), R"doc(Run full (or sections-only) simulation; returns elapsed wall time (s). sampling_points is updated in-place if used.)doc")
        .def("set_save_directory", &KarsticNetwork::set_save_directory, py::arg("directory"))
        .def("save_painted_box", &KarsticNetwork::save_painted_box, py::arg("propdensity"), py::arg("propikp"))
        .def("set_geostat_params", &KarsticNetwork::set_geostat_params, py::arg("geostat_params"))
        .def("set_amplification_params", &KarsticNetwork::set_amplification_params, py::arg("max_distance"), py::arg("min_distance"), py::arg("nb_cycles"))
        .def("set_amplification_vadose_params", &KarsticNetwork::set_amplification_vadose_params, py::arg("max_dist_loops_vadose"), py::arg("loop_density_vadose"))
        .def("set_amplification_phreatic_params", &KarsticNetwork::set_amplification_phreatic_params, py::arg("max_dist_loops_phreatic"), py::arg("loop_density_phreatic"))
        .def("set_water_table_weight", &KarsticNetwork::set_water_table_weight, py::arg("vadose_weight"), py::arg("phreatic_weight"))
        .def("disable_water_table", &KarsticNetwork::disable_water_table);

    // RNG
    // void initializeRng(const std::vector<std::uint32_t>& seed) from randomgenerator.h (not a class, just a helper)
    m.def("initializeRng", &initializeRng, py::arg("seed"), R"doc(Initializes the random number generator with a given seed.)doc");

    py::add_ostream_redirect(m, "ostream_redirect");
}
