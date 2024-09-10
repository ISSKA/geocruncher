#include "TestSuite.h"
#include "FileIO.h"
#include "AquiferCalc.h"
#include <CGAL/Polygon_mesh_processing/bbox.h>
#include <CGAL/Polygon_mesh_processing/transform.h>

namespace PMP = CGAL::Polygon_mesh_processing;
CGAL::Bbox_3 NULL_BBOX; // Use when assigning a spring to no mesh
const double BBOX_TOLERANCE_FRACTION = 0.02;

const int RETURN_SUCCESS = 0;
const int RETURN_FAIL = 1;

int TestSuite::runTests()
{
  bool success = runSimpleTests() && runMultiMeshTests();
  return success ? RETURN_SUCCESS : RETURN_FAIL;
}

bool TestSuite::runSimpleTests()
{
  std::vector<TestCase> testcases;
  testcases.push_back(TestCase("Tetrahedron","tetrahedron.off", Point_3(0, 0, 0.9)));
  testcases.push_back(TestCase("U-shaped", "U-mesh.off", Point_3(0, 0, 0.55)));
  testcases.push_back(TestCase("U-shaped flipped", {"U-mesh-flipped.off"}, SpringToBbox{ {Point_3(0, 0, -0.7), CGAL::Bbox_3(-0.673691, -0.747661, -1.19409, 1.19535, 0.15274, -0.7)} }));

  {
    Point_3 innerSpring(0.25, -0.25, -0.3);
    Point_3 outerSpring(1, -1, -0.28);
    Point_3 outerSpring2(1, -1, -0.32);
    Point_3 innerOuterJoinedSpring(0.3, 0.4, -0.2);
    CGAL::Bbox_3 innerBox(-0.469237, -0.469237, -0.813492, 0.469237, 0.469237, -0.3);
    CGAL::Bbox_3 outerBox(-1, -1, -1, 1, 1, -0.28);

    testcases.push_back(TestCase("Submesh selection: Check smallest submesh is kept", {"Surrounded-Box.off"}, SpringToBbox{ {innerSpring, innerBox }}));
    testcases.push_back(TestCase("Check surrounding submesh is kept", "Surrounded-Box.off", outerSpring));
    testcases.push_back(TestCase("Check inner and outer parts are kept", "Surrounded-Box.off", innerOuterJoinedSpring));
    testcases.push_back(TestCase("Multiple springs: Check all separate parts are kept", {"Surrounded-Box.off"}, SpringToBbox{ {outerSpring, outerBox}, { innerSpring, innerBox } }));
    testcases.push_back(TestCase("Multiple springs: Check intersecting parts are merged", {"Surrounded-Box.off"}, SpringToBbox{ {outerSpring, outerBox}, { outerSpring2, NULL_BBOX } }));
  }

  // Check that nothing is returned when no meshes generated
  testcases.push_back(TestCase("Tetrahedron Empty Result", {"tetrahedron.off"}, SpringToBbox{ { Point_3(0, 0, -999), NULL_BBOX }}));

  std::vector<bool> testResults;
  for (const TestCase& test : testcases) {
    bool pass = runSimpleTest(test);
    testResults.push_back(pass);
    if (pass) {
      std::cout << "PASSED" << std::endl;
    } else {
      std::cout << "FAILED" << std::endl;
    }
  }

  std::ptrdiff_t numPassed = std::count_if(testResults.cbegin(), testResults.cend(), [](bool b) { return b; });

  std::cout
    << "*****************************************" << std::endl
    << "FINISHED SINGLE MESH TESTS. PASSED " << numPassed << " OF " << testcases.size() << std::endl
    << "*****************************************" << std::endl;

  return testcases.size() == numPassed;
}

bool TestSuite::runSimpleTest(const TestCase& testcase)
{
  const int mesh_id = 1; // The value doesn't matter, just used to assign spring to mesh.

  std::cout
    << "*****************************************" << std::endl
    << "TEST CASE: " << testcase.name << std::endl
    << "*****************************************" << std::endl;

  std::vector<UnitMesh> meshes;
  CGAL::Bbox_3 bboxOriginal;

  for (auto const& meshFilename : testcase.meshFilenames) {
    try {
      UnitMesh unit_mesh(FileIO::load_off("res/" + meshFilename), mesh_id);
      bboxOriginal = PMP::bbox(unit_mesh.mesh);
      meshes.push_back(std::move(unit_mesh));
    }
    catch (const std::exception& ex) {
      std::cout << "Failed to load mesh file: \"" << ex.what() << "\"" << std::endl;
      return false;
    }
  }

  std::vector<Spring> springs;
  int springId = 0;
  for (auto const& mapping : testcase.springToExpectedBbox) {
    springs.push_back(Spring(springId, mapping.first, mesh_id));
    springId++;
  }

  std::cout << "Mesh Bbox3: " << bboxOriginal << std::endl;

  AquiferCalc aquiferCalc(std::move(meshes), std::move(springs));
  auto aquifers = aquiferCalc.calculate();

  const auto& null_bbox_copy = NULL_BBOX;
  const size_t expectedAquifers = testcase.withBbox
    ? std::count_if(testcase.springToExpectedBbox.cbegin(), testcase.springToExpectedBbox.cend(), [&null_bbox_copy](const std::pair<const Point_3, CGAL::Bbox_3>& elem) { return elem.second != null_bbox_copy; })
    : testcase.springToExpectedBbox.size();
  
  if (aquifers.size() < expectedAquifers) {
    std::cout << "Failed. Expected " << expectedAquifers << " aquifers, but only found " << aquifers.size() << std::endl;
    return false;
  }

  for (const auto& aquifer_unit : aquifers) {
    if (!aquifer_unit.has_spring) {
      std::cout << "Failed. An aquifer was returned that has no spring assigned." << std::endl;
      return false;
    }

    const Point_3& spring = aquifer_unit.spring.location;

    // Check bounding box corresponds
    CGAL::Bbox_3 bboxAquifer = PMP::bbox(aquifer_unit.mesh);
    CGAL::Bbox_3 bboxExpected;
    if (testcase.withBbox) {
      bboxExpected = testcase.springToExpectedBbox.at(spring);
    } else {
      // Expected bounding box is the whole bounding box, clipped at Spring Z coordinate.
      bboxExpected = CGAL::Bbox_3(
        bboxOriginal.xmin(), bboxOriginal.ymin(), bboxOriginal.zmin(),
        bboxOriginal.xmax(), bboxOriginal.ymax(), spring.z()
      );
    }
    std::cout << "Spring: " << spring << std::endl;
    std::cout << "Bbox3 actual:   " << bboxAquifer << std::endl;
    std::cout << "Bbox3 expected: " << bboxExpected << std::endl;

    bool bboxCorrect = equalsWithTolerance(bboxExpected, bboxAquifer, BBOX_TOLERANCE_FRACTION);
    if (!bboxCorrect) return false;
  }

  return true;

}

/**
 Verify that water "flows" between connected units.
*/
bool TestSuite::runMultiMeshTests()
{
  std::cout
    << "*****************************************" << std::endl
    << "MULTI MESH TESTS" << std::endl
    << "*****************************************" << std::endl;

  std::cout << "TEST: 2 adjacent boxes. 1 disconnected." << std::endl;

  //
  // Create meshes
  //
  UnitMesh box1(FileIO::load_off("res/box1.off"), 42);

  auto bbox1_orig = PMP::bbox(box1.mesh);
  const double box_size_x = bbox1_orig.xmax() - bbox1_orig.xmin();
  const double box_size_z = bbox1_orig.zmax() - bbox1_orig.zmin();
  auto translate_points = [box_size_x, box_size_z](Point_3& p) { return Point_3(p.x() + box_size_x, p.y(), p.z() - 0.3 * box_size_z); };

  // box2 touches box1
  Mesh box2_mesh(box1.mesh);
  PMP::transform(translate_points, box2_mesh);
  UnitMesh box2(box2_mesh, 101);

  // box3 touches box2
  Mesh box3_mesh(box2.mesh);
  PMP::transform(translate_points, box3_mesh);
  UnitMesh box3(box3_mesh, 213);

  // box4 is disconnected
  Mesh box4_mesh(box1.mesh);
  auto translate_points_far_away = [](Point_3& p) { return Point_3(p.x() + 99, p.y(), p.z()); };
  PMP::transform(translate_points_far_away, box4_mesh);
  UnitMesh box4(box4_mesh, 1337);

  // Assign spring to first box
  const double springZ = (bbox1_orig.zmin() + bbox1_orig.zmax()) * 0.5;
  Spring box1_spring(0, Point_3(bbox1_orig.xmax(), bbox1_orig.ymax(), springZ), box1.unit_id);

  AquiferCalc aquiferCalc(std::move(std::vector<UnitMesh> { box1, box2, box3, box4 }), std::move(std::vector<Spring> { box1_spring }));
  auto aquifers = aquiferCalc.calculate();

  // Validate results
  const std::vector<int> aquifer_unit_ids{ box1.unit_id, box2.unit_id, box3.unit_id };
  if (aquifers.size() == aquifer_unit_ids.size()) {
    std::cout << "OK Number of aquifers: " << aquifers.size() << std::endl;
  } else {
    std::cout << "FAIL Expected " << aquifer_unit_ids.size() << " groundwater bodies, but got " << aquifers.size() << std::endl;
    return false;
  }

  for (int id : aquifer_unit_ids) {
    auto aquiferWithUnitId = std::find_if(aquifers.cbegin(), aquifers.cend(), [id](const UnitMesh& aqui) { return aqui.unit_id == id; });
    if (aquiferWithUnitId == aquifers.cend()) {
      std::cout << "FAIL No aquifer found for unit ID " << id << std::endl;
      return false;
    }
  }

  // Check bbox sizes are correct (original bbox, limited at spring Z)
  for (const auto& aqui : aquifers) {
    Mesh* orig_mesh;
    if (aqui.unit_id == box1.unit_id) {
      orig_mesh = &box1.mesh;
    } else if (aqui.unit_id == box2.unit_id) {
      orig_mesh = &box2.mesh;
    } else if (aqui.unit_id == box3.unit_id) {
      orig_mesh = &box3.mesh;
    } else {
      continue; // Shouldn't happen
    }
    
    auto orig_bbox = PMP::bbox(*orig_mesh);
    CGAL::Bbox_3 expected_bbox(orig_bbox.xmin(), orig_bbox.ymin(), orig_bbox.zmin(), orig_bbox.xmax(), orig_bbox.ymax(), std::min(orig_bbox.zmax(), springZ));
    auto aqui_bbox = PMP::bbox(aqui.mesh);

    if (equalsWithTolerance(expected_bbox, aqui_bbox, BBOX_TOLERANCE_FRACTION)) {
      std::cout << "OK Bbox of aquifer for unit " << aqui.unit_id << std::endl;
    } else {
      std::cout << "FAIL Bbox of aquifer for unit " << aqui.unit_id << "  incorrect" << std::endl;
    }
  }

  return true;
}

bool TestSuite::equalsWithTolerance(const CGAL::Bbox_3& bboxReference, const CGAL::Bbox_3& bboxComp, double BBOX_TOLERANCE_FRACTION)
{
  for (int dim = 0; dim < 3; dim++) {
    double pMin1 = bboxReference.min(dim);
    double pMin2 = bboxComp.min(dim);

    double pMax1 = bboxReference.max(dim);
    double pMax2 = bboxComp.max(dim);

    if (abs(pMin1 - pMin2) > abs(pMin1 * BBOX_TOLERANCE_FRACTION) || abs(pMax1 - pMax2) > abs(pMax1 * BBOX_TOLERANCE_FRACTION)) {
      return false;
    }
  }

  return true;
}
