#pragma once

#include <cstdint>
#include <string>

namespace triage {

struct ScanResult {
  std::uint64_t total_files = 0;
  std::uint64_t total_bytes = 0;
  std::uint64_t hashed_files = 0;
  std::uint64_t hashed_bytes = 0;
  std::uint64_t distinct_contents = 0;
  std::uint64_t duplicate_groups = 0;
  std::uint64_t redundant_copies = 0;
  std::uint64_t redundant_bytes = 0;
  double walk_seconds = 0.0;
  double hash_seconds = 0.0;
  double total_seconds = 0.0;
};

/// Walks `root`, buckets by size, SHA-256s only the sizes seen more than once,
/// then buckets by digest. Mirrors python/src/xlsreport/scan.py exactly.
ScanResult scan(const std::string& root);

std::string to_json(const ScanResult& result);

}  // namespace triage
