#pragma once
#include "CommonDefs.h"

class AquiferCalc {
public:
  AquiferCalc(std::vector<UnitMesh> meshes, std::vector<Spring> springs);
  std::vector<UnitMesh> calculate();

private:
  std::vector<UnitMesh> meshes;
  std::vector<Spring> springs;

  bool isMeshValid(const Mesh& mesh);
  std::vector<UnitMesh> findConnectedGroundwaterBodyParts(const UnitMesh& init_source, const Spring& spring);
  std::vector<Mesh> findConnectedComponents(Mesh& mesh);
  void cutMeshZ(Mesh& mesh, double maxZ);
  void keepClosestSubmeshOnly(Mesh& mesh, const Point_3& point);
  Mesh::Face_index findClosestFace(const Mesh& mesh, const Point_3& point);

};
