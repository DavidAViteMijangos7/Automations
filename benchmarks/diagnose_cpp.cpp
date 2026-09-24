// Explains *why* triage loses to xlsreport on the walk phase.
//
// run.py reports the two tools end to end. This isolates the individual
// primitives so the gap can be attributed rather than guessed at.
//
// Build and run (needs the tree from generate_tree.py):
//   g++ -O3 -std=c++20 -I cpp/include benchmarks/diagnose_cpp.cpp \
//       cpp/src/sha256.cpp -o diagnose_cpp
//   ./diagnose_cpp <tree>
//
// The W4 case is Windows-only and is the point of the whole file: it is the
// same OS primitive Python's os.scandir uses, so it shows the floor that
// std::filesystem is leaving on the table.

#include <chrono>
#include <cstdio>
#include <filesystem>
#include <string>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#endif

#include "triage/sha256.hpp"

namespace fs = std::filesystem;
using clk = std::chrono::steady_clock;

namespace {

double secs(clk::time_point from, clk::time_point to) {
  return std::chrono::duration<double>(to - from).count();
}

std::vector<std::string> collect(const std::string& root) {
  std::vector<std::string> paths;
  std::error_code ec;
  for (fs::recursive_directory_iterator
           it(root, fs::directory_options::skip_permission_denied, ec),
       end;
       !ec && it != end; it.increment(ec)) {
    std::error_code entry_ec;
    if (it->is_regular_file(entry_ec) && !entry_ec) {
      paths.push_back(it->path().string());
    }
  }
  return paths;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc < 2) {
    std::fprintf(stderr, "usage: diagnose_cpp <tree>\n");
    return 2;
  }
  const std::string root = argv[1];

  std::printf("== hashing ==\n");
  {
    std::vector<unsigned char> block(256u * 1024u * 1024u, 0xABu);
    const auto t0 = clk::now();
    triage::Sha256 hasher;
    hasher.update(block.data(), block.size());
    const std::string digest = hasher.hex_digest();
    const double t = secs(t0, clk::now());
    std::printf("  scalar SHA-256           : %6.2f s / 256 MiB = %7.1f MiB/s  [%.8s]\n",
                t, 256.0 / t, digest.c_str());
  }

  const std::vector<std::string> paths = collect(root);
  std::printf("== reading (%zu files) ==\n", paths.size());

  {
    const auto t0 = clk::now();
    std::vector<char> buffer(64u * 1024u);
    unsigned long long total = 0;
    for (const std::string& path : paths) {
      std::FILE* file = std::fopen(path.c_str(), "rb");
      if (file == nullptr) continue;
      std::setvbuf(file, nullptr, _IONBF, 0);
      std::size_t got = 0;
      while ((got = std::fread(buffer.data(), 1, buffer.size(), file)) > 0) total += got;
      std::fclose(file);
    }
    const double t = secs(t0, clk::now());
    std::printf("  stdio fread (in use)     : %6.2f s / %6.1f MiB = %7.1f MiB/s (%.3f ms/file)\n",
                t, total / 1048576.0, (total / 1048576.0) / t,
                t * 1000.0 / static_cast<double>(paths.size()));
  }

  std::printf("== walking ==\n");
  {
    const auto t0 = clk::now();
    std::size_t n = 0;
    unsigned long long bytes = 0;
    std::error_code ec;
    for (fs::recursive_directory_iterator
             it(root, fs::directory_options::skip_permission_denied, ec),
         end;
         !ec && it != end; it.increment(ec)) {
      std::error_code entry_ec;
      if (it->is_regular_file(entry_ec)) {
        bytes += it->file_size(entry_ec);
        ++n;
      }
    }
    std::printf("  std::filesystem (in use) : %6.2f s (%zu files, %.1f MiB)\n",
                secs(t0, clk::now()), n, bytes / 1048576.0);
  }

#ifdef _WIN32
  {
    const auto t0 = clk::now();
    std::size_t n = 0;
    unsigned long long bytes = 0;
    std::vector<std::wstring> stack{std::wstring(root.begin(), root.end())};
    while (!stack.empty()) {
      const std::wstring dir = stack.back();
      stack.pop_back();
      WIN32_FIND_DATAW found;
      HANDLE handle = FindFirstFileW((dir + L"\\*").c_str(), &found);
      if (handle == INVALID_HANDLE_VALUE) continue;
      do {
        const std::wstring name = found.cFileName;
        if (name == L"." || name == L"..") continue;
        if (found.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
          stack.push_back(dir + L"\\" + name);
        } else {
          bytes += (static_cast<unsigned long long>(found.nFileSizeHigh) << 32) |
                   found.nFileSizeLow;
          ++n;
        }
      } while (FindNextFileW(handle, &found));
      FindClose(handle);
    }
    std::printf("  Win32 FindFirstFileW     : %6.2f s (%zu files, %.1f MiB)\n",
                secs(t0, clk::now()), n, bytes / 1048576.0);
  }
#endif
  return 0;
}
