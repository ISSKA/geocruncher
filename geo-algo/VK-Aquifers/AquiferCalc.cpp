#include "AquiferCalc.h"
#include <CGAL/Polygon_mesh_processing/connected_components.h>
#include <CGAL/Polygon_mesh_processing/measure.h>
#include <CGAL/Polygon_mesh_processing/clip.h>
#include <CGAL/AABB_face_graph_triangle_primitive.h>
#include <CGAL/AABB_traits.h>
#include <CGAL/AABB_tree.h>
#include <CGAL/exceptions.h>
#include <CGAL/boost/graph/helpers.h>
#include <queue>

typedef CGAL::AABB_face_graph_triangle_primitive<Mesh> AABB_primitive;
typedef CGAL::AABB_traits<Kernel, AABB_primitive> AABB_traits;
typedef CGAL::AABB_tree<AABB_traits> AABB_tree;

namespace PMP = CGAL::Polygon_mesh_processing;

/**
Groundwater Body Algorithm

Each spring is assigned to a mesh representing a geological unit.
Each groundwater body is determined by one principal spring, and the water from
the spring may propagate from its assigned unit to adjacent units.

Main
-----
Input: Springs, Unit Meshes

1. Sort springs by Z coordinate, descending
2. For each spring:
  2.1 Compute aquifer on the spring's unit mesh
  2.2 If aquifer is contained in existing groundwater body, skip
  2.2 Else: Propagate from the found aquifer to adjacent unit meshes -> Groundwater Body for spring

Propagation
------------
Input: Spring, Origin (aquifer mesh belonging to spring)

1. Cut all unit meshes at Z coordinate of Spring
2. Candidates: All unit meshes except origin
3. Work queue: For each candidate 'C', add flow (Origin, C) to queue
4. Take (Source, Target) from queue until empty
  4.1 If Source and Target intersect:
    4.1.1 Add Target to this groundwater body
    4.1.2 Remove Target from Candidates
    4.1.3 For each candidate 'C', add flow (target, C)
5. Return groundwater body  

*/

/**
* meshes: List of triangle meshes. The meshes must be closed and manifold.
* spring_to_mesh: location of a spring and its assignment to a mesh ID. Invalid mesh IDs will throw a exception during calculation.
*/
AquiferCalc::AquiferCalc(std::vector<UnitMesh> meshes, std::vector<Spring> springs)
  : meshes(std::move(meshes)), springs(std::move(springs)) { }


/**
* Find the aquifers for all the meshes. Connected meshes are considered as one.
* Returns meshes of all aquifers in no specific order.
*/
std::vector<UnitMesh> AquiferCalc::calculate()
{
  std::vector<UnitMesh> aquifers;
  std::sort(springs.begin(), springs.end(), [](const Spring& s1, const Spring& s2) { return s1.location.z() > s2.location.z(); });

  for (const auto& spring : springs) {
    int unit_mesh_id = spring.meshId;

    auto it = std::find_if(meshes.cbegin(), meshes.cend(), [&unit_mesh_id](const UnitMesh& m) { return m.unit_id == unit_mesh_id; });
    if (it == meshes.cend()) {
      std::string msg("Spring to mesh assignment: Invalid mesh ID " + std::to_string(unit_mesh_id));
      throw std::runtime_error(msg.c_str());
    }

    if (!isMeshValid((*it).mesh)) {
      std::string msg("Mesh " + std::to_string((*it).unit_id) + " is not closed. This leads to incorrect results. Aborting.");
      throw std::runtime_error(msg.c_str());
    }

    UnitMesh init_aquifer(*it); // Create a copy
    cutMeshZ(init_aquifer.mesh, spring.location.z());
    if (init_aquifer.mesh.number_of_faces() == 0) {
      continue;
    }

    keepClosestSubmeshOnly(init_aquifer.mesh, spring.location);  // Cutting may result in multiple meshes. Keep the one closest to the spring
    // Check if overlaps with existing aquifer. Cancel if so.
    bool does_intersect = std::find_if(aquifers.cbegin(), aquifers.cend(),
      [&init_aquifer](const UnitMesh& other) { return PMP::do_intersect(init_aquifer.mesh, other.mesh); }
    ) != aquifers.cend();
    if (does_intersect) {
      continue; // This aquifer is part of a larger one, skip it. [Guaranteed due to springs being sorted]
    }
    
    // Propagate spring from init aquifer to touching units
    std::vector<UnitMesh> groundwater_body = findConnectedGroundwaterBodyParts(init_aquifer, spring);
    aquifers.insert(aquifers.cend(), groundwater_body.begin(), groundwater_body.end());
  }

  for (auto& aquifer : aquifers) {
    aquifer.volume = PMP::volume(aquifer.mesh);
  }
  
  return aquifers;
}

bool AquiferCalc::isMeshValid(const Mesh& mesh) {
  return CGAL::is_closed(mesh);
}


std::vector<UnitMesh> AquiferCalc::findConnectedGroundwaterBodyParts(const UnitMesh& init_source, const Spring& spring) {
  typedef std::shared_ptr<const UnitMesh> UnitPtr;
  typedef std::pair<UnitPtr, UnitPtr> SourceToTargetFlow;

  std::vector<UnitPtr> candidates;
  candidates.reserve(meshes.size());
  std::vector<UnitMesh> aquifers; // Result

  // Cut across all unit meshes at height of spring
  for (const auto& u : meshes) {
    Mesh mesh_copy(u.mesh);
    cutMeshZ(mesh_copy, spring.location.z());
    std::vector<Mesh> components = findConnectedComponents(mesh_copy);

    for (const auto& m : components) {
      UnitMesh um(m, u.unit_id, spring);
      candidates.push_back(std::move(std::make_shared<const UnitMesh>(um)));
    }
  }

  // Start the queue with the source mesh
  auto origin_ptr = std::make_shared<const UnitMesh>(init_source);
  std::queue<SourceToTargetFlow> worklist;
  for (const auto& c : candidates) {
    SourceToTargetFlow f(origin_ptr, c);
    worklist.emplace(f);
  }

  while (!worklist.empty()) {
    const auto& flow = worklist.front();
    const auto& origin = flow.first;
    const auto& target = flow.second;
    auto targetItr = std::find(candidates.begin(), candidates.end(), target);
    if (targetItr != candidates.end()) {
      if (PMP::do_intersect(origin->mesh, target->mesh)) {
        aquifers.push_back(*target);
        candidates.erase(targetItr);
        // Add worklist items: (Target, c) for each c in candidates
        for (const auto& c : candidates) {
          SourceToTargetFlow f(target, c);
          worklist.emplace(f);
        }
      }
    }

    worklist.pop();
  }

  return aquifers;
}

std::vector<Mesh> AquiferCalc::findConnectedComponents(Mesh& mesh) {
  const std::string facemap_name = "f:ConnectedComponent";
  auto pm_pair = mesh.add_property_map<Mesh::Face_index, std::size_t>(facemap_name);
  auto face_component_map = pm_pair.first;
  const size_t num_components = PMP::connected_components(mesh, face_component_map);

  std::vector<Mesh> components;
  components.reserve(num_components);
  for (size_t id = 0; id < num_components; id++) {
    Mesh component(mesh);
    // Important: We need to work on a new copy of the property map, otherwise it's overwritten.
    PMP::keep_connected_components(component, std::vector<size_t>{ id }, component.property_map<Mesh::Face_index, std::size_t>(facemap_name).first);
    component.collect_garbage();
    components.push_back(std::move(component));
  }  

  return components;
}

/**
* Cuts mesh so that all points are at or below specified Z coordinate. Holes in the mesh are closed.
*/
void AquiferCalc::cutMeshZ(Mesh& mesh, double maxZ) {

  Kernel::Point_3 p(0, 0, maxZ);
  Kernel::Vector_3 up(0, 0, 1);
  Kernel::Plane_3 plane(p, up);

  PMP::clip(mesh, plane, PMP::parameters::clip_volume(true));
  mesh.collect_garbage();  // This actually removes the clipped elements. Critical.
}

void AquiferCalc::keepClosestSubmeshOnly(Mesh& mesh, const Point_3& point)
{
  Mesh::Face_index closestFace = findClosestFace(mesh, point);
  std::vector<Mesh::Face_index> keepFaces;

  PMP::connected_component(closestFace, mesh, std::back_inserter(keepFaces));
  PMP::keep_connected_components(mesh, keepFaces);
}

Mesh::Face_index AquiferCalc::findClosestFace(const Mesh& mesh, const Point_3& point)
{
  AABB_tree tree(mesh.faces_begin(), mesh.faces_end(), mesh);
  tree.accelerate_distance_queries();

  Point_3 closestPoint;
  Mesh::Face_index closestFace;
  std::tie(closestPoint, closestFace) = tree.closest_point_and_primitive(point);

  assert(closestFace != mesh.null_face());
  return closestFace;
}
