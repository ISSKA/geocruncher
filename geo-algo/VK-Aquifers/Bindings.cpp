#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "AquiferCalc.h"
#include "FileIO.h"

namespace py = pybind11;

PYBIND11_MODULE(PyGeoAlgo, m) {
    m.doc() = "GeoAlgo pybind11 python bindings";

    py::class_<AquiferCalc>(m, "AquiferCalc")
        .def(py::init<std::vector<UnitMesh>&&, std::vector<Spring>&&>())
        .def("calculate", &AquiferCalc::calculate);

    py::class_<FileIO>(m, "FileIO")
        .def_static("load_from_bytes", [](py::buffer buf) {
            py::buffer_info info = buf.request();
            if (info.ndim != 1) {
                throw std::runtime_error("Expected a 1D buffer");
            }
            return FileIO::load_from_bytes(
                static_cast<const char*>(info.ptr), 
                info.size * info.itemsize
            );
        })
        .def_static("write_to_bytes", [](const Mesh &mesh, bool use_off) {
            char* data = nullptr;
            size_t size = 0;
            FileIO::write_to_bytes(mesh, &data, &size, use_off);
        
            // Use pybind11's capsule to auto-delete the data when Python is done
            py::capsule free_when_done(data, [](void* f) {
                delete[] static_cast<char*>(f);
            });
        
            return py::bytes(data, size);  // Convert to Python bytes
        }, py::arg("mesh"), py::arg("use_off") = false);

    py::class_<Point_3>(m, "Point_3")
        .def(py::init<double, double, double>());

    py::class_<Mesh>(m, "Mesh");

    py::class_<Spring>(m, "Spring")
        .def(py::init<>())
        .def(py::init<const int&, const Point_3&, const int&>())
        .def_readwrite("id", &Spring::id)
        .def_readwrite("location", &Spring::location)
        .def_readwrite("meshId", &Spring::meshId);

    py::class_<VkUnitMesh<Mesh>>(m, "UnitMesh")
        .def(py::init<>())
        .def(py::init<const Mesh&>())
        .def(py::init<const VkUnitMesh<Mesh>&>())
        .def(py::init<const Mesh&, const int>())
        .def(py::init<const Mesh&, const int, const Spring&>())
        .def_readwrite("unit_id", &VkUnitMesh<Mesh>::unit_id)
        .def_readwrite("spring", &VkUnitMesh<Mesh>::spring)
        .def_readwrite("volume", &VkUnitMesh<Mesh>::volume)
        .def_readwrite("mesh", &VkUnitMesh<Mesh>::mesh);
}
