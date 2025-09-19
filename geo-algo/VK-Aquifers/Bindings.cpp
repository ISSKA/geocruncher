#include <CGAL/Polygon_mesh_processing/triangulate_faces.h>
#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "AquiferCalc.h"
#include "FileIO.h"

namespace py = pybind11;

PYBIND11_MODULE(PyGeoAlgo, m) {
  m.doc() = "GeoAlgo pybind11 python bindings";

  py::class_<AquiferCalc>(m, "AquiferCalc")
      .def(py::init<std::vector<UnitMesh>, std::vector<Spring>>())
      .def("calculate", &AquiferCalc::calculate);

  py::class_<FileIO>(m, "FileIO")
      .def_static("load_from_bytes",
                  [](py::buffer buf) {
                    py::buffer_info info = buf.request();
                    if (info.ndim != 1) {
                      throw std::runtime_error("Expected a 1D buffer");
                    }
                    return FileIO::load_from_bytes(
                        static_cast<const char *>(info.ptr),
                        info.size * info.itemsize);
                  })
      .def_static(
          "write_to_bytes",
          [](const Mesh &mesh, bool use_off) {
            const auto &vec = FileIO::write_to_bytes(mesh, use_off);
            // Convert directly to Python bytes (zero-copy for the view)
            return py::bytes(vec.data(), vec.size());
          },
          py::arg("mesh"), py::arg("use_off") = false);

  py::class_<Point_3>(m, "Point_3").def(py::init<double, double, double>());

  py::class_<Mesh>(m, "Mesh").def("to_numpy", [](const Mesh &mesh) {
    namespace PMP = CGAL::Polygon_mesh_processing;

    // Ensure triangles only
    Mesh copy = mesh;
    PMP::triangulate_faces(copy);

    std::vector<std::array<double, 3>> vertices;
    std::vector<std::array<size_t, 3>> triangles;

    std::unordered_map<Mesh::Vertex_index, size_t> vmap;
    vertices.reserve(copy.number_of_vertices());

    size_t idx = 0;
    for (auto v : copy.vertices()) {
      const auto &p = copy.point(v);
      vertices.push_back({p.x(), p.y(), p.z()});
      vmap[v] = idx++;
    }

    for (auto f : copy.faces()) {
      std::array<size_t, 3> tri;
      int i = 0;
      for (auto v : CGAL::vertices_around_face(copy.halfedge(f), copy)) {
        tri[i++] = vmap[v];
      }
      if (i == 3) {
        triangles.push_back(tri);
      }
    }

    // Return as numpy arrays
    py::array v_np(py::dtype::of<double>(),
                   {(py::ssize_t)vertices.size(), (py::ssize_t)3});
    py::array t_np(py::dtype::of<size_t>(),
                   {(py::ssize_t)triangles.size(), (py::ssize_t)3});

    std::memcpy(v_np.mutable_data(), vertices.data(),
                vertices.size() * 3 * sizeof(double));
    std::memcpy(t_np.mutable_data(), triangles.data(),
                triangles.size() * 3 * sizeof(size_t));

    return py::make_tuple(v_np, t_np);
  });

  py::class_<Spring>(m, "Spring")
      .def(py::init<>())
      .def(py::init<const int &, const Point_3 &, const int &>())
      .def_readwrite("id", &Spring::id)
      .def_readwrite("location", &Spring::location)
      .def_readwrite("meshId", &Spring::meshId);

  py::class_<VkUnitMesh<Mesh>>(m, "UnitMesh")
      .def(py::init<>())
      .def(py::init<const Mesh &>())
      .def(py::init<const VkUnitMesh<Mesh> &>())
      .def(py::init<const Mesh &, const int>())
      .def(py::init<const Mesh &, const int, const Spring &>())
      .def_readwrite("unit_id", &VkUnitMesh<Mesh>::unit_id)
      .def_readwrite("spring", &VkUnitMesh<Mesh>::spring)
      .def_readwrite("volume", &VkUnitMesh<Mesh>::volume)
      .def_readwrite("mesh", &VkUnitMesh<Mesh>::mesh);
}
