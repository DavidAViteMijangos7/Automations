#include <gtest/gtest.h>

#include "package_name/example.hpp"

TEST(ExampleTest, AddsTwoPositiveNumbers) {
  EXPECT_EQ(package_name::add(2, 3), 5);
}

TEST(ExampleTest, AddsNegativeNumbers) {
  EXPECT_EQ(package_name::add(-2, -3), -5);
}

TEST(ExampleTest, AddsZero) {
  EXPECT_EQ(package_name::add(5, 0), 5);
}
