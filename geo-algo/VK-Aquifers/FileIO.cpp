#include "FileIO.h"
#include <sstream>
#include <vector>

#include <draco/attributes/geometry_attribute.h>
#include <draco/compression/decode.h>
#include <draco/compression/encode.h>
#include <draco/mesh/mesh.h>
#include <stdexcept>

Mesh FileIO::load_off(std::string filename) {
  std::ifstream meshFile(filename);
  if (!meshFile) {
    throw std::invalid_argument("The file '" + filename +
                                "' could not be opened.");
  }

  return load_off(meshFile);
}

Mesh FileIO::load_off(std::istream &file) {
  Mesh mesh;
  if (!file || !(file >> mesh)) {
    throw std::invalid_argument("Invalid input file.");
  }
  if (mesh.is_empty()) {
    throw std::invalid_argument("Invalid input file. Mesh is empty.");
  }
  if (!CGAL::is_triangle_mesh(mesh)) {
    throw std::invalid_argument(
        "Invalid input file. Mesh is not a triangle mesh.");
  }

  return std::move(mesh);
}

Mesh FileIO::load_off_from_string(const std::string &off) {
  std::stringstream s(off);
  std::istream &is = static_cast<std::istream &>(s);
  return load_off(is);
}

void FileIO::write_off(std::string filename, const Mesh &mesh) {
  std::ofstream meshFile(filename);
  if (!meshFile) {
    throw std::invalid_argument("The file '" + filename +
                                "' could not be opened.");
  }
  write_off(meshFile, mesh);
}

void FileIO::write_off(std::ostream &file, const Mesh &mesh) {
  if (!file || !(file << mesh)) {
    throw std::invalid_argument("Invalid output file.");
  }
}

std::vector<char> FileIO::write_off_to_bytes(const Mesh &mesh) {
  // Generate OFF data into a stringstream
  std::stringstream s;
  write_off(s, mesh); // Write OFF format using CGAL's << operator

  // Directly construct vector from string (no extra copies)
  std::string off_str = s.str();
  return std::vector<char>(off_str.begin(), off_str.end());
}

Mesh FileIO::load_draco_from_bytes(const char *draco_data, size_t size) {
  // Create and initialize decoder buffer
  draco::DecoderBuffer buffer;
  buffer.Init(draco_data, size);

  // Decode the Draco data
  draco::Decoder decoder;
  auto statusor = decoder.DecodeMeshFromBuffer(&buffer);
  if (!statusor.ok()) {
    throw std::invalid_argument("Failed to decode Draco mesh: " +
                                std::string(statusor.status().error_msg()));
  }

  std::unique_ptr<draco::Mesh> draco_mesh = std::move(statusor).value();
  if (draco_mesh->num_faces() == 0) {
    throw std::invalid_argument("Invalid Draco data. Mesh is empty.");
  }

  // Get position attribute
  const draco::PointAttribute *pos_att =
      draco_mesh->GetNamedAttribute(draco::GeometryAttribute::POSITION);
  if (pos_att == nullptr) {
    throw std::invalid_argument("No position attribute in Draco mesh.");
  }

  // Convert to CGAL mesh
  Mesh cgal_mesh;

  // Add all vertices
  switch (pos_att->data_type()) {
  case draco::DataType::DT_FLOAT32:
    if (pos_att->num_components() != 3) {
      throw std::invalid_argument("Error: Invalid number of components in "
                                  "compressed mesh position attribute.");
    }
    if (pos_att->byte_stride() > 16) {
      throw std::invalid_argument("Error: Attribute byte stride is too long");
    }
    for (int v = 0; v < draco_mesh->num_points(); v++) {
      float pos[3];
      pos_att->GetMappedValue(draco::PointIndex(v), &pos[0]);
      cgal_mesh.add_vertex(Point_3(pos[0], pos[1], pos[2]));
    }
    break;
  default:
    throw std::invalid_argument(
        "Error: Invalid data type in compressed mesh position attribute");
    break;
  }

  // Add all faces
  for (int t = 0; t < draco_mesh->num_faces(); ++t) {
    const auto &face = draco_mesh->face(draco::FaceIndex(t));
    std::vector<Mesh::Vertex_index> vertices;
    for (int i = 0; i < 3; ++i) {
      vertices.push_back(Mesh::Vertex_index(face[i].value()));
    }
    cgal_mesh.add_face(vertices[0], vertices[1], vertices[2]);
  }

  // Validate the resulting mesh
  if (cgal_mesh.is_empty()) {
    throw std::invalid_argument("Conversion failed. Resulting mesh is empty.");
  }

  if (!CGAL::is_triangle_mesh(cgal_mesh)) {
    throw std::invalid_argument("Resulting mesh is not a triangle mesh.");
  }

  return cgal_mesh;
}

std::vector<char> FileIO::write_draco_to_bytes(const Mesh &cgal_mesh) {
  // Create Draco mesh
  draco::Mesh draco_mesh;
  const size_t num_vertices = cgal_mesh.number_of_vertices();
  draco_mesh.set_num_points(num_vertices);

  // Add position attribute (3D float coordinates)
  draco::GeometryAttribute pos_att;
  pos_att.Init(draco::GeometryAttribute::POSITION, nullptr, 3,
               draco::DT_FLOAT32, false, sizeof(float) * 3, 0);
  const int pos_att_id = draco_mesh.AddAttribute(pos_att, true, num_vertices);
  if (pos_att_id < 0) {
    throw std::runtime_error(
        "Failed to create position attribute in Draco mesh.");
  }

  // Add vertices to Draco mesh
  for (auto v : cgal_mesh.vertices()) {
    const Point_3 &p = cgal_mesh.point(v);
    float pos[3] = {static_cast<float>(CGAL::to_double(p.x())),
                    static_cast<float>(CGAL::to_double(p.y())),
                    static_cast<float>(CGAL::to_double(p.z()))};
    draco_mesh.attribute(pos_att_id)
        ->SetAttributeValue(draco::AttributeValueIndex(v.idx()), pos);
  }

  // Add faces (triangles) to Draco mesh
  for (auto f : cgal_mesh.faces()) {
    std::vector<draco::PointIndex> indices;
    auto h = cgal_mesh.halfedge(f);
    auto start = h;
    do {
      auto v = cgal_mesh.target(h);
      indices.push_back(draco::PointIndex(v.idx()));
      h = cgal_mesh.next(h);
    } while (h != start);

    if (indices.size() != 3) {
      throw std::invalid_argument("CGAL mesh contains non-triangular faces.");
    }
    draco_mesh.AddFace({{indices[0], indices[1], indices[2]}});
  }

  // Validate before encoding
  if (draco_mesh.num_points() == 0) {
    throw std::invalid_argument("CGAL mesh has no vertices.");
  }
  if (draco_mesh.num_faces() == 0) {
    throw std::invalid_argument("CGAL mesh has no faces.");
  }

  // Encode mesh to Draco buffer
  draco::Encoder encoder;
  encoder.SetSpeedOptions(DRACO_ENCODING_SPEED, DRACO_DECODING_SPEED);
  encoder.SetAttributeQuantization(draco::GeometryAttribute::POSITION,
                                   DRACO_POSITION_QUANTIZATION_BITS);

  draco::EncoderBuffer buffer;
  const draco::Status status = encoder.EncodeMeshToBuffer(draco_mesh, &buffer);
  if (!status.ok()) {
    throw std::runtime_error("Draco encoding failed: " +
                             std::string(status.error_msg()));
  }

  // Efficiently convert to std::vector<char> without extra copies
  const char *data = buffer.data();
  const size_t size = buffer.size();

  // Create vector directly from Draco buffer (move semantics)
  return std::vector<char>(data, data + size);
}

bool is_off_file(const char *data, size_t size) {
  return (size >= 3) && (data[0] == 'O') && (data[1] == 'F') &&
         (data[2] == 'F');
}

Mesh FileIO::load_from_bytes(const char *data, size_t size) {
  if (is_off_file(data, size)) {
    // Convert to string and pass to OFF loader
    std::string off_data(data, size);
    return load_off_from_string(off_data);
  } else {
    // Pass raw bytes to Draco loader
    return load_draco_from_bytes(data, size);
  }
}

std::vector<char> FileIO::write_to_bytes(const Mesh &mesh,
                                         bool use_off = false) {
  if (use_off) {
    return write_off_to_bytes(mesh);
  } else {
    return write_draco_to_bytes(mesh);
  }
}
