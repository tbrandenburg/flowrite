# Agent Guidelines

## Rules

* **ALWAYS** Keep it simple
* **ALWAYS** Apply smart state-of-the-art library usage for keeping this project only on glue code level
* **AVOID** Writing own code - all own code needs to be laboriously maintained and introduces new bugs - we want to avoid that

## Testing Protocol

* **MANDATORY** Run `make test` after any code changes to ensure no regressions
* **MANDATORY** All tests must pass before committing changes
* The test suite includes both unit tests (pytest) and integration tests (workflow simulations)
* Any new functionality must include corresponding test coverage