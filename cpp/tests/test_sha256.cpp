#include <gtest/gtest.h>

#include <string>

#include "triage/sha256.hpp"

namespace {

std::string hash_of(const std::string& text) {
  triage::Sha256 hasher;
  hasher.update(reinterpret_cast<const unsigned char*>(text.data()), text.size());
  return hasher.hex_digest();
}

}  // namespace

// Standard NIST/FIPS-180 test vectors.
TEST(Sha256Test, EmptyString) {
  EXPECT_EQ(hash_of(""), "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
}

TEST(Sha256Test, Abc) {
  EXPECT_EQ(hash_of("abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
}

TEST(Sha256Test, FiftySixCharacterMessage) {
  EXPECT_EQ(hash_of("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"),
            "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1");
}

// Exercises the multi-block path and the length-padding overflow branch.
TEST(Sha256Test, OneMillionAs) {
  triage::Sha256 hasher;
  const std::string block(1000, 'a');
  for (int i = 0; i < 1000; ++i) {
    hasher.update(reinterpret_cast<const unsigned char*>(block.data()), block.size());
  }
  EXPECT_EQ(hasher.hex_digest(),
            "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0");
}

TEST(Sha256Test, ChunkedUpdatesMatchSingleUpdate) {
  const std::string text = "the quick brown fox jumps over the lazy dog";
  triage::Sha256 chunked;
  for (const char character : text) {
    chunked.update(reinterpret_cast<const unsigned char*>(&character), 1u);
  }
  EXPECT_EQ(chunked.hex_digest(), hash_of(text));
}

TEST(Sha256Test, MissingFileReturnsEmpty) {
  EXPECT_TRUE(triage::sha256_file("definitely/not/a/real/path.bin").empty());
}
