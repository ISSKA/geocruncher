#pragma once
#include "CommonDefs.h"

class TestSuite
{
  typedef std::map<Point_3, CGAL::Bbox_3> SpringToBbox;

  struct TestCase {
    std::string name;
    std::vector<std::string> meshFilenames;
    bool withBbox;
    SpringToBbox springToExpectedBbox;

    /*
    Convenience overload for 1 spring
    */
    TestCase(std::string name, std::string meshFilename, Point_3 spring)
      : name(name), meshFilenames({meshFilename}), springToExpectedBbox(SpringToBbox{ {spring, CGAL::Bbox_3()} }), withBbox(false) {}

    TestCase(std::string name, std::vector<std::string> meshFilenames, SpringToBbox springToExpectedBbox)
      : name(name), meshFilenames(meshFilenames), springToExpectedBbox(springToExpectedBbox), withBbox(true) {}

  };

public:
  static int runTests();

private:
  static bool runSimpleTests();
  static bool runSimpleTest(const TestCase& testcase);
  static bool runMultiMeshTests();
  static bool equalsWithTolerance(const CGAL::Bbox_3& bboxReference, const CGAL::Bbox_3& bboxComp, double BBOX_TOLERANCE_FRACTION);
};

