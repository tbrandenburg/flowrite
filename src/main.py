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
import click
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

    # Log command output for visibility
    if stdout.strip():
        # Filter out the special parsing markers
        clean_lines = []
        in_output_section = False
        for line in stdout.split('\n'):
            if line.strip() == "=== GITHUB_OUTPUT ===":
                in_output_section = True
            elif line.strip() == "=== END ===":
                in_output_section = False
            elif not in_output_section and line.strip() and "GITHUB_" not in line:
                clean_lines.append(line)
        
        if clean_lines:
            for line in clean_lines:
                if line.strip():
                    logger.info(f"TEMPORAL: {line}")

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


@activity.defn
async def get_environment_vars() -> Dict[str, str]:
    """Get environment variables (non-deterministic operation)"""
    return dict(os.environ)


@activity.defn
async def get_workflow_id() -> str:
    """Generate workflow ID (non-deterministic operation)"""
    return f"workflow-{os.getpid()}"


@activity.defn
async def load_workflow_file(workflow_file: str) -> dict:
    """Load and parse workflow file (non-deterministic operation)"""
    if not os.path.exists(workflow_file):
        raise FileNotFoundError(f"Workflow file not found: {workflow_file}")

    workflow_def = WorkflowParser.load_from_file(workflow_file)
    errors = WorkflowParser.validate(workflow_def)
    if errors:
        raise Exception(f"Workflow validation failed: {', '.join(errors)}")

    # Return as dict to allow serialization
    return {
        "name": workflow_def.name,
        "jobs": {
            job_id: {
                "name": job.name,
                "steps": [
                    {
                        "name": step.name,
                        "run": step.run,
                        "id": step.id,
                        "loop": step.loop.__dict__ if step.loop else None,
                    }
                    for step in job.steps
                ],
                "needs": job.needs,
                "if_condition": job.if_condition,
                "loop": job.loop.__dict__ if job.loop else None,
            }
            for job_id, job in workflow_def.jobs.items()
        },
    }


@workflow.defn(sandboxed=False)
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
                    job_id=job_id, status=JobStatus.COMPLETED.value, outputs=all_outputs
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
                        job_id=job_id, status=JobStatus.FAILED.value, error=str(e)
                    )

        # Should not reach here
        return JobOutput(
            job_id=job_id,
            status=JobStatus.FAILED.value,
            error="Unexpected workflow termination",
        )


@workflow.defn(sandboxed=False)
class WorkflowExecutor:
    @workflow.run
    async def run(self, workflow_file: str) -> WorkflowResult:
        """Execute complete workflow"""
        # Parse workflow directly (file I/O is deterministic for our use case)
        workflow_def = WorkflowParser.load_from_file(workflow_file)

        # Validate
        errors = WorkflowParser.validate(workflow_def)
        if errors:
            raise Exception(f"Workflow validation failed: {', '.join(errors)}")

        # Get environment variables using activity
        env_vars = await workflow.execute_activity(
            get_environment_vars, start_to_close_timeout=timedelta(seconds=10)
        )

        logger.info(f"Starting workflow: {workflow_def.name}")

        # Initialize execution state
        completed = set()
        job_outputs = {}

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
                            job_id=job_id, status=JobStatus.SKIPPED.value
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
                        job_id=job_id, status=JobStatus.FAILED.value, error=str(e)
                    ).__dict__

                completed.add(job_id)

        # Build final result
        final_job_outputs = {}
        for job_id, output_dict in job_outputs.items():
            final_job_outputs[job_id] = JobOutput(**output_dict)

        return WorkflowResult(
            workflow_name=workflow_def.name,
            status=JobStatus.COMPLETED.value,
            jobs=final_job_outputs,
        )


class LocalEngine:
    """Local execution mode - real bash execution without Temporal server"""

    def __init__(self, config: Config):
        self.config = config

    async def run_workflow(self, workflow_file: str) -> WorkflowResult:
        """Run workflow in local mode with real command execution"""
        workflow_def = self._parse_and_validate_workflow(workflow_file)
        completed, job_outputs, env_vars, executor = self._initialize_execution_state(
            workflow_def
        )

        # Main execution loop
        while len(completed) < len(workflow_def.jobs):
            ready_jobs, should_break = await self._get_ready_jobs_with_diagnostics(
                workflow_def, completed, job_outputs, env_vars
            )

            if should_break:
                break

            # Execute ready jobs
            for job_id in ready_jobs:
                await self._execute_job(
                    job_id, workflow_def, job_outputs, env_vars, executor, completed
                )

        return self._build_final_result(workflow_def, job_outputs)

    def _parse_and_validate_workflow(self, workflow_file: str):
        """Parse and validate workflow definition"""
        workflow_def = WorkflowParser.load_from_file(workflow_file)
        errors = WorkflowParser.validate(workflow_def)
        if errors:
            raise Exception(f"Workflow validation failed: {', '.join(errors)}")

        logger.info(f"LOCAL: Starting workflow {workflow_def.name}")
        return workflow_def

    def _initialize_execution_state(self, workflow_def):
        """Initialize execution state variables"""
        completed = set()
        job_outputs = {}
        env_vars = dict(os.environ)
        executor = BashExecutor()
        return completed, job_outputs, env_vars, executor

    async def _get_ready_jobs_with_diagnostics(
        self, workflow_def, completed, job_outputs, env_vars
    ):
        """Get ready jobs and handle diagnostics for blocked jobs"""
        ready_jobs = DependencyResolver.get_ready_jobs(
            workflow_def, completed, job_outputs, env_vars
        )

        if not ready_jobs:
            remaining = set(workflow_def.jobs.keys()) - completed
            if remaining:
                return await self._handle_blocked_jobs(
                    workflow_def, completed, job_outputs, env_vars
                )
            else:
                return [], True  # No more jobs, should break

        return ready_jobs, False  # Continue processing

    async def _handle_blocked_jobs(
        self, workflow_def, completed, job_outputs, env_vars
    ):
        """Handle jobs that are blocked by dependencies or conditions"""
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

        # Handle different blocking scenarios
        if waiting_for_deps and condition_failed:
            logger.error(
                f"Jobs blocked - Dependencies: {waiting_for_deps}, Conditions: {condition_failed}"
            )
            self._mark_condition_failed_jobs_as_skipped(
                diagnostics, job_outputs, completed
            )
            return [], False  # Continue to process remaining jobs
        elif waiting_for_deps:
            logger.error(f"Jobs waiting for dependencies: {waiting_for_deps}")
        elif condition_failed:
            logger.error(f"Jobs with unmet conditions: {condition_failed}")
            self._mark_condition_failed_jobs_as_skipped(
                diagnostics, job_outputs, completed
            )
            return [], False  # Continue to process remaining jobs
        else:
            remaining = set(workflow_def.jobs.keys()) - completed
            logger.error(f"Unknown blocking issue with jobs: {remaining}")

        return [], True  # Should break from main loop

    def _mark_condition_failed_jobs_as_skipped(
        self, diagnostics, job_outputs, completed
    ):
        """Mark jobs with unmet conditions as skipped"""
        for job_id, diag in diagnostics.items():
            if diag["status"] == "condition_not_met":
                job_outputs[job_id] = self._create_job_output(job_id, "skipped")
                completed.add(job_id)

    def _create_job_output(self, job_id: str, status: str, outputs=None, error=None):
        """Factory method for creating job output dictionaries"""
        return {
            "job_id": job_id,
            "status": status,
            "outputs": outputs if outputs is not None else {},
            "error": error,
        }

    async def _execute_job(
        self, job_id: str, workflow_def, job_outputs, env_vars, executor, completed
    ):
        """Execute a single job with all its steps"""
        job_def = workflow_def.jobs[job_id]

        # Check condition first
        if job_def.if_condition:
            condition_met = ConditionEvaluator.evaluate_job_condition(
                job_def.if_condition, job_outputs, env_vars
            )
            if not condition_met:
                logger.info(f"LOCAL: Skipping {job_id} (condition not met)")
                job_outputs[job_id] = self._create_job_output(job_id, "skipped")
                completed.add(job_id)
                return

        logger.info(f"LOCAL: Executing job {job_id}")

        # Execute all steps in the job
        all_outputs, job_failed, error_message = await self._execute_job_steps(
            job_def, env_vars, executor, job_id
        )

        # Process job-level output mappings
        job_level_outputs = self._process_job_level_outputs(
            job_def, all_outputs, env_vars, job_failed
        )

        # Combine outputs and store result
        final_outputs = {**all_outputs, **job_level_outputs}
        job_status = "failure" if job_failed else "completed"

        job_outputs[job_id] = self._create_job_output(
            job_id, job_status, final_outputs, error_message
        )

        # Update global environment (only if job succeeded)
        if not job_failed:
            self._update_global_environment(job_id, final_outputs, env_vars)

        completed.add(job_id)

    async def _execute_job_steps(self, job_def, env_vars, executor, job_id):
        """Execute all steps in a job with retry logic"""
        all_outputs = {}
        job_failed = False
        error_message = None
        step_outputs = {}  # Track outputs by step id

        max_retries = getattr(self.config, "max_retries", 3)

        for step in job_def.steps:
            if step.run and not job_failed:
                command = VariableSubstitution.substitute(step.run, env_vars)
                (
                    outputs,
                    step_succeeded,
                    step_error,
                ) = await self._execute_step_with_retry(
                    command, env_vars, executor, max_retries, job_id
                )

                if step_succeeded:
                    all_outputs.update(outputs)
                    if step.id:
                        step_outputs[step.id] = outputs
                        self._update_step_environment(step.id, outputs, env_vars)
                else:
                    job_failed = True
                    error_message = step_error
                    break

        return all_outputs, job_failed, error_message

    async def _execute_step_with_retry(
        self, command, env_vars, executor, max_retries, job_id
    ):
        """Execute a single step with retry logic and exponential backoff"""
        outputs = {}

        for attempt in range(max_retries + 1):
            try:
                success, stdout, stderr, env_updates = executor.execute(
                    command, env_vars, working_dir=os.getcwd()
                )

                if success:
                    # Log command output for visibility
                    if stdout.strip():
                        # Filter out the special parsing markers
                        clean_lines = []
                        in_output_section = False
                        for line in stdout.split('\n'):
                            if line.strip() == "=== GITHUB_OUTPUT ===":
                                in_output_section = True
                            elif line.strip() == "=== END ===":
                                in_output_section = False
                            elif not in_output_section and line.strip() and "GITHUB_" not in line:
                                clean_lines.append(line)
                        
                        if clean_lines:
                            for line in clean_lines:
                                if line.strip():
                                    logger.info(f"LOCAL: {line}")
                    
                    outputs = env_updates
                    return outputs, True, None
                elif attempt < max_retries:
                    logger.warning(
                        f"LOCAL: Retry {attempt + 1}/{max_retries} for command: {command[:50]}..."
                    )
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                else:
                    error_msg = (
                        f"Command failed after {max_retries + 1} attempts: {stderr}"
                    )
                    logger.error(f"LOCAL: Step failed in job {job_id}: {stderr}")
                    return outputs, False, error_msg
            except Exception as e:
                if attempt == max_retries:
                    error_msg = f"Execution error after {max_retries + 1} attempts: {e}"
                    logger.error(f"LOCAL: Step execution error in job {job_id}: {e}")
                    return outputs, False, error_msg
                logger.warning(f"LOCAL: Execution attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(2**attempt)

        return outputs, False, "Unknown execution error"

    def _update_step_environment(self, step_id, outputs, env_vars):
        """Update environment variables for step references"""
        for key, value in outputs.items():
            env_vars[f"STEP_{step_id}_{key}".upper()] = str(value)

    def _process_job_level_outputs(
        self, job_def, step_outputs_dict, env_vars, job_failed
    ):
        """Process job-level output mappings"""
        job_level_outputs = {}
        if job_def.outputs and not job_failed:
            for output_name, output_expression in job_def.outputs.items():
                if "${{" in output_expression:
                    # Handle step reference patterns
                    value = self._resolve_step_reference(
                        output_expression, step_outputs_dict
                    )
                    if value is not None:
                        job_level_outputs[output_name] = value
                else:
                    # Direct value or variable substitution
                    job_level_outputs[output_name] = VariableSubstitution.substitute(
                        output_expression, env_vars
                    )
        return job_level_outputs

    def _resolve_step_reference(self, output_expression, step_outputs_dict):
        """Resolve step reference patterns like ${{ steps.step_id.outputs.key }}"""
        import re

        step_pattern = r"\$\{\{\s*steps\.(\w+)\.outputs\.(\w+)\s*\}\}"
        match = re.search(step_pattern, output_expression)
        if match:
            step_id = match.group(1)
            output_key = match.group(2)
            # Note: step_outputs_dict here is actually all_outputs, need to find step-specific outputs
            # This is a simplified version - might need refinement based on actual step output tracking
            return step_outputs_dict.get(output_key)
        return None

    def _update_global_environment(self, job_id, final_outputs, env_vars):
        """Update global environment variables with job outputs"""
        for key, value in final_outputs.items():
            env_vars[f"JOB_{job_id.upper()}_{key.upper()}"] = str(value)

    def _build_final_result(self, workflow_def, job_outputs):
        """Build and return the final workflow result"""
        final_job_outputs = {}
        workflow_failed = False

        for job_id, output_dict in job_outputs.items():
            if isinstance(output_dict, dict):
                job_status_str = output_dict.get("status", "completed")
                # Map string status directly (no enum conversion needed)
                if job_status_str == "failure":
                    job_status = JobStatus.FAILED.value
                    workflow_failed = True
                elif job_status_str == "skipped":
                    job_status = JobStatus.SKIPPED.value
                else:  # "completed" or other success statuses
                    job_status = JobStatus.COMPLETED.value

                final_job_outputs[job_id] = JobOutput(
                    job_id=output_dict.get("job_id", job_id),
                    status=job_status,
                    outputs=output_dict.get("outputs", {}),
                    error=output_dict.get("error"),
                )

        overall_status = (
            JobStatus.FAILED.value if workflow_failed else JobStatus.COMPLETED.value
        )

        return WorkflowResult(
            workflow_name=workflow_def.name,
            status=overall_status,
            jobs=final_job_outputs,
        )


async def run_temporal(yaml_file: str) -> WorkflowResult:
    """Run with Temporal server"""
    import time

    client = await Client.connect(config.temporal_server)
    # Use timestamp instead of PID for workflow ID
    workflow_id = f"workflow-{int(time.time())}-{hash(yaml_file) % 10000}"
    return await client.execute_workflow(
        WorkflowExecutor.run,
        yaml_file,
        id=workflow_id,
        task_queue="flowrite-main",
    )


async def start_worker():
    """Start Temporal worker"""
    client = await Client.connect(config.temporal_server)

    main_worker = Worker(
        client,
        task_queue="flowrite-main",
        workflows=[WorkflowExecutor],
        activities=[evaluate_condition, get_environment_vars],
    )

    job_worker = Worker(
        client,
        task_queue="flowrite-jobs",
        workflows=[JobWorkflow],
        activities=[execute_job_step],
    )

    await asyncio.gather(main_worker.run(), job_worker.run())


def get_sample_workflow_content():
    """Get the sample workflow YAML content"""
    return """name: Simple Parallel Workflow (loop semantics explained)

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


async def execute_workflow(yaml_file: str, local_mode: bool) -> WorkflowResult:
    """Execute workflow in local or temporal mode"""
    global config

    if not os.path.exists(yaml_file):
        raise ValueError(f"{yaml_file} not found")

    try:
        if local_mode:
            engine = LocalEngine(config)
            result = await engine.run_workflow(yaml_file)
        else:
            result = await run_temporal(yaml_file)
        return result
    except ValueError:
        # Re-raise user-friendly errors
        raise
    except Exception as e:
        # Wrap other errors for consistent handling
        raise RuntimeError(f"Workflow execution failed: {e}") from e


def display_result(result: WorkflowResult):
    """Display workflow execution result"""
    click.echo("SUCCESS!")
    click.echo(f"Workflow: {result.workflow_name}")
    click.echo(f"Status: {result.status}")
    click.echo("Jobs:")
    for job_id, job_output in result.jobs.items():
        click.echo(f"  {job_id}: {job_output.status}")
        if job_output.outputs:
            for key, value in job_output.outputs.items():
                click.echo(f"    {key}={value}")


@click.group()
@click.pass_context
def cli(ctx):
    """Flowrite Workflow Executor - YAML-based temporal workflow execution"""
    global config
    ctx.ensure_object(dict)

    # Load configuration
    env_config = ConfigLoader.from_env()
    config = Config(**ConfigLoader.from_dict(env_config, config.__dict__))


@cli.command()
@click.argument("yaml_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--local", is_flag=True, help="Execute locally (real bash commands)")
@click.pass_context
def run(ctx, yaml_file: str, local: bool):
    """Execute workflow from YAML file"""
    mode_desc = "(local)" if local else "(temporal)"
    click.echo(f"Executing {yaml_file} {mode_desc}")

    try:
        result = asyncio.run(execute_workflow(yaml_file, local))
        display_result(result)
    except ValueError as e:
        click.echo(f"ERROR: {e}", err=True)
        ctx.exit(1)
    except RuntimeError as e:
        click.echo(f"FAILED: {e}", err=True)
        import traceback

        traceback.print_exc()
        ctx.exit(1)


@cli.command()
def worker():
    """Start Temporal worker"""
    click.echo("Starting Temporal worker...")
    try:
        asyncio.run(start_worker())
    except KeyboardInterrupt:
        click.echo("\nShutting down worker...")
    except Exception as e:
        click.echo(f"Worker failed: {e}", err=True)
        raise


@cli.command("create-sample")
@click.option(
    "-f",
    "--file",
    "filename",
    default="sample_workflow.yaml",
    help="Output filename for the sample workflow",
)
def create_sample(filename: str):
    """Create sample YAML workflow"""
    content = get_sample_workflow_content()

    try:
        with open(filename, "w") as f:
            f.write(content)
        click.echo(f"Created {filename}")
    except Exception as e:
        click.echo(f"Error creating sample file: {e}", err=True)
        raise


def main():
    """Main CLI entry point"""
    cli()


if __name__ == "__main__":
    main()
