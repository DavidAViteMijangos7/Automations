#include <gtest/gtest.h>

#include <filesystem>
#include <fstream>
#include <string>

#include "triage/scan.hpp"

namespace fs = std::filesystem;

namespace {

void write_file(const fs::path& path, const std::string& content) {
  fs::create_directories(path.parent_path());
  std::ofstream out(path, std::ios::binary);
  out << content;
}

// Mirrors build_tree() in python/tests/test_scan.py so both suites assert
// the same numbers against the same shape of input.
fs::path build_tree() {
  const fs::path root = fs::temp_directory_path() / "triage_scan_test";
  fs::remove_all(root);
  fs::create_directories(root / "nested" / "deep");
  write_file(root / "a1.txt", "AAAA");
  write_file(root / "nested" / "a2.txt", "AAAA");
  write_file(root / "nested" / "deep" / "a3.txt", "AAAA");
  write_file(root / "b1.bin", "BBBB");
  write_file(root / "nested" / "b2.bin", "BBBB");
  write_file(root / "c1.log", "CCCC");
  write_file(root / "nested" / "deep" / "d1.dat", "DDDDDDDDDD");
  return root;
}

}  // namespace

TEST(ScanTest, CountsMatchKnownTree) {
  const fs::path root = build_tree();
  const triage::ScanResult result = triage::scan(root.string());

  EXPECT_EQ(result.total_files, 7u);
  EXPECT_EQ(result.total_bytes, (4u * 6u) + 10u);
  EXPECT_EQ(result.distinct_contents, 4u);
  EXPECT_EQ(result.duplicate_groups, 2u);
  EXPECT_EQ(result.redundant_copies, 3u);
  EXPECT_EQ(result.redundant_bytes, 12u);

  fs::remove_all(root);
}

TEST(ScanTest, SkipsSizesSeenOnce) {
  const fs::path root = build_tree();
  const triage::ScanResult result = triage::scan(root.string());
  // d1.dat is the only 10-byte file, so the size filter drops it before hashing.
  EXPECT_EQ(result.hashed_files, 6u);
  fs::remove_all(root);
}

TEST(ScanTest, EmptyTree) {
  const fs::path root = fs::temp_directory_path() / "triage_scan_empty";
  fs::remove_all(root);
  fs::create_directories(root);

  const triage::ScanResult result = triage::scan(root.string());
  EXPECT_EQ(result.total_files, 0u);
  EXPECT_EQ(result.duplicate_groups, 0u);
  EXPECT_EQ(result.distinct_contents, 0u);

  fs::remove_all(root);
}

TEST(ScanTest, JsonContainsToolName) {
  const triage::ScanResult result;
  const std::string json = triage::to_json(result);
  EXPECT_NE(json.find("\"tool\": \"triage\""), std::string::npos);
}
