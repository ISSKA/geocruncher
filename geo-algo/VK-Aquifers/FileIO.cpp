#include "FileIO.h"
#include <sstream>

Mesh FileIO::load_off(std::string filename)
{
  std::ifstream meshFile(filename);
  if (!meshFile) {
    throw std::invalid_argument("The file '" + filename + "' could not be opened.");
  }

  return load_off(meshFile);
}

Mesh FileIO::load_off(std::istream& file)
{
  Mesh mesh;
  if (!file || !(file >> mesh)) {
    throw std::invalid_argument("Invalid input file.");
  }
  if (mesh.is_empty()) {
    throw std::invalid_argument("Invalid input file. Mesh is empty.");
  }
  if (!CGAL::is_triangle_mesh(mesh)) {
    throw std::invalid_argument("Invalid input file. Mesh is not a triangle mesh.");
  }

  return std::move(mesh);
}

Mesh FileIO::load_off_from_string(std::string off)
{
  std::stringstream s(off);
  std::istream& is = static_cast<std::istream&>(s);
  return load_off(is);
}

void FileIO::write_off(std::string filename, Mesh mesh)
{
  std::ofstream meshFile(filename);
  if (!meshFile) {
    throw std::invalid_argument("The file '" + filename + "' could not be opened.");
  }
  write_off(meshFile, mesh);
}

void FileIO::write_off(std::ostream& file, Mesh mesh)
{
  if (!file || !(file << mesh)) {
    throw std::invalid_argument("Invalid output file.");
  }
}

std::string FileIO::write_off_to_string(Mesh mesh)
{
  std::stringstream s;
  std::ostream& os = static_cast<std::ostream&>(s);
  write_off(os, mesh);
  return s.str();
}
