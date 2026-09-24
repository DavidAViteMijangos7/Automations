#include "triage/sha256.hpp"

#include <cstdio>
#include <cstring>
#include <vector>

namespace triage {
namespace {

constexpr std::uint32_t kK[64] = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u, 0x3956c25bu, 0x59f111f1u, 0x923f82a4u,
    0xab1c5ed5u, 0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u, 0x72be5d74u, 0x80deb1feu,
    0x9bdc06a7u, 0xc19bf174u, 0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu, 0x2de92c6fu,
    0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau, 0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u,
    0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u, 0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu,
    0x53380d13u, 0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u, 0xa2bfe8a1u, 0xa81a664bu,
    0xc24b8b70u, 0xc76c51a3u, 0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u, 0x19a4c116u,
    0x1e376c08u, 0x2748774cu, 0x34b0bcb5u, 0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
    0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u, 0x90befffau, 0xa4506cebu, 0xbef9a3f7u,
    0xc67178f2u};

constexpr std::size_t kReadChunk = 64u * 1024u;

inline std::uint32_t rotr(std::uint32_t value, std::uint32_t bits) {
  return (value >> bits) | (value << (32u - bits));
}

}  // namespace

Sha256::Sha256() : bitlen_(0), buflen_(0) {
  state_[0] = 0x6a09e667u;
  state_[1] = 0xbb67ae85u;
  state_[2] = 0x3c6ef372u;
  state_[3] = 0xa54ff53au;
  state_[4] = 0x510e527fu;
  state_[5] = 0x9b05688cu;
  state_[6] = 0x1f83d9abu;
  state_[7] = 0x5be0cd19u;
  std::memset(buffer_, 0, sizeof(buffer_));
}

void Sha256::transform(const unsigned char* chunk) {
  std::uint32_t w[64];
  for (std::size_t i = 0; i < 16; ++i) {
    const std::size_t base = i * 4u;
    w[i] = (static_cast<std::uint32_t>(chunk[base]) << 24) |
           (static_cast<std::uint32_t>(chunk[base + 1u]) << 16) |
           (static_cast<std::uint32_t>(chunk[base + 2u]) << 8) |
           static_cast<std::uint32_t>(chunk[base + 3u]);
  }
  for (std::size_t i = 16; i < 64; ++i) {
    const std::uint32_t s0 = rotr(w[i - 15u], 7u) ^ rotr(w[i - 15u], 18u) ^ (w[i - 15u] >> 3u);
    const std::uint32_t s1 = rotr(w[i - 2u], 17u) ^ rotr(w[i - 2u], 19u) ^ (w[i - 2u] >> 10u);
    w[i] = w[i - 16u] + s0 + w[i - 7u] + s1;
  }

  std::uint32_t a = state_[0];
  std::uint32_t b = state_[1];
  std::uint32_t c = state_[2];
  std::uint32_t d = state_[3];
  std::uint32_t e = state_[4];
  std::uint32_t f = state_[5];
  std::uint32_t g = state_[6];
  std::uint32_t h = state_[7];

  for (std::size_t i = 0; i < 64; ++i) {
    const std::uint32_t big_s1 = rotr(e, 6u) ^ rotr(e, 11u) ^ rotr(e, 25u);
    const std::uint32_t choice = (e & f) ^ (~e & g);
    const std::uint32_t temp1 = h + big_s1 + choice + kK[i] + w[i];
    const std::uint32_t big_s0 = rotr(a, 2u) ^ rotr(a, 13u) ^ rotr(a, 22u);
    const std::uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
    const std::uint32_t temp2 = big_s0 + majority;

    h = g;
    g = f;
    f = e;
    e = d + temp1;
    d = c;
    c = b;
    b = a;
    a = temp1 + temp2;
  }

  state_[0] += a;
  state_[1] += b;
  state_[2] += c;
  state_[3] += d;
  state_[4] += e;
  state_[5] += f;
  state_[6] += g;
  state_[7] += h;
}

void Sha256::update(const unsigned char* data, std::size_t len) {
  std::size_t offset = 0;

  if (buflen_ > 0) {
    const std::size_t need = 64u - buflen_;
    const std::size_t take = (len < need) ? len : need;
    std::memcpy(buffer_ + buflen_, data, take);
    buflen_ += take;
    offset += take;
    if (buflen_ == 64u) {
      transform(buffer_);
      bitlen_ += 512u;
      buflen_ = 0;
    }
  }

  for (; offset + 64u <= len; offset += 64u) {
    transform(data + offset);
    bitlen_ += 512u;
  }

  if (offset < len) {
    std::memcpy(buffer_, data + offset, len - offset);
    buflen_ = len - offset;
  }
}

std::string Sha256::hex_digest() {
  const std::uint64_t total_bits = bitlen_ + (static_cast<std::uint64_t>(buflen_) * 8u);

  std::size_t i = buflen_;
  buffer_[i++] = 0x80u;
  if (i > 56u) {
    while (i < 64u) {
      buffer_[i++] = 0u;
    }
    transform(buffer_);
    i = 0;
  }
  while (i < 56u) {
    buffer_[i++] = 0u;
  }
  for (std::size_t j = 0; j < 8u; ++j) {
    const std::uint32_t shift = static_cast<std::uint32_t>(56u - (8u * j));
    buffer_[56u + j] = static_cast<unsigned char>((total_bits >> shift) & 0xFFu);
  }
  transform(buffer_);

  static const char kHex[] = "0123456789abcdef";
  std::string out;
  out.reserve(64u);
  for (std::size_t k = 0; k < 8u; ++k) {
    for (std::uint32_t shift = 24u;; shift -= 8u) {
      const std::uint32_t byte = (state_[k] >> shift) & 0xFFu;
      out.push_back(kHex[byte >> 4u]);
      out.push_back(kHex[byte & 0x0Fu]);
      if (shift == 0u) {
        break;
      }
    }
  }
  return out;
}

std::string sha256_file(const std::string& path) {
  std::FILE* file = std::fopen(path.c_str(), "rb");
  if (file == nullptr) {
    return std::string();
  }

  // std::ifstream measured ~10x slower than stdio here (see
  // benchmarks/results.md). We do our own 64 KiB buffering, so switch stdio
  // buffering off rather than pay for a second copy of every byte.
  std::setvbuf(file, nullptr, _IONBF, 0);

  static thread_local std::vector<unsigned char> buffer(kReadChunk);
  Sha256 hasher;
  std::size_t got = 0;
  while ((got = std::fread(buffer.data(), 1, buffer.size(), file)) > 0) {
    hasher.update(buffer.data(), got);
  }
  std::fclose(file);
  return hasher.hex_digest();
}

}  // namespace triage
