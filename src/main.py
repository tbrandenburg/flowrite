#!/usr/bin/env python3
"""
Flowrite Workflow Executor - YAML-based temporal workflow execution
Supports parallel jobs, conditionals, loops, and data passing.
"""

import asyncio
import logging
import os
import sys
import time
from datetime import timedelta
from typing import Dict, Any

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker

from .types import (
    Config,
    JobDefinition,
    StepResult,
    JobOutput,
    WorkflowResult,
    JobStatus,
)
from .dsl import WorkflowParser, ConditionEvaluator, DependencyResolver, OutputParser
from .utils import BashExecutor, VariableSubstitution, ConfigLoader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global configuration
config = Config()


@activity.defn
async def execute_job_step(
    job_id: str, step_name: str, command: str, env_vars: Dict[str, str]
) -> StepResult:
    """Execute a single job step"""
    logger.info(f"Executing step '{step_name}' in job {job_id}")

    if not command:
        return StepResult(success=True)

    executor = BashExecutor(config.activity_timeout_seconds)
    success, stdout, stderr, env_updates = executor.execute(command, env_vars)

    # Parse outputs
    outputs = OutputParser.parse_github_output(command)
    outputs.update(OutputParser.parse_github_env(command))

    return StepResult(
        success=success, outputs=outputs, error=stderr if not success else None
    )


@activity.defn
async def evaluate_condition(
    condition: str, job_outputs: Dict[str, Dict[str, Any]], env_vars: Dict[str, str]
) -> bool:
    """Evaluate job condition"""
    return ConditionEvaluator.evaluate_job_condition(condition, job_outputs, env_vars)


@workflow.defn
class JobWorkflow:
    @workflow.run
    async def run(
        self, job_id: str, job_def: JobDefinition, env_vars: Dict[str, str]
    ) -> JobOutput:
        """Execute a complete job with retry logic"""
        logger.info(f"Starting job: {job_id}")

        max_attempts = job_def.loop.max_iterations if job_def.loop else 1

        for attempt in range(max_attempts):
            try:
                all_outputs = {}

                # Execute each step
                for step in job_def.steps:
                    step_max = step.loop.max_iterations if step.loop else 1

                    for step_attempt in range(step_max):
                        # Substitute variables in command
                        command = VariableSubstitution.substitute(
                            step.run or "", env_vars
                        )

                        result = await workflow.execute_activity(
                            execute_job_step,
                            args=[
                                job_id,
                                step.name or f"step-{len(all_outputs)}",
                                command,
                                env_vars,
                            ],
                            start_to_close_timeout=timedelta(
                                seconds=config.step_timeout_seconds
                            ),
                        )

                        if result.success:
                            all_outputs.update(result.outputs)
                            # Update environment with step outputs
                            if step.id:
                                for key, value in result.outputs.items():
                                    env_vars[f"STEP_{step.id}_{key}".upper()] = str(
                                        value
                                    )
                            break
                        else:
                            # Check step loop condition
                            if step.loop:
                                should_continue = (
                                    not ConditionEvaluator.evaluate_loop_condition(
                                        step.loop.until or "",
                                        step_attempt + 1,
                                        step_max,
                                        result.success,
                                        env_vars,
                                    )
                                )
                                if should_continue and step_attempt < step_max - 1:
                                    continue

                            if step_attempt == step_max - 1:
                                raise Exception(f"Step failed: {result.error}")

                return JobOutput(
                    job_id=job_id, status=JobStatus.COMPLETED, outputs=all_outputs
                )

            except Exception as e:
                logger.error(f"Job {job_id} attempt {attempt + 1} failed: {e}")

                # Check job loop condition
                if job_def.loop:
                    should_continue = not ConditionEvaluator.evaluate_loop_condition(
                        job_def.loop.until or "",
                        attempt + 1,
                        max_attempts,
                        False,
                        env_vars,
                    )
                    if should_continue and attempt < max_attempts - 1:
                        await asyncio.sleep(1)
                        continue

                if attempt == max_attempts - 1:
                    return JobOutput(
                        job_id=job_id, status=JobStatus.FAILED, error=str(e)
                    )

        # Should not reach here
        return JobOutput(
            job_id=job_id,
            status=JobStatus.FAILED,
            error="Unexpected workflow termination",
        )


@workflow.defn
class WorkflowExecutor:
    @workflow.run
    async def run(self, workflow_file: str) -> WorkflowResult:
        """Execute complete workflow"""
        # Parse workflow
        workflow_def = WorkflowParser.load_from_file(workflow_file)

        # Validate
        errors = WorkflowParser.validate(workflow_def)
        if errors:
            raise Exception(f"Workflow validation failed: {', '.join(errors)}")

        logger.info(f"Starting workflow: {workflow_def.name}")

        # Initialize execution state
        completed = set()
        job_outputs = {}
        env_vars = dict(os.environ)

        # Load configuration from environment
        env_config = ConfigLoader.from_env()
        global config
        config = Config(**ConfigLoader.from_dict(env_config, config.__dict__))

        # Main execution loop
        while len(completed) < len(workflow_def.jobs):
            # Get ready jobs
            ready_jobs = DependencyResolver.get_ready_jobs(
                workflow_def, completed, job_outputs, env_vars
            )

            if not ready_jobs:
                remaining = set(workflow_def.jobs.keys()) - completed
                if remaining:
                    logger.error(f"Dependency cycle or unmet conditions: {remaining}")
                    break
                else:
                    break

            # Execute jobs in parallel
            handles = []
            for job_id in ready_jobs:
                job_def = workflow_def.jobs[job_id]

                # Check if condition to skip
                if job_def.if_condition:
                    condition_met = await workflow.execute_activity(
                        evaluate_condition,
                        args=[job_def.if_condition, job_outputs, env_vars],
                        start_to_close_timeout=timedelta(
                            seconds=config.eval_timeout_seconds
                        ),
                    )

                    if not condition_met:
                        job_outputs[job_id] = JobOutput(
                            job_id=job_id, status=JobStatus.SKIPPED
                        ).__dict__
                        completed.add(job_id)
                        continue

                # Start job workflow
                handle = await workflow.start_child_workflow(
                    JobWorkflow.run,
                    args=[job_id, job_def, env_vars],
                    id=f"job-{job_id}-{workflow.info().workflow_id}",
                    task_queue="flowrite-jobs",
                )
                handles.append((job_id, handle))

            # Wait for completion and collect results
            for job_id, handle in handles:
                try:
                    result = await handle
                    job_outputs[job_id] = result.__dict__

                    # Update global environment with job outputs
                    for key, value in result.outputs.items():
                        env_vars[f"JOB_{job_id.upper()}_{key.upper()}"] = str(value)

                except Exception as e:
                    logger.error(f"Job {job_id} failed: {e}")
                    job_outputs[job_id] = JobOutput(
                        job_id=job_id, status=JobStatus.FAILED, error=str(e)
                    ).__dict__

                completed.add(job_id)

        # Build final result
        final_job_outputs = {}
        for job_id, output_dict in job_outputs.items():
            final_job_outputs[job_id] = JobOutput(**output_dict)

        return WorkflowResult(
            workflow_name=workflow_def.name,
            status=JobStatus.COMPLETED,
            jobs=final_job_outputs,
        )


class LocalEngine:
    """Local execution mode - real bash execution without Temporal server"""

    def __init__(self, config: Config):
        self.config = config

    async def run_workflow(self, workflow_file: str) -> WorkflowResult:
        """Run workflow in local mode with real command execution"""
        # Parse workflow
        workflow_def = WorkflowParser.load_from_file(workflow_file)

        # Validate
        errors = WorkflowParser.validate(workflow_def)
        if errors:
            raise Exception(f"Workflow validation failed: {', '.join(errors)}")

        logger.info(f"LOCAL: Starting workflow {workflow_def.name}")

        # Initialize execution state
        completed = set()
        job_outputs = {}
        env_vars = dict(os.environ)
        executor = BashExecutor()

        # Main execution loop
        while len(completed) < len(workflow_def.jobs):
            # Get ready jobs
            ready_jobs = DependencyResolver.get_ready_jobs(
                workflow_def, completed, job_outputs, env_vars
            )

            if not ready_jobs:
                remaining = set(workflow_def.jobs.keys()) - completed
                if remaining:
                    # Get detailed diagnostics
                    diagnostics = DependencyResolver.get_job_diagnostics(
                        workflow_def, completed, job_outputs, env_vars
                    )

                    # Categorize the issues
                    waiting_for_deps = []
                    condition_failed = []

                    for job_id, diag in diagnostics.items():
                        if diag["status"] == "waiting_for_dependencies":
                            waiting_for_deps.append(
                                f"{job_id} (needs: {diag['missing_dependencies']})"
                            )
                        elif diag["status"] == "condition_not_met":
                            condition_failed.append(
                                f"{job_id} (if: {diag['condition_details']['expression']})"
                            )

                    # Provide detailed error message and handle unmet conditions
                    if waiting_for_deps and condition_failed:
                        logger.error(
                            f"Jobs blocked - Dependencies: {waiting_for_deps}, Conditions: {condition_failed}"
                        )
                        # Mark jobs with unmet conditions as skipped
                        for job_id, diag in diagnostics.items():
                            if diag["status"] == "condition_not_met":
                                job_outputs[job_id] = {
                                    "job_id": job_id,
                                    "status": "skipped",
                                    "outputs": {},
                                }
                                completed.add(job_id)
                        # Continue the loop to see if we can process the remaining jobs
                        continue
                    elif waiting_for_deps:
                        logger.error(
                            f"Jobs waiting for dependencies: {waiting_for_deps}"
                        )
                    elif condition_failed:
                        logger.error(f"Jobs with unmet conditions: {condition_failed}")
                        # Mark jobs with unmet conditions as skipped
                        for job_id, diag in diagnostics.items():
                            if diag["status"] == "condition_not_met":
                                job_outputs[job_id] = {
                                    "job_id": job_id,
                                    "status": "skipped",
                                    "outputs": {},
                                }
                                completed.add(job_id)
                        # Continue the loop to see if we can process the remaining jobs
                        continue
                    else:
                        logger.error(f"Unknown blocking issue with jobs: {remaining}")

                    break
                else:
                    break

            # Execute jobs (real bash execution)
            for job_id in ready_jobs:
                job_def = workflow_def.jobs[job_id]

                # Check condition
                if job_def.if_condition:
                    condition_met = ConditionEvaluator.evaluate_job_condition(
                        job_def.if_condition, job_outputs, env_vars
                    )
                    if not condition_met:
                        logger.info(f"LOCAL: Skipping {job_id} (condition not met)")
                        job_outputs[job_id] = {
                            "job_id": job_id,
                            "status": "skipped",
                            "outputs": {},
                        }
                        completed.add(job_id)
                        continue

                logger.info(f"LOCAL: Executing job {job_id}")
                all_outputs = {}
                job_failed = False
                error_message = None

                # Execute steps with real bash commands
                step_outputs = {}  # Track outputs by step id
                for step in job_def.steps:
                    if step.run and not job_failed:
                        command = VariableSubstitution.substitute(step.run, env_vars)

                        # KEY DIFFERENCE: Use real execution with retry logic
                        max_retries = getattr(self.config, "max_retries", 3)
                        outputs = {}  # Initialize outputs
                        step_succeeded = False

                        for attempt in range(max_retries + 1):
                            try:
                                success, stdout, stderr, env_updates = executor.execute(
                                    command, env_vars, working_dir=os.getcwd()
                                )

                                if success:
                                    # Parse outputs from env_updates (GITHUB_OUTPUT/GITHUB_ENV)
                                    outputs = env_updates
                                    all_outputs.update(outputs)
                                    step_succeeded = True
                                    break
                                elif attempt < max_retries:
                                    logger.warning(
                                        f"LOCAL: Retry {attempt + 1}/{max_retries} for command: {command[:50]}..."
                                    )
                                    await asyncio.sleep(
                                        2**attempt
                                    )  # Exponential backoff
                                else:
                                    logger.error(
                                        f"LOCAL: Step failed in job {job_id}: {stderr}"
                                    )
                                    job_failed = True
                                    error_message = f"Command failed after {max_retries + 1} attempts: {stderr}"
                                    break
                            except Exception as e:
                                if attempt == max_retries:
                                    logger.error(
                                        f"LOCAL: Step execution error in job {job_id}: {e}"
                                    )
                                    job_failed = True
                                    error_message = f"Execution error after {max_retries + 1} attempts: {e}"
                                    break
                                logger.warning(
                                    f"LOCAL: Execution attempt {attempt + 1} failed: {e}"
                                )
                                await asyncio.sleep(2**attempt)

                        # Track step outputs by step id (only if step succeeded)
                        if step_succeeded and step.id:
                            step_outputs[step.id] = outputs
                            # Update environment for step references
                            for key, value in outputs.items():
                                env_vars[f"STEP_{step.id}_{key}".upper()] = str(value)

                # Process job-level output mappings
                job_level_outputs = {}
                if job_def.outputs and not job_failed:
                    for output_name, output_expression in job_def.outputs.items():
                        # Handle ${{ steps.step_id.outputs.key }} patterns
                        if "${{" in output_expression:
                            # Extract step reference: ${{ steps.deps.outputs.ready }}
                            import re

                            step_pattern = (
                                r"\$\{\{\s*steps\.(\w+)\.outputs\.(\w+)\s*\}\}"
                            )
                            match = re.search(step_pattern, output_expression)
                            if match:
                                step_id = match.group(1)
                                output_key = match.group(2)
                                if (
                                    step_id in step_outputs
                                    and output_key in step_outputs[step_id]
                                ):
                                    job_level_outputs[output_name] = step_outputs[
                                        step_id
                                    ][output_key]
                        else:
                            # Direct value or variable substitution
                            job_level_outputs[output_name] = (
                                VariableSubstitution.substitute(
                                    output_expression, env_vars
                                )
                            )

                # Combine step outputs and job-level mapped outputs
                final_outputs = {**all_outputs, **job_level_outputs}

                # Store job result (failed or completed)
                job_status = "failure" if job_failed else "completed"
                job_outputs[job_id] = {
                    "job_id": job_id,
                    "status": job_status,
                    "outputs": final_outputs,
                    "error": error_message if job_failed else None,
                }

                # Update global environment (only if job succeeded)
                if not job_failed:
                    for key, value in final_outputs.items():
                        env_vars[f"JOB_{job_id.upper()}_{key.upper()}"] = str(value)

                completed.add(job_id)
                # No artificial delay for local execution

        # Build final result and determine overall status
        final_job_outputs = {}
        workflow_failed = False

        for job_id, output_dict in job_outputs.items():
            if isinstance(output_dict, dict):
                job_status_str = output_dict.get("status", "completed")
                # Map string status to JobStatus enum
                if job_status_str == "failure":
                    job_status = JobStatus.FAILED
                    workflow_failed = True
                elif job_status_str == "skipped":
                    job_status = JobStatus.SKIPPED
                else:  # "completed" or other success statuses
                    job_status = JobStatus.COMPLETED

                final_job_outputs[job_id] = JobOutput(
                    job_id=output_dict.get("job_id", job_id),
                    status=job_status,
                    outputs=output_dict.get("outputs", {}),
                    error=output_dict.get("error"),
                )

        overall_status = JobStatus.FAILED if workflow_failed else JobStatus.COMPLETED

        return WorkflowResult(
            workflow_name=workflow_def.name,
            status=overall_status,
            jobs=final_job_outputs,
        )


async def run_temporal(yaml_file: str) -> WorkflowResult:
    """Run with Temporal server"""
    client = await Client.connect(config.temporal_server)
    return await client.execute_workflow(
        WorkflowExecutor.run,
        yaml_file,
        id=f"workflow-{os.getpid()}",
        task_queue="flowrite-main",
    )


async def start_worker():
    """Start Temporal worker"""
    client = await Client.connect(config.temporal_server)

    main_worker = Worker(
        client,
        task_queue="flowrite-main",
        workflows=[WorkflowExecutor],
        activities=[evaluate_condition],
    )

    job_worker = Worker(
        client,
        task_queue="flowrite-jobs",
        workflows=[JobWorkflow],
        activities=[execute_job_step],
    )

    await asyncio.gather(main_worker.run(), job_worker.run())


def main():
    """Main CLI entry point"""
    global config

    if len(sys.argv) < 2:
        print("Usage: python -m src.main <command> [args]")
        print("Commands:")
        print("  worker                      - Start Temporal worker")
        print("  run <yaml> [--local]        - Execute workflow locally (real bash)")
        print(
            "  run <yaml>                  - Execute workflow with Temporal (distributed)"
        )
        print("  create-sample               - Create sample YAML")
        return

    # Load configuration
    env_config = ConfigLoader.from_env()
    config = Config(**ConfigLoader.from_dict(env_config, config.__dict__))

    command = sys.argv[1]

    if command == "worker":
        asyncio.run(start_worker())

    elif command == "run" and len(sys.argv) > 2:
        yaml_file = sys.argv[2]
        if not os.path.exists(yaml_file):
            print(f"Error: {yaml_file} not found")
            return

        local_mode = "--local" in sys.argv

        mode_desc = "(local)" if local_mode else "(temporal)"
        print(f"Executing {yaml_file} {mode_desc}")

        try:
            if local_mode:
                engine = LocalEngine(config)
                result = asyncio.run(engine.run_workflow(yaml_file))
            else:
                result = asyncio.run(run_temporal(yaml_file))

            print("SUCCESS!")
            print(f"Workflow: {result.workflow_name}")
            print(f"Status: {result.status.value}")
            print("Jobs:")
            for job_id, job_output in result.jobs.items():
                print(f"  {job_id}: {job_output.status.value}")
                if job_output.outputs:
                    for key, value in job_output.outputs.items():
                        print(f"    {key}={value}")

        except ValueError as e:
            # User-friendly errors (YAML parsing, validation, etc.)
            print(f"ERROR: {e}")
        except Exception as e:
            print(f"FAILED: {e}")
            import traceback

            traceback.print_exc()

    elif command == "create-sample":
        sample_content = """name: Simple Parallel Workflow (loop semantics explained)

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
    loop:
      until: success()
      max_iterations: 3
    steps:
      - name: Job B attempt start
        run: echo "Starting job B attempt"

      - name: Poll external condition
        id: poll
        loop:
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
"""
        with open("sample_workflow.yaml", "w") as f:
            f.write(sample_content)
        print("Created sample_workflow.yaml")

    else:
        print("Invalid command")


if __name__ == "__main__":
    main()
