#pragma once
#include "CommonDefs.h"
#include <fstream>

class FileIO {

public:
  static Mesh load_off(std::string);
  static Mesh load_off(std::istream &);
  static Mesh load_off_from_string(const std::string &);
  static void write_off(std::string, const Mesh &);
  static void write_off(std::ostream &, const Mesh &);
  static void write_off_to_bytes(const Mesh &, char **, size_t *);
  static Mesh load_draco_from_bytes(const char *, size_t);
  static void write_draco_to_bytes(const Mesh &, char **, size_t *);
  static Mesh load_from_bytes(const char *, size_t);
  static void write_to_bytes(const Mesh &, char **, size_t *, bool);

private:
};
