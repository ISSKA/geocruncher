#pragma once
#include "CommonDefs.h"
#include <fstream>

class FileIO {

public:
  static Mesh load_off(std::string);
  static Mesh load_off(std::istream&);
  static Mesh load_off_from_string(std::string);
  static void write_off(std::string, Mesh);
  static void write_off(std::ostream&, Mesh);
  static std::string write_off_to_string(Mesh);

private:

};
