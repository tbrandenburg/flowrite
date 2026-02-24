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