name: Simple Parallel Workflow (loop semantics explained)

on:
  push:
    branches: [ main ]

jobs:
  setup:
    name: Setup and decision job
    runs-on: ubuntu-latest
    outputs:
      run_extra: ${{ steps.decide.outputs.run_extra }}
    steps:
      - name: Setup step
        run: echo "Running setup job"

      - name: Decide whether to run job B
        id: decide
        run: |
          echo "run_extra=true" >> "$GITHUB_OUTPUT"
          echo "Setup decided run_extra=true"

  job_a:
    name: Parallel job A
    runs-on: ubuntu-latest
    needs: setup
    steps:
      - run: echo "Running job A"

  job_b:
    name: Parallel job B (job-level + step-level loops)
    runs-on: ubuntu-latest
    needs: setup
    if: needs.setup.outputs.run_extra == 'true'

    # --------------------------------------------------
    # JOB-LEVEL LOOP (retry semantics)
    # --------------------------------------------------
    loop:
      # success()
      # → returns true if the *previous job attempt* completed successfully
      # → classic retry-until-success behavior
      # → safest and most predictable job-level loop
      until: success()

      # cancelled()
      # → returns true if the workflow or job was manually cancelled
      # → allows immediate exit instead of retrying
      # → typically implicit, but explicit here for clarity
      #
      # failure()
      # → returns true if the previous job attempt failed
      # → usually NOT used with retries, but can be used to stop-on-failure
      #
      # NOTE: only ONE `until` would exist in real syntax;
      # these are shown together for explanation purposes.
      max_iterations: 3

    steps:
      - name: Job B attempt start
        run: echo "Starting job B attempt"

      # --------------------------------------------------
      # STEP-LEVEL LOOP (polling semantics)
      # --------------------------------------------------
      - name: Poll external condition
        id: poll
        loop:
          # success()
          # → step completed successfully (exit code 0)
          # → useful for retrying flaky commands
          #
          # failure()
          # → step failed (non-zero exit)
          # → useful for retry-until-failure testing scenarios
          #
          # cancelled()
          # → workflow or job was cancelled
          # → lets the loop exit early
          #
          # Variable-based conditions (recommended for polling):
          until: env.POLL_STATUS == 'COMPLETE'
          max_iterations: 5
        run: |
          echo "Polling inside job B..."
          echo "POLL_STATUS=COMPLETE" >> "$GITHUB_ENV"
          echo "POLL_STATUS is now $POLL_STATUS"

      - name: Check completion signal
        id: check
        run: |
          echo "status=COMPLETE" >> "$GITHUB_OUTPUT"
          echo "Job-level completion signaled"

  final:
    name: Final aggregation job
    runs-on: ubuntu-latest
    needs: [job_a, job_b]
    if: always()
    steps:
      - run: echo "Running final job"

# --------------------------------------------------
# FOREACH LOOPS (iteration semantics) - NEW FEATURE
# --------------------------------------------------

# FOREACH provides iteration capabilities that complement the existing
# `until` loop semantics. While `until` loops are for retry/polling,
# `foreach` loops are for processing lists of items.

# STEP-LEVEL FOREACH EXAMPLE:
  foreach_step_example:
    name: Process Files with Step-Level Foreach
    runs-on: ubuntu-latest
    steps:
      - name: Process each file individually
        loop:
          # Execute this step once for each item in the list
          # Items can be newline-separated or space-separated
          foreach: "file1.txt file2.txt file3.txt"
          max_iterations: 10  # Safety limit
        run: |
          echo "Processing: $FOREACH_ITEM"
          echo "Index: $FOREACH_INDEX"
          echo "Iteration: $FOREACH_ITERATION"

# JOB-LEVEL FOREACH EXAMPLE:
  foreach_job_example:
    name: Deploy to Environment
    runs-on: ubuntu-latest
    loop:
      # Execute entire job once for each environment
      foreach: "dev staging prod"
      max_iterations: 5
    steps:
      - name: Deploy
        run: |
          echo "Deploying to: $FOREACH_ITEM"
          echo "Environment index: $FOREACH_INDEX"

# FOREACH PARSING RULES:
# 1. Smart auto-detection:
#    - "a b c"        → ["a", "b", "c"] (space-separated)
#    - "a\nb\nc"      → ["a", "b", "c"] (newline-separated)
#    - "file 1\nfile 2" → ["file 1", "file 2"] (preserves spaces within items)
#
# 2. GitHub Actions expressions supported:
#    foreach: ${{ steps.setup.outputs.file_list }}
#    foreach: ${{ needs.job.outputs.items }}
#
# 3. Environment variables during execution:
#    - FOREACH_ITEM: Current item being processed
#    - FOREACH_INDEX: Zero-based index (0, 1, 2, ...)
#    - FOREACH_ITERATION: One-based iteration number (1, 2, 3, ...)
#
# 4. Mutual exclusion with `until`:
#    ❌ Cannot use both `until` and `foreach` in same loop configuration
#
# 5. GitHub Actions compatibility:
#    ✅ Full compatibility with existing GitHub Actions workflow syntax
#    ✅ Standard variable substitution patterns
#    ✅ Compatible with needs.job.outputs and env variables