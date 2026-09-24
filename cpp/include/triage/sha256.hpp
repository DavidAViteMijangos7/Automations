#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

namespace triage {

/// Streaming SHA-256. Portable scalar C++ — no external dependencies, which
/// keeps the CMake build self-contained. See benchmarks/results.md for what
/// that costs relative to Python's OpenSSL-backed hashlib.
class Sha256 {
 public:
  Sha256();

  void update(const unsigned char* data, std::size_t len);

  /// Finalizes the hash and returns it as 64 lowercase hex characters.
  /// The object must not be updated after this call.
  std::string hex_digest();

 private:
  void transform(const unsigned char* chunk);

  std::uint32_t state_[8];
  std::uint64_t bitlen_;
  unsigned char buffer_[64];
  std::size_t buflen_;
};

/// Hashes a file in 64 KiB chunks. Returns an empty string if it cannot be read.
std::string sha256_file(const std::string& path);

}  // namespace triage
