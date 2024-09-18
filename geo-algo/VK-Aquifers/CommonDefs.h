#pragma once
#include <CGAL/Exact_predicates_inexact_constructions_kernel.h>
#include <CGAL/Surface_mesh.h>
#include <boost/shared_ptr.hpp>

// Primitives
typedef CGAL::Exact_predicates_inexact_constructions_kernel Kernel;
typedef Kernel::Point_3 Point_3;
typedef Kernel::Vector_3 Vector_3;

struct Spring {
  int id;
  Point_3 location;
  int meshId;

  Spring() = default;
  Spring(const int& id, const Point_3& location, const int& meshId): id(id), location(location), meshId(meshId) {}
};

// Mesh
template <typename MeshType>
class VkUnitMesh {
private:

public:
  VkUnitMesh() = default;
  
  VkUnitMesh(const MeshType& mesh) : unit_id(-1), has_spring(false), volume(0.0) {
    this->mesh = mesh;
  }

  VkUnitMesh(const VkUnitMesh& other) : unit_id(other.unit_id), spring(other.spring), has_spring(other.has_spring), volume(other.volume) {
    this->mesh = other.mesh;
  }

  VkUnitMesh(const MeshType& mesh, const int unit_id) : unit_id(unit_id), has_spring(false), volume(0.0) {
    this->mesh = mesh;
  }

  VkUnitMesh(const MeshType& mesh, const int unit_id, const Spring& spring) : unit_id(unit_id), spring(spring), has_spring(true), volume(0.0) {
    this->mesh = mesh;
  }

  // TODO Make const & add accessors?
  int unit_id;
  Spring spring;
  bool has_spring;
  double volume;
  MeshType mesh;
};

typedef CGAL::Surface_mesh<Point_3> Mesh;
typedef VkUnitMesh<Mesh> UnitMesh;
