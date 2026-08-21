#include <iostream>

#include "package_name/example.hpp"

int main() {
  const int result = package_name::add(2, 3);
  std::cout << "2 + 3 = " << result << '\n';
  return 0;
}
