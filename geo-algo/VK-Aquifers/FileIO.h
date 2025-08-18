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
  static std::vector<char> write_off_to_bytes(const Mesh &);
  static Mesh load_draco_from_bytes(const char *, size_t);
  static std::vector<char> write_draco_to_bytes(const Mesh &);
  static Mesh load_from_bytes(const char *, size_t);
  static std::vector<char> write_to_bytes(const Mesh &, bool = false);

private:
    // From Draco implementation comments:
    // Sets the desired encoding and decoding speed for the given options.
    //
    //  0 = slowest speed, but the best compression.
    // 10 = fastest, but the worst compression.
    // -1 = undefined.
    //
    // Note that both speed options affect the encoder choice of used methods and
    // algorithms. For example, a requirement for fast decoding may prevent the
    // encoder from using the best compression methods even if the encoding speed
    // is set to 0. In general, the faster of the two options limits the choice of
    // features that can be used by the encoder. Additionally, setting
    // |decoding_speed| to be faster than the |encoding_speed| may allow the
    // encoder to choose the optimal method out of the available features for the
    // given |decoding_speed|.
    static const int DRACO_ENCODING_SPEED = 5;
    static const int DRACO_DECODING_SPEED = 5;
    static const int DRACO_POSITION_QUANTIZATION_BITS = 14;
};
