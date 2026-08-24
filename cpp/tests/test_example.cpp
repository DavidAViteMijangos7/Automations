#include <gtest/gtest.h>

#include "triage/example.hpp"

TEST(ExampleTest, AddsTwoPositiveNumbers) {
  EXPECT_EQ(triage::add(2, 3), 5);
}

TEST(ExampleTest, AddsNegativeNumbers) {
  EXPECT_EQ(triage::add(-2, -3), -5);
}

TEST(ExampleTest, AddsZero) {
  EXPECT_EQ(triage::add(5, 0), 5);
}
