"""
Tests for improved YAML parsing error messages
"""

import pytest
import tempfile
import os
from src.dsl import WorkflowParser


class TestYAMLErrorHandling:
    """Test improved YAML parsing error messages"""

    def test_invalid_yaml_syntax_error(self):
        """Test handling of invalid YAML syntax"""
        invalid_yaml = """
invalid yaml:
  - indentation
 problem: here
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(invalid_yaml)
            temp_file = f.name

        try:
            with pytest.raises(ValueError) as exc_info:
                WorkflowParser.load_from_file(temp_file)

            error_msg = str(exc_info.value)
            assert "YAML parsing error" in error_msg
            assert "Please check your YAML syntax" in error_msg
            assert temp_file in error_msg
        finally:
            os.unlink(temp_file)

    def test_empty_yaml_file_error(self):
        """Test handling of empty YAML files"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            temp_file = f.name

        try:
            with pytest.raises(ValueError) as exc_info:
                WorkflowParser.load_from_file(temp_file)

            error_msg = str(exc_info.value)
            assert "Empty or invalid YAML file" in error_msg
            assert temp_file in error_msg
        finally:
            os.unlink(temp_file)

    def test_invalid_workflow_property_error(self):
        """Test handling of unknown workflow properties"""
        invalid_data = {
            "name": "Test",
            "invalid_property": "should not be here",
            "jobs": {"test": {"steps": [{"run": "echo test"}]}},
        }

        with pytest.raises(ValueError) as exc_info:
            WorkflowParser.parse(invalid_data)

        error_msg = str(exc_info.value)
        assert "Unknown workflow property: 'invalid_property'" in error_msg
        assert "Valid top-level properties are: name, jobs, on" in error_msg
        assert "Did you mean to put" in error_msg

    def test_invalid_data_type_error(self):
        """Test handling of wrong data types (e.g., array instead of object)"""
        invalid_data = ["name: test", "jobs: test"]

        with pytest.raises(ValueError) as exc_info:
            WorkflowParser.parse(invalid_data)

        error_msg = str(exc_info.value)
        assert "Invalid workflow format" in error_msg
        assert "expected a YAML object but got list" in error_msg
        assert (
            "Workflows must start with properties like 'name:' and 'jobs:'" in error_msg
        )

    def test_file_not_found_error(self):
        """Test handling of missing files"""
        with pytest.raises(ValueError) as exc_info:
            WorkflowParser.load_from_file("/nonexistent/path/file.yaml")

        error_msg = str(exc_info.value)
        assert "Workflow file not found" in error_msg
        assert "/nonexistent/path/file.yaml" in error_msg

    def test_valid_workflow_still_works(self):
        """Test that valid workflows still parse correctly"""
        valid_data = {
            "name": "Test Workflow",
            "jobs": {"test": {"steps": [{"run": "echo test"}]}},
        }

        # Should not raise any exceptions
        workflow = WorkflowParser.parse(valid_data)
        assert workflow.name == "Test Workflow"
        assert "test" in workflow.jobs


if __name__ == "__main__":
    pytest.main([__file__])
