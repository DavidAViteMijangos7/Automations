#include "triage/scan.hpp"

#include <chrono>
#include <cstdint>
#include <filesystem>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

#include "triage/sha256.hpp"

namespace fs = std::filesystem;

namespace triage {
namespace {

struct Entry {
  std::string path;
  std::uint64_t size;
};

double seconds_between(std::chrono::steady_clock::time_point from,
                       std::chrono::steady_clock::time_point to) {
  return std::chrono::duration<double>(to - from).count();
}

}  // namespace

ScanResult scan(const std::string& root) {
  ScanResult result;
  const auto started = std::chrono::steady_clock::now();

  // ---- 1. walk ----------------------------------------------------------
  std::vector<Entry> entries;
  std::error_code ec;
  fs::recursive_directory_iterator it(root, fs::directory_options::skip_permission_denied, ec);
  const fs::recursive_directory_iterator end;
  for (; !ec && it != end; it.increment(ec)) {
    std::error_code entry_ec;
    if (!it->is_regular_file(entry_ec) || entry_ec) {
      continue;
    }
    const std::uintmax_t size = it->file_size(entry_ec);
    if (entry_ec) {
      continue;
    }
    entries.push_back(Entry{it->path().string(), static_cast<std::uint64_t>(size)});
  }
  const auto after_walk = std::chrono::steady_clock::now();

  // ---- 2. bucket by size ------------------------------------------------
  std::unordered_map<std::uint64_t, std::vector<std::size_t>> by_size;
  by_size.reserve(entries.size());
  for (std::size_t i = 0; i < entries.size(); ++i) {
    by_size[entries[i].size].push_back(i);
    result.total_bytes += entries[i].size;
  }
  result.total_files = static_cast<std::uint64_t>(entries.size());

  std::uint64_t solo_by_size = 0;
  for (const auto& bucket : by_size) {
    if (bucket.second.size() == 1u) {
      ++solo_by_size;
    }
  }

  // ---- 3. hash the survivors -------------------------------------------
  std::unordered_map<std::string, std::vector<std::size_t>> by_digest;
  for (const auto& bucket : by_size) {
    if (bucket.second.size() < 2u) {
      continue;
    }
    for (const std::size_t index : bucket.second) {
      const std::string digest = sha256_file(entries[index].path);
      if (digest.empty()) {
        continue;
      }
      by_digest[digest].push_back(index);
      ++result.hashed_files;
      result.hashed_bytes += entries[index].size;
    }
  }
  const auto finished = std::chrono::steady_clock::now();

  // ---- 4. tally ---------------------------------------------------------
  for (const auto& bucket : by_digest) {
    if (bucket.second.size() > 1u) {
      ++result.duplicate_groups;
      const std::uint64_t extra = static_cast<std::uint64_t>(bucket.second.size()) - 1u;
      result.redundant_copies += extra;
      result.redundant_bytes += extra * entries[bucket.second.front()].size;
    }
  }
  result.distinct_contents = solo_by_size + static_cast<std::uint64_t>(by_digest.size());

  result.walk_seconds = seconds_between(started, after_walk);
  result.hash_seconds = seconds_between(after_walk, finished);
  result.total_seconds = seconds_between(started, finished);
  return result;
}

std::string to_json(const ScanResult& result) {
  std::ostringstream out;
  out.setf(std::ios::fixed);
  out.precision(4);
  out << "{\"tool\": \"triage\""
      << ", \"total_files\": " << result.total_files << ", \"total_bytes\": " << result.total_bytes
      << ", \"hashed_files\": " << result.hashed_files
      << ", \"hashed_bytes\": " << result.hashed_bytes
      << ", \"distinct_contents\": " << result.distinct_contents
      << ", \"duplicate_groups\": " << result.duplicate_groups
      << ", \"redundant_copies\": " << result.redundant_copies
      << ", \"redundant_bytes\": " << result.redundant_bytes
      << ", \"walk_seconds\": " << result.walk_seconds
      << ", \"hash_seconds\": " << result.hash_seconds
      << ", \"total_seconds\": " << result.total_seconds << "}";
  return out.str();
}

}  // namespace triage
