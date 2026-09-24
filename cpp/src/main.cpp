#include <iostream>
#include <string>
#include <vector>

#include "triage/scan.hpp"

namespace {

int usage() {
  std::cerr << "usage: triage scan <root> [--json]\n";
  return 2;
}

}  // namespace

int main(int argc, char** argv) {
  const std::vector<std::string> args(argv + 1, argv + argc);
  if (args.size() < 2 || args[0] != "scan") {
    return usage();
  }

  const std::string root = args[1];
  bool as_json = false;
  for (std::size_t i = 2; i < args.size(); ++i) {
    if (args[i] == "--json") {
      as_json = true;
    } else {
      return usage();
    }
  }

  const triage::ScanResult result = triage::scan(root);

  if (as_json) {
    std::cout << triage::to_json(result) << '\n';
    return 0;
  }

  std::cout << "files scanned    : " << result.total_files << '\n'
            << "bytes scanned    : " << result.total_bytes << '\n'
            << "distinct contents: " << result.distinct_contents << '\n'
            << "duplicate groups : " << result.duplicate_groups << '\n'
            << "redundant copies : " << result.redundant_copies << '\n'
            << "reclaimable bytes: " << result.redundant_bytes << '\n'
            << "elapsed          : " << result.total_seconds << "s\n";
  return 0;
}
