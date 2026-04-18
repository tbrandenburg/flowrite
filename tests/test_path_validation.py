"""Tests for path validation security."""
import pytest

from src.security.path import validate_safe_path, validate_workflow_path, PathTraversalError


class TestValidateSafePath:
    def test_simple_relative_path(self, tmp_path):
        """Accept simple relative paths within allowed dir."""
        test_file = tmp_path / "test.yaml"
        test_file.write_text("content")

        result = validate_safe_path("test.yaml", allowed_dir=str(tmp_path))
        assert result == str(test_file.resolve())

    def test_rejects_parent_traversal(self, tmp_path):
        """Reject paths that escape allowed directory."""
        with pytest.raises(PathTraversalError):
            validate_safe_path("../outside.yaml", allowed_dir=str(tmp_path))

    def test_rejects_absolute_traversal(self, tmp_path):
        """Reject absolute paths outside allowed directory."""
        with pytest.raises(PathTraversalError):
            validate_safe_path("/etc/passwd", allowed_dir=str(tmp_path))

    def test_rejects_double_dot_in_path(self, tmp_path):
        """Reject paths with embedded traversal."""
        outside = tmp_path / ".."
        with pytest.raises(PathTraversalError):
            validate_safe_path(str(outside), allowed_dir=str(tmp_path))

    def test_allows_nested_subdir(self, tmp_path):
        """Allow paths in subdirectories of allowed dir."""
        subdir = tmp_path / "subdir" / "nested"
        subdir.mkdir(parents=True)
        test_file = subdir / "deep.yaml"
        test_file.write_text("content")

        result = validate_safe_path("subdir/nested/deep.yaml", allowed_dir=str(tmp_path))
        assert result == str(test_file.resolve())


class TestValidateWorkflowPath:
    def test_valid_workflow_file(self, tmp_path):
        """Accept existing workflow file."""
        wf_file = tmp_path / "workflow.yaml"
        wf_file.write_text("steps: []")

        result = validate_workflow_path("workflow.yaml", base_dir=str(tmp_path))
        assert result == str(wf_file.resolve())

    def test_rejects_nonexistent_file(self, tmp_path):
        """Reject non-existent workflow files."""
        with pytest.raises(FileNotFoundError):
            validate_workflow_path("missing.yaml", base_dir=str(tmp_path))

    def test_rejects_traversal_to_file(self, tmp_path):
        """Reject traversal to existing file outside allowed dir."""
        outside_dir = tmp_path.parent
        target_file = outside_dir / "secret.yaml"
        target_file.write_text("secret: true")

        with pytest.raises(PathTraversalError):
            validate_workflow_path("../secret.yaml", base_dir=str(tmp_path))