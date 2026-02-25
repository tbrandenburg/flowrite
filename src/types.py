"""
Flowrite Workflow Types - Core data structures for workflow execution
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from enum import Enum


class JobStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class LoopCondition(Enum):
    SUCCESS = "success()"
    FAILURE = "failure()"
    CANCELLED = "cancelled()"


@dataclass
class Config:
    """Global configuration for workflow execution"""

    step_timeout_seconds: int = 300  # 5 minutes
    activity_timeout_seconds: int = 30
    eval_timeout_seconds: int = 10
    temporal_server: str = "localhost:7233"
    max_retries: int = 3


@dataclass
class LoopConfig:
    """Configuration for job and step-level loops"""

    until: Optional[str] = None  # Condition expression
    max_iterations: int = 1


@dataclass
class StepDefinition:
    """A single step within a job"""

    name: Optional[str] = None
    id: Optional[str] = None
    run: Optional[str] = None
    loop: Optional[LoopConfig] = None

    def __post_init__(self):
        if isinstance(self.loop, dict):
            self.loop = LoopConfig(**self.loop)


@dataclass
class JobDefinition:
    """A job definition from YAML"""

    name: Optional[str] = None
    runs_on: Optional[str] = None
    needs: Union[str, List[str]] = field(default_factory=list)
    if_condition: Optional[str] = None
    outputs: Dict[str, str] = field(default_factory=dict)
    steps: List[StepDefinition] = field(default_factory=list)
    loop: Optional[LoopConfig] = None

    def __post_init__(self):
        # Convert needs to list
        if isinstance(self.needs, str):
            self.needs = [self.needs]

        # Convert loop dict to object
        if isinstance(self.loop, dict):
            self.loop = LoopConfig(**self.loop)

        # Convert steps dicts to objects
        converted_steps = []
        for step in self.steps:
            if isinstance(step, dict):
                converted_steps.append(StepDefinition(**step))
            else:
                converted_steps.append(step)
        self.steps = converted_steps


@dataclass
class WorkflowDefinition:
    """Complete workflow definition"""

    name: Optional[str] = None
    on: Dict[str, Any] = field(default_factory=dict)
    jobs: Dict[str, JobDefinition] = field(default_factory=dict)

    def __post_init__(self):
        # Convert job dicts to objects
        converted_jobs = {}
        for job_id, job_data in self.jobs.items():
            if isinstance(job_data, dict):
                # Handle 'if' key mapping to 'if_condition'
                if "if" in job_data:
                    job_data["if_condition"] = job_data.pop("if")
                # Handle 'runs-on' key mapping to 'runs_on'
                if "runs-on" in job_data:
                    job_data["runs_on"] = job_data.pop("runs-on")
                converted_jobs[job_id] = JobDefinition(**job_data)
            else:
                converted_jobs[job_id] = job_data
        self.jobs = converted_jobs


@dataclass
class JobOutput:
    """Results from job execution"""

    job_id: str
    status: str = "completed"  # Use string instead of enum for JSON serialization
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class StepResult:
    """Results from step execution"""

    success: bool
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class WorkflowResult:
    """Complete workflow execution results"""

    workflow_name: Optional[str]
    status: str  # Use string instead of enum for JSON serialization
    jobs: Dict[str, JobOutput] = field(default_factory=dict)
