"""
Performance Tests

These tests focus on verifying that the workflow execution system performs well
at scale, handling large workflows, deep dependency chains, many conditions,
extensive variable substitution, and monitoring memory usage.
"""

import time
import gc
import psutil
import os
from src.types import WorkflowDefinition, JobDefinition, StepDefinition
from src.dsl import DependencyResolver, ConditionEvaluator
from src.utils import VariableSubstitution, BashExecutor


class TestPerformanceScenarios:
    """Test suite for performance and scalability"""

    def test_large_workflow_performance(self):
        """Test that performance with 50+ jobs is reasonable"""
        # Create a large workflow with 50+ jobs
        num_jobs = 60
        jobs = {}

        # Create setup jobs (first 5 jobs have no dependencies)
        for i in range(5):
            job_id = f"setup_{i}"
            jobs[job_id] = JobDefinition(
                name=job_id,
                runs_on="ubuntu-latest",
                steps=[
                    StepDefinition(
                        run=f'echo "{job_id}_complete=true" >> "$GITHUB_OUTPUT"'
                    )
                ],
                needs=[],
            )

        # Create build jobs (depend on setup jobs)
        for i in range(5, 15):
            job_id = f"build_{i}"
            setup_deps = [f"setup_{j}" for j in range(5)]
            jobs[job_id] = JobDefinition(
                name=job_id,
                runs_on="ubuntu-latest",
                steps=[
                    StepDefinition(
                        run=f'echo "{job_id}_complete=true" >> "$GITHUB_OUTPUT"'
                    )
                ],
                needs=setup_deps,
            )

        # Create test jobs (depend on build jobs)
        for i in range(15, 35):
            job_id = f"test_{i}"
            build_deps = [f"build_{j}" for j in range(5, 15)]
            jobs[job_id] = JobDefinition(
                name=job_id,
                runs_on="ubuntu-latest",
                steps=[
                    StepDefinition(
                        run=f'echo "{job_id}_complete=true" >> "$GITHUB_OUTPUT"'
                    )
                ],
                needs=build_deps,
            )

        # Create deploy jobs (depend on test jobs)
        for i in range(35, 50):
            job_id = f"deploy_{i}"
            test_deps = [f"test_{j}" for j in range(15, 35)]
            jobs[job_id] = JobDefinition(
                name=job_id,
                runs_on="ubuntu-latest",
                steps=[
                    StepDefinition(
                        run=f'echo "{job_id}_complete=true" >> "$GITHUB_OUTPUT"'
                    )
                ],
                needs=test_deps,
            )

        # Create final verification jobs (depend on deploy jobs)
        for i in range(50, num_jobs):
            job_id = f"verify_{i}"
            deploy_deps = [f"deploy_{j}" for j in range(35, 50)]
            jobs[job_id] = JobDefinition(
                name=job_id,
                runs_on="ubuntu-latest",
                steps=[
                    StepDefinition(
                        run=f'echo "{job_id}_complete=true" >> "$GITHUB_OUTPUT"'
                    )
                ],
                needs=deploy_deps,
            )

        workflow = WorkflowDefinition(name="Large Workflow Performance Test", jobs=jobs)

        # Test dependency resolution performance
        completed = set()
        job_outputs = {}
        env_vars = {}

        # Measure time for initial dependency resolution
        start_time = time.time()
        ready_jobs = DependencyResolver.get_ready_jobs(
            workflow, completed, job_outputs, env_vars
        )
        initial_resolution_time = time.time() - start_time

        # Should identify setup jobs as ready
        assert len(ready_jobs) == 5
        assert all(job.startswith("setup_") for job in ready_jobs)

        # Initial resolution should be fast (under 100ms for 60 jobs)
        assert initial_resolution_time < 0.1, (
            f"Initial resolution took {initial_resolution_time:.3f}s, expected < 0.1s"
        )

        # Simulate completing jobs layer by layer and measure performance
        total_resolution_time = initial_resolution_time
        layer_count = 0

        while len(completed) < num_jobs:
            layer_count += 1

            # Complete currently ready jobs
            for job_id in ready_jobs:
                completed.add(job_id)
                job_outputs[job_id] = {"outputs": {f"{job_id}_complete": "true"}}

            # Find next ready jobs
            start_time = time.time()
            ready_jobs = DependencyResolver.get_ready_jobs(
                workflow, completed, job_outputs, env_vars
            )
            resolution_time = time.time() - start_time
            total_resolution_time += resolution_time

            # Each resolution should still be fast
            assert resolution_time < 0.1, (
                f"Layer {layer_count} resolution took {resolution_time:.3f}s, expected < 0.1s"
            )

            # Prevent infinite loops
            if layer_count > 10:
                break

        # Total time for all dependency resolutions should be reasonable
        assert total_resolution_time < 0.5, (
            f"Total resolution time {total_resolution_time:.3f}s, expected < 0.5s"
        )

        # Should have completed all jobs
        assert len(completed) == num_jobs

    def test_deep_dependency_chains(self):
        """Test that long chains of dependencies work efficiently"""
        # Create a deep dependency chain: job_0 → job_1 → job_2 → ... → job_49
        chain_length = 50
        jobs = {}

        for i in range(chain_length):
            job_id = f"job_{i}"
            needs = [f"job_{i - 1}"] if i > 0 else []

            jobs[job_id] = JobDefinition(
                name=job_id,
                runs_on="ubuntu-latest",
                steps=[
                    StepDefinition(
                        run=f'echo "step_{i}_complete=true" >> "$GITHUB_OUTPUT"'
                    )
                ],
                needs=needs,
                if_condition=f"needs.job_{i - 1}.outputs.step_{i - 1}_complete == 'true'"
                if i > 0
                else None,
            )

        workflow = WorkflowDefinition(name="Deep Dependency Chain Test", jobs=jobs)

        # Simulate execution step by step
        completed = set()
        job_outputs = {}
        env_vars = {}

        total_time = 0

        for i in range(chain_length):
            start_time = time.time()
            ready_jobs = DependencyResolver.get_ready_jobs(
                workflow, completed, job_outputs, env_vars
            )
            resolution_time = time.time() - start_time
            total_time += resolution_time

            # Should always find exactly one ready job (except at the end)
            if i < chain_length:
                assert len(ready_jobs) == 1, (
                    f"Step {i}: expected 1 ready job, got {len(ready_jobs)}"
                )
                expected_job = f"job_{i}"
                assert ready_jobs[0] == expected_job, (
                    f"Step {i}: expected {expected_job}, got {ready_jobs[0]}"
                )

            # Complete the ready job
            if ready_jobs:
                job_id = ready_jobs[0]
                completed.add(job_id)
                job_outputs[job_id] = {"outputs": {f"step_{i}_complete": "true"}}

            # Each step should resolve quickly
            assert resolution_time < 0.05, (
                f"Step {i} took {resolution_time:.3f}s, expected < 0.05s"
            )

        # Total time should be reasonable for 50-step chain
        assert total_time < 1.0, (
            f"Total chain resolution took {total_time:.3f}s, expected < 1.0s"
        )

        # All jobs should be completed
        assert len(completed) == chain_length

    def test_many_condition_evaluations(self):
        """Test that many complex conditions do not timeout"""
        # Create jobs with many complex conditions
        num_jobs = 30
        jobs = {}

        # Create base jobs that will be referenced
        for i in range(5):
            job_id = f"base_{i}"
            jobs[job_id] = JobDefinition(
                name=job_id,
                runs_on="ubuntu-latest",
                steps=[
                    StepDefinition(
                        run=f'echo "status_{i}=success" >> "$GITHUB_OUTPUT"'
                    ),
                    StepDefinition(run=f'echo "result_{i}=passed" >> "$GITHUB_OUTPUT"'),
                ],
                needs=[],
            )

        # Create jobs with complex conditions referencing the base jobs
        for i in range(5, num_jobs):
            job_id = f"conditional_{i}"

            # Create increasingly complex conditions
            if i < 10:
                # Simple conditions
                condition = f"needs.base_0.outputs.status_0 == 'success'"
            elif i < 15:
                # AND conditions
                condition = f"needs.base_0.outputs.status_0 == 'success' && needs.base_1.outputs.status_1 == 'success'"
            elif i < 20:
                # OR conditions
                condition = f"needs.base_0.outputs.status_0 == 'success' || needs.base_1.outputs.status_1 == 'failed'"
            elif i < 25:
                # Complex mixed conditions
                condition = f"(needs.base_0.outputs.status_0 == 'success' && needs.base_1.outputs.result_1 == 'passed') || (needs.base_2.outputs.status_2 == 'success' && needs.base_3.outputs.result_3 == 'passed')"
            else:
                # Very complex conditions with environment variables
                condition = f"needs.base_0.outputs.status_0 == 'success' && needs.base_1.outputs.result_1 == 'passed' && env.TEST_ENV == 'production' && (needs.base_2.outputs.status_2 == 'success' || needs.base_3.outputs.status_3 == 'success')"

            jobs[job_id] = JobDefinition(
                name=job_id,
                runs_on="ubuntu-latest",
                steps=[
                    StepDefinition(
                        run=f'echo "{job_id}_complete=true" >> "$GITHUB_OUTPUT"'
                    )
                ],
                needs=[f"base_{j}" for j in range(5)],
                if_condition=condition,
            )

        workflow = WorkflowDefinition(name="Many Conditions Test", jobs=jobs)

        # Set up job outputs for base jobs
        job_outputs = {}
        for i in range(5):
            job_outputs[f"base_{i}"] = {
                "outputs": {f"status_{i}": "success", f"result_{i}": "passed"}
            }

        env_vars = {"TEST_ENV": "production"}
        completed = {f"base_{i}" for i in range(5)}

        # Test condition evaluation performance
        start_time = time.time()
        ready_jobs = DependencyResolver.get_ready_jobs(
            workflow, completed, job_outputs, env_vars
        )
        evaluation_time = time.time() - start_time

        # Should identify conditional jobs as ready (since conditions should evaluate to True)
        expected_conditional_jobs = num_jobs - 5  # 25 conditional jobs
        assert len(ready_jobs) == expected_conditional_jobs, (
            f"Expected {expected_conditional_jobs} ready jobs, got {len(ready_jobs)}"
        )

        # Condition evaluation should be fast even with many complex conditions
        assert evaluation_time < 0.5, (
            f"Condition evaluation took {evaluation_time:.3f}s, expected < 0.5s"
        )

        # Test individual condition evaluation performance
        condition_times = []
        for job_id, job in workflow.jobs.items():
            if job_id.startswith("conditional_") and job.if_condition:
                start_time = time.time()
                result = ConditionEvaluator.evaluate_job_condition(
                    job.if_condition, job_outputs, env_vars
                )
                condition_time = time.time() - start_time
                condition_times.append(condition_time)

                # Each individual condition should evaluate quickly
                assert condition_time < 0.01, (
                    f"Condition for {job_id} took {condition_time:.4f}s, expected < 0.01s"
                )
                # All conditions should evaluate to True with our test data
                assert result is True, (
                    f"Condition for {job_id} evaluated to False, expected True"
                )

        # Average condition evaluation time should be very fast
        avg_condition_time = sum(condition_times) / len(condition_times)
        assert avg_condition_time < 0.005, (
            f"Average condition time {avg_condition_time:.4f}s, expected < 0.005s"
        )

    def test_extensive_variable_substitution(self):
        """Test that large amounts of variable substitution perform well"""
        # Create many environment variables
        large_env = {}
        for i in range(100):
            large_env[f"VAR_{i}"] = (
                f"value_{i}_with_some_longer_text_to_make_it_realistic"
            )
            large_env[f"PATH_{i}"] = f"/path/to/directory_{i}/with/nested/structure"
            large_env[f"URL_{i}"] = (
                f"https://example.com/api/v1/endpoint_{i}?param=value"
            )

        # Create complex substitution patterns
        patterns_to_test = []

        # Simple variable substitutions
        for i in range(50):
            patterns_to_test.append(f"Processing $VAR_{i} in ${{PATH_{i}}}")

        # Mixed substitutions with multiple variables
        for i in range(25):
            patterns_to_test.append(
                f"Connect to ${{URL_{i}}} using $VAR_{i} from ${{PATH_{i}}}"
            )

        # Complex patterns with text around variables
        for i in range(25):
            patterns_to_test.append(
                f'export COMBINED_{i}="prefix-$VAR_{i}-middle-${{PATH_{i}}}-suffix"'
            )

        # Test substitution performance
        total_substitution_time = 0

        for pattern in patterns_to_test:
            start_time = time.time()
            result = VariableSubstitution.substitute(pattern, large_env)
            substitution_time = time.time() - start_time
            total_substitution_time += substitution_time

            # Each substitution should be fast
            assert substitution_time < 0.001, (
                f"Substitution took {substitution_time:.4f}s, expected < 0.001s"
            )

            # Result should be a string (basic sanity check)
            assert isinstance(result, str)

            # Should have performed substitutions (no $ left for defined variables)
            # Count $ signs that are not part of undefined variables
            remaining_dollars = result.count("$")
            # For defined variables, there should be no $ signs left
            expected_dollars = 0  # All our variables are defined
            assert remaining_dollars == expected_dollars, (
                f"Pattern '{pattern}' left {remaining_dollars} unsubstituted variables"
            )

        # Total time for all substitutions should be reasonable
        assert total_substitution_time < 0.1, (
            f"Total substitution time {total_substitution_time:.3f}s, expected < 0.1s"
        )

        # Average substitution time should be very fast
        avg_time = total_substitution_time / len(patterns_to_test)
        assert avg_time < 0.001, (
            f"Average substitution time {avg_time:.4f}s, expected < 0.001s"
        )

        # Test bash execution with many variables
        executor = BashExecutor(timeout=30)

        # Create a bash script that uses many variables
        bash_script = """
        echo "Starting environment test"
        """

        # Add variable usage to the script
        for i in range(0, 20):  # Use a subset to keep test reasonable
            bash_script += f'echo "VAR_{i}: $VAR_{i}"\n'

        bash_script += 'echo "test_complete=true" >> "$GITHUB_OUTPUT"'

        # Test bash execution with large environment
        start_time = time.time()
        success, stdout, stderr, outputs = executor.execute(bash_script, large_env)
        execution_time = time.time() - start_time

        assert success, "Bash execution should succeed"
        assert outputs.get("test_complete") == "true", "Should complete successfully"

        # Execution should be reasonably fast even with large environment
        assert execution_time < 2.0, (
            f"Bash execution took {execution_time:.3f}s, expected < 2.0s"
        )

    def test_simulation_memory_usage(self):
        """Test that simulation does not leak memory on large workflows"""
        process = psutil.Process(os.getpid())

        # Get initial memory usage
        gc.collect()  # Force garbage collection
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create and process multiple medium-sized workflows
        for iteration in range(10):
            # Create a workflow with 20 jobs
            jobs = {}
            for i in range(20):
                job_id = f"job_{iteration}_{i}"
                needs = [f"job_{iteration}_{i - 1}"] if i > 0 else []

                jobs[job_id] = JobDefinition(
                    name=job_id,
                    runs_on="ubuntu-latest",
                    steps=[
                        StepDefinition(
                            run=f'echo "ITER_VAR_{i}=iteration_{iteration}_value_{i}" >> "$GITHUB_ENV"'
                        ),
                        StepDefinition(
                            run=f'echo "output_{i}=result_{iteration}_{i}" >> "$GITHUB_OUTPUT"'
                        ),
                    ],
                    needs=needs,
                    if_condition=f"needs.job_{iteration}_{i - 1}.outputs.output_{i - 1} == 'result_{iteration}_{i - 1}'"
                    if i > 0
                    else None,
                )

            workflow = WorkflowDefinition(
                name=f"Memory Test Workflow {iteration}", jobs=jobs
            )

            # Simulate complete workflow execution
            completed = set()
            job_outputs = {}
            env_vars = {}

            # Execute workflow step by step
            for step in range(20):
                ready_jobs = DependencyResolver.get_ready_jobs(
                    workflow, completed, job_outputs, env_vars
                )

                if ready_jobs:
                    job_id = ready_jobs[0]
                    completed.add(job_id)

                    # Simulate job outputs
                    job_outputs[job_id] = {
                        "outputs": {f"output_{step}": f"result_{iteration}_{step}"}
                    }

                    # Simulate environment variables
                    env_vars[f"ITER_VAR_{step}"] = f"iteration_{iteration}_value_{step}"

            # Force cleanup every few iterations
            if iteration % 3 == 0:
                gc.collect()

        # Check memory usage after all iterations
        gc.collect()  # Force final garbage collection
        final_memory = process.memory_info().rss / 1024 / 1024  # MB

        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 50MB for this test)
        # This accounts for normal Python overhead and test framework memory usage
        assert memory_increase < 50, (
            f"Memory increased by {memory_increase:.1f}MB, expected < 50MB"
        )

        # Test that large individual workflows don't cause excessive memory usage
        # Create one very large workflow
        large_jobs = {}
        for i in range(100):
            job_id = f"large_job_{i}"
            large_jobs[job_id] = JobDefinition(
                name=job_id,
                runs_on="ubuntu-latest",
                steps=[
                    StepDefinition(run=f'echo "Large job {i} executing"'),
                    StepDefinition(
                        run=f'echo "large_output_{i}=large_result_{i}" >> "$GITHUB_OUTPUT"'
                    ),
                ],
                needs=[f"large_job_{i - 1}"] if i > 0 else [],
            )

        large_workflow = WorkflowDefinition(
            name="Large Workflow Memory Test", jobs=large_jobs
        )

        # Test dependency resolution on large workflow
        pre_large_memory = process.memory_info().rss / 1024 / 1024

        completed = set()
        job_outputs = {}
        env_vars = {}

        # Just test dependency resolution, not full execution
        for _ in range(5):  # Test a few dependency resolution cycles
            ready_jobs = DependencyResolver.get_ready_jobs(
                large_workflow, completed, job_outputs, env_vars
            )
            if ready_jobs:
                # Complete first ready job
                job_id = ready_jobs[0]
                completed.add(job_id)
                job_outputs[job_id] = {
                    "outputs": {
                        f"large_output_{len(completed) - 1}": f"large_result_{len(completed) - 1}"
                    }
                }

        post_large_memory = process.memory_info().rss / 1024 / 1024
        large_workflow_memory_increase = post_large_memory - pre_large_memory

        # Large workflow processing should not cause excessive memory usage
        assert large_workflow_memory_increase < 20, (
            f"Large workflow increased memory by {large_workflow_memory_increase:.1f}MB, expected < 20MB"
        )
