"""
Flowrite DSL - Domain Specific Language parser and evaluator for workflows
"""

import re
import yaml
from typing import Any, Dict, List, Optional
from .types import WorkflowDefinition, JobDefinition, StepDefinition, LoopConfig


class ConditionEvaluator:
    """Evaluates workflow conditions and expressions"""

    @staticmethod
    def evaluate_job_condition(
        condition: str, job_outputs: Dict[str, Dict[str, Any]], env_vars: Dict[str, str]
    ) -> bool:
        """Evaluate job-level if conditions"""
        if not condition:
            return True

        condition = condition.strip()

        # Handle always()
        if condition == "always()":
            return True

        # Handle success(), failure(), cancelled() functions
        if condition in ["success()", "failure()", "cancelled()"]:
            # TODO: Implement based on actual execution context
            return True

        # Handle needs.job.outputs.key == 'value' patterns
        needs_pattern = r'needs\.(\w+)\.outputs\.(\w+)\s*==\s*[\'"]([^\'"]*)[\'"]'
        match = re.search(needs_pattern, condition)
        if match:
            job_id, output_key, expected_value = match.groups()
            actual_value = (
                job_outputs.get(job_id, {}).get("outputs", {}).get(output_key)
            )
            return actual_value == expected_value

        # Handle env.VARIABLE == 'value' patterns
        env_pattern = r'env\.(\w+)\s*==\s*[\'"]([^\'"]*)[\'"]'
        match = re.search(env_pattern, condition)
        if match:
            var_name, expected_value = match.groups()
            actual_value = env_vars.get(var_name)
            return actual_value == expected_value

        # Default to true for unknown conditions
        return True

    @staticmethod
    def evaluate_loop_condition(
        condition: str,
        iteration: int,
        max_iterations: int,
        step_success: bool,
        env_vars: Dict[str, str],
    ) -> bool:
        """Evaluate loop until conditions"""
        if not condition:
            return iteration >= max_iterations

        condition = condition.strip()

        # Function-based conditions
        if condition == "success()":
            return step_success
        elif condition == "failure()":
            return not step_success
        elif condition == "cancelled()":
            # TODO: Implement cancellation detection
            return False

        # Environment variable conditions
        env_pattern = r'env\.(\w+)\s*==\s*[\'"]([^\'"]*)[\'"]'
        match = re.search(env_pattern, condition)
        if match:
            var_name, expected_value = match.groups()
            actual_value = env_vars.get(var_name)
            return actual_value == expected_value

        # Default: continue until max iterations
        return iteration >= max_iterations


class WorkflowParser:
    """Parses YAML workflows into structured definitions"""

    @staticmethod
    def load_from_file(file_path: str) -> WorkflowDefinition:
        """Load workflow from YAML file with user-friendly error messages"""
        try:
            with open(file_path, "r") as f:
                yaml_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            # Provide user-friendly YAML parsing errors
            error_msg = f"YAML parsing error in {file_path}:\n  {str(e)}\n  Please check your YAML syntax."
            raise ValueError(error_msg) from None
        except FileNotFoundError:
            raise ValueError(f"Workflow file not found: {file_path}") from None
        except PermissionError:
            raise ValueError(f"Permission denied reading file: {file_path}") from None

        if yaml_data is None:
            raise ValueError(f"Empty or invalid YAML file: {file_path}")

        return WorkflowParser.parse(yaml_data)

    @staticmethod
    def parse(yaml_data: Dict[str, Any]) -> WorkflowDefinition:
        """Parse YAML data into workflow definition with better error messages"""
        if not isinstance(yaml_data, dict):
            raise ValueError(
                f"Invalid workflow format: expected a YAML object but got {type(yaml_data).__name__}.\n"
                f"  Workflows must start with properties like 'name:' and 'jobs:'"
            )

        try:
            return WorkflowDefinition(**yaml_data)
        except TypeError as e:
            if "unexpected keyword argument" in str(e):
                # Extract the problematic field name
                import re

                match = re.search(r"unexpected keyword argument '(\w+)'", str(e))
                if match:
                    field_name = match.group(1)
                    raise ValueError(
                        f"Unknown workflow property: '{field_name}'\n"
                        f"  Valid top-level properties are: name, jobs, on\n"
                        f"  Did you mean to put '{field_name}' inside a job definition?"
                    ) from None
            raise ValueError(f"Workflow structure error: {str(e)}") from None
        except Exception as e:
            raise ValueError(f"Error parsing workflow definition: {str(e)}") from None

    @staticmethod
    def validate(workflow: WorkflowDefinition) -> List[str]:
        """Validate workflow definition and return error messages"""
        errors = []

        if not workflow.jobs:
            errors.append("Workflow must contain 'jobs'")
            return errors

        job_ids = set(workflow.jobs.keys())

        # Validate job dependencies
        for job_id, job in workflow.jobs.items():
            for dep in job.needs:
                if dep not in job_ids:
                    errors.append(f"Job '{job_id}' depends on non-existent job '{dep}'")

        # Check for circular dependencies
        visited = set()
        rec_stack = set()

        def has_cycle(job_id: str) -> bool:
            if job_id in rec_stack:
                return True
            if job_id in visited:
                return False

            visited.add(job_id)
            rec_stack.add(job_id)

            job = workflow.jobs.get(job_id)
            if job:
                for dep in job.needs:
                    if has_cycle(dep):
                        return True

            rec_stack.remove(job_id)
            return False

        for job_id in job_ids:
            if job_id not in visited and has_cycle(job_id):
                errors.append(f"Circular dependency detected involving job '{job_id}'")
                break

        return errors


class DependencyResolver:
    """Resolves job execution order based on dependencies"""

    @staticmethod
    def get_ready_jobs(
        workflow: WorkflowDefinition,
        completed: set,
        job_outputs: Dict[str, Dict[str, Any]],
        env_vars: Dict[str, str],
    ) -> List[str]:
        """Get list of jobs ready to execute"""
        ready = []
        remaining = set(workflow.jobs.keys()) - completed

        for job_id in remaining:
            job = workflow.jobs[job_id]

            # Check if all dependencies are completed
            if all(dep in completed for dep in job.needs):
                # Check condition if present
                if job.if_condition:
                    condition_met = ConditionEvaluator.evaluate_job_condition(
                        job.if_condition, job_outputs, env_vars
                    )
                    if condition_met:
                        ready.append(job_id)
                else:
                    ready.append(job_id)

        return ready


class OutputParser:
    """Parses outputs from command execution"""

    @staticmethod
    def parse_github_output(command: str) -> Dict[str, str]:
        """Parse GITHUB_OUTPUT style outputs from command"""
        outputs = {}

        # Look for echo "key=value" >> "$GITHUB_OUTPUT" patterns
        for line in command.split("\n"):
            line = line.strip()
            if "GITHUB_OUTPUT" in line and 'echo "' in line:
                try:
                    # Extract the quoted content
                    start = line.find('echo "') + 6
                    end = line.find('"', start)
                    if start > 5 and end > start:
                        content = line[start:end]
                        if "=" in content:
                            key, value = content.split("=", 1)
                            outputs[key.strip()] = value.strip()
                except:
                    pass

        return outputs

    @staticmethod
    def parse_github_env(command: str) -> Dict[str, str]:
        """Parse GITHUB_ENV style environment variables from command"""
        env_vars = {}

        # Look for echo "KEY=value" >> "$GITHUB_ENV" patterns
        for line in command.split("\n"):
            line = line.strip()
            if "GITHUB_ENV" in line and 'echo "' in line:
                try:
                    # Extract the quoted content
                    start = line.find('echo "') + 6
                    end = line.find('"', start)
                    if start > 5 and end > start:
                        content = line[start:end]
                        if "=" in content:
                            key, value = content.split("=", 1)
                            env_vars[key.strip()] = value.strip()
                except:
                    pass

        return env_vars
