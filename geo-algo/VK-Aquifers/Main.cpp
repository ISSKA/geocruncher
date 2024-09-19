#include "CommonDefs.h"
#include "FileIO.h"
#include "AquiferCalc.h"
#include "TestSuite.h"
#include <string>
#include <sstream>
#include "Main.h"

/**
  Determines the groundwater bodies based on meshes and their springs. Reads commands from stdin.
  Mesh format: OFF
  Usage:
  """
  Mesh {id} {filename}
  Spring {spring id} {mesh id} {x} {y} {z}
  ...
  Compute {output directory}
  """
*/
int main(int argc, char *argv[])
{
  if (argc == 2 && strcmp(argv[1], "runTests") == 0) {
    return TestSuite::runTests();
  }

  typedef std::pair<std::string, int> MeshfileAndId;

  auto& input = std::cin;
  auto& output = std::cout;

  std::vector<MeshfileAndId> mesh_file_and_id;
  std::vector<Spring> springs;
  std::string targetDir;

  while (true) {
    std::string line;
    std::getline(input, line);
    std::istringstream iss(line);

    std::string cmd;
    iss >> cmd;

    if (cmd == "Mesh") {
      std::string mesh_file;
      int mesh_id;
      iss >> mesh_id >> mesh_file;
      mesh_file_and_id.push_back(MeshfileAndId(mesh_file, mesh_id));

    } else if(cmd == "Spring") {
      int spring_id;
      int spring_mesh_id;
      double springX, springY, springZ;
      iss >> spring_id >> spring_mesh_id >> springX >> springY >> springZ;
      springs.push_back(Spring(spring_id, Point_3(springX, springY, springZ), spring_mesh_id));

    } else if(cmd == "Compute") {
      iss >> targetDir;
      std::vector<UnitMesh> meshes;
      for (const auto& entry : mesh_file_and_id) {
        try {
          UnitMesh mesh(FileIO::load_off(entry.first), entry.second);
          meshes.push_back(std::move(mesh));
        } catch (const std::exception& ex) {
          std::cerr << "Failed to load mesh file " << entry.second << ": \"" << ex.what() << "\"" << std::endl;
          return -1;
        }
      }

      AquiferCalc aquiferCalc(std::move(meshes), std::move(springs));
      std::vector<UnitMesh> aquifers;
      try {
        aquifers = aquiferCalc.calculate();
      } catch (const std::exception& ex) {
        std::cerr << "Failed to compute aquifers: \"" << ex.what() << "\"" << std::endl;
        return -1;
      }

      int i = 0;
      for (auto& aquifer : aquifers) {
        std::ostringstream targetFile;
        replaceAll(targetDir, "\\", "\\\\"); // Escape backslashes for path in JSON string
        targetFile << targetDir << "/aquifer_" << i << ".off";
        FileIO::write_off(targetFile.str(), aquifer.mesh);
        output << "{ "
          << "\"file\": \"" << targetFile.str() << "\", "
          << "\"unitId\": " << aquifer.unit_id << ", "
          << "\"springId\": " << aquifer.spring.id << ", "
          << "\"volume\": " << aquifer.volume
          << " }"
          << std::endl;
        i++;
      }

      if (i == 0) {
        std::cerr << "Could not generate any aquifer mesh. Number of springs: " << springs.size() << std::endl;
        return -1;
      }

      return 0;
    } else {
      std::cerr << "Invalid command" << std::endl;
    }
  }

}

void replaceAll(std::string& str, const std::string& from, const std::string& to) {
  if (from.empty())
    return;
  size_t start_pos = 0;
  while ((start_pos = str.find(from, start_pos)) != std::string::npos) {
    str.replace(start_pos, from.length(), to);
    start_pos += to.length(); // In case 'to' contains 'from', like replacing 'x' with 'yx'
  }
}
