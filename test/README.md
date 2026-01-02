# Homely Automated Tests

## Organisation

**Unit Tests** focus on demonstrating working behaviour of a specific module.
These are located in `test/unit/` and should match the name of the module they
test. These should use mocks where necessary to maintain fast performance and
low overhead.

**Feature Tests** demonstrate working behaviour of a specific part of Homely's
public-facing API, such as `homely.files.*()`. These should just test the most
important aspects of the feature - unit tests should be used to comprehensively
test edge cases of each feature.

**System Tests** demonstrate working behaviour of the Homely CLI, treating it
as a "black box". These should just test the most import aspects of the CLI -
unit tests should be used to comprehensively test edge cases of the CLI.


## Running tests

To run all tests under all valid python versions, run `bin/all_tests_containerised.sh ALL`.
