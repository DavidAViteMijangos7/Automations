#include <iostream>

#include "triage/example.hpp"

int main() {
  const int result = triage::add(2, 3);
  std::cout << "2 + 3 = " << result << '\n';
  return 0;
}
