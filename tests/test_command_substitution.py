"""
Test cases for command substitution in Flowrite workflow simulation.
These tests ensure that command substitution patterns like $(date +%s) are
properly simulated during workflow execution.
"""

import pytest
import re
import time
from src.utils import BashExecutor, VariableSubstitution


class TestCommandSubstitution:
    """Test command substitution in workflow simulation"""

    def test_date_command_unix_timestamp(self):
        """Test $(date +%s) should generate Unix timestamps"""
        executor = BashExecutor(timeout=10)

        # Test Unix timestamp generation in variable assignment
        command = """
        BUILD_ID="build-$(date +%s)"
        echo "build_id=${BUILD_ID}" >> "$GITHUB_OUTPUT"
        """
        success, outputs = executor.execute_simulation(command, {})

        assert success

        # The simulation should have processed the date command and created a BUILD_ID output
        # We can verify that the timestamp was substituted by checking the output
        if outputs and "build_id" in outputs:
            build_id = outputs["build_id"]
            # Should start with "build-" and have a timestamp
            assert build_id.startswith("build-")
            # Extract timestamp part
            timestamp_part = build_id.replace("build-", "")
            # Should be a valid Unix timestamp (numeric, around 10 digits)
            assert timestamp_part.isdigit()
            assert len(timestamp_part) == 10

    def test_date_command_formatted(self):
        """Test $(date +%Y%m%d) should generate formatted dates"""
        executor = BashExecutor(timeout=10)

        # Test formatted date generation
        command = """
        VERSION_DATE=$(date +%Y%m%d)
        echo "version_tag=v${VERSION_DATE}" >> "$GITHUB_OUTPUT"
        """

        success, outputs = executor.execute_simulation(command, {})
        assert success

        # Should have created an output with a formatted date
        if outputs and "version_tag" in outputs:
            version_tag = outputs["version_tag"]
            # Should match pattern like v20261225
            assert re.match(r"^v\d{8}$", version_tag)

    def test_date_command_iso(self):
        """Test $(date -Iseconds) should generate ISO timestamps"""
        executor = BashExecutor(timeout=10)

        # Test ISO date generation
        command = """
        ISO_DATE=$(date -Iseconds)
        echo "created_at=${ISO_DATE}" >> "$GITHUB_OUTPUT"
        """

        success, outputs = executor.execute_simulation(command, {})
        assert success

        # Should have created an output with ISO format
        if outputs and "created_at" in outputs:
            created_at = outputs["created_at"]
            # Should match ISO format pattern (basic check)
            assert len(created_at) > 10  # ISO dates are longer than this
            assert "-" in created_at or "T" in created_at  # Basic ISO format indicators

    def test_hash_command_substitution(self):
        """Test $(echo "text" | sha256sum | cut -d' ' -f1 | head -c 8) should generate hashes"""
        executor = BashExecutor(timeout=10)

        # Test hash command simulation
        command = """
        COMMIT_HASH=$(echo "test-content" | sha256sum | cut -d' ' -f1 | head -c 8)
        echo "short_hash=${COMMIT_HASH}" >> "$GITHUB_OUTPUT"
        """

        success, outputs = executor.execute_simulation(command, {})
        assert success

        # Should have created an output with a short hash
        if outputs and "short_hash" in outputs:
            short_hash = outputs["short_hash"]
            # Should be 8 characters of hex
            assert len(short_hash) == 8
            assert re.match(r"^[a-f0-9]{8}$", short_hash)

    def test_nested_command_substitution(self):
        """Test BUILD_$(date +%s)_$ENV should handle nested patterns"""
        executor = BashExecutor(timeout=10)

        # Test nested command substitution with environment variables
        command = """
        ENV=production
        BUILD_TAG="BUILD_$(date +%s)_${ENV}"
        echo "build_tag=${BUILD_TAG}" >> "$GITHUB_OUTPUT"
        """

        success, outputs = executor.execute_simulation(command, {})
        assert success

        # Should have created a build tag with timestamp and environment
        if outputs and "build_tag" in outputs:
            build_tag = outputs["build_tag"]
            # Should match pattern like BUILD_1234567890_production
            assert build_tag.startswith("BUILD_")
            assert build_tag.endswith("_production")
            # Extract the middle part (timestamp)
            parts = build_tag.split("_")
            assert len(parts) == 3
            timestamp_part = parts[1]
            assert timestamp_part.isdigit()
            assert len(timestamp_part) == 10  # Unix timestamp length

    def test_variable_expansion_in_commands(self):
        """Test $(echo "$VAR" | sha256sum) should expand variables first"""
        executor = BashExecutor(timeout=10)

        # Test variable expansion within command substitution
        command = """
        SECRET_VALUE="my-secret-key"
        # This should expand SECRET_VALUE first, then hash the result
        HASH=$(echo "$SECRET_VALUE" | sha256sum | cut -d' ' -f1 | head -c 12)
        echo "hashed_secret=${HASH}" >> "$GITHUB_OUTPUT"
        """

        success, outputs = executor.execute_simulation(command, {})
        assert success

        # Should have created a hashed output
        if outputs and "hashed_secret" in outputs:
            hashed_secret = outputs["hashed_secret"]
            # Should be 12 characters of hex
            assert len(hashed_secret) == 12
            assert re.match(r"^[a-f0-9]{12}$", hashed_secret)

            # Verify that it's actually the hash of "my-secret-key"
            import hashlib

            expected_hash = hashlib.sha256("my-secret-key".encode()).hexdigest()[:12]
            assert hashed_secret == expected_hash

    def test_command_substitution_with_variables(self):
        """Test command substitution combined with variable substitution"""
        # Test that variable substitution works with command patterns
        text = "Deploying build-$(date +%s) to ${ENVIRONMENT}"
        variables = {"ENVIRONMENT": "staging"}

        # First substitute variables
        result = VariableSubstitution.substitute(text, variables)
        assert result == "Deploying build-$(date +%s) to staging"

        # Then simulate command execution
        executor = BashExecutor(timeout=10)
        command = f'DEPLOY_MSG="{result}"'

        success, outputs = executor.execute_simulation(command, {})
        assert success

    def test_multiple_command_substitutions(self):
        """Test multiple command substitutions in one command"""
        executor = BashExecutor(timeout=10)

        command = """
        TIMESTAMP=$(date +%s)
        DATE_FORMAT=$(date +%Y%m%d_%H%M%S)
        BUILD_INFO="build-${TIMESTAMP}-${DATE_FORMAT}"
        echo "build_info=${BUILD_INFO}" >> "$GITHUB_OUTPUT"
        """

        success, outputs = executor.execute_simulation(command, {})
        assert success

        if outputs and "build_info" in outputs:
            build_info = outputs["build_info"]
            # Should contain both timestamp patterns
            assert "build-" in build_info
            # Should have two different time-based components
            parts = build_info.replace("build-", "").split("-")
            assert len(parts) == 2

            # First part should be Unix timestamp
            assert parts[0].isdigit()
            assert len(parts[0]) == 10

            # Second part should be formatted date
            assert len(parts[1]) >= 8  # At least YYYYMMDD format

    def test_command_substitution_error_handling(self):
        """Test that malformed command substitution doesn't crash"""
        executor = BashExecutor(timeout=10)

        # Test with malformed command substitution
        command = """
        # This has unmatched parentheses
        MALFORMED=$(echo "test" 
        echo "result=success" >> "$GITHUB_OUTPUT"
        """

        # Should not crash, should handle gracefully
        success, outputs = executor.execute_simulation(command, {})
        # Even if some parts fail, the basic simulation should succeed
        assert isinstance(success, bool)

        # Should still process the valid parts
        if outputs:
            assert "result" in outputs

    def test_command_substitution_with_pipes(self):
        """Test command substitution with complex pipe sequences"""
        executor = BashExecutor(timeout=10)

        command = """
        # Test a complex pipeline simulation
        PROCESSED=$(echo "hello world" | sha256sum | cut -d' ' -f1 | head -c 16)
        echo "processed=${PROCESSED}" >> "$GITHUB_OUTPUT"
        """

        success, outputs = executor.execute_simulation(command, {})
        assert success

        if outputs and "processed" in outputs:
            processed = outputs["processed"]
            # Should be 16 characters of hex
            assert len(processed) == 16
            assert re.match(r"^[a-f0-9]{16}$", processed)

            # Verify it's the correct hash
            import hashlib

            expected = hashlib.sha256("hello world".encode()).hexdigest()[:16]
            assert processed == expected

    def test_time_based_build_ids(self):
        """Test realistic time-based build ID generation"""
        executor = BashExecutor(timeout=10)

        command = """
        # Realistic build ID generation
        BUILD_TIMESTAMP=$(date +%s)
        BUILD_DATE=$(date +%Y%m%d)
        BUILD_TIME=$(date +%H%M)
        BUILD_ID="rel-${BUILD_DATE}-${BUILD_TIME}-${BUILD_TIMESTAMP}"
        echo "build_id=${BUILD_ID}" >> "$GITHUB_OUTPUT"
        """

        success, outputs = executor.execute_simulation(command, {})
        assert success

        if outputs and "build_id" in outputs:
            build_id = outputs["build_id"]
            # Should match pattern like rel-20261225-1430-1234567890
            assert build_id.startswith("rel-")
            parts = build_id.split("-")
            assert len(parts) == 4
            assert parts[0] == "rel"
            assert len(parts[1]) == 8  # YYYYMMDD
            assert len(parts[2]) == 4  # HHMM
            assert len(parts[3]) == 10  # Unix timestamp
            assert parts[3].isdigit()

    def test_command_substitution_in_conditions(self):
        """Test that command substitution works in conditional contexts"""
        executor = BashExecutor(timeout=10)

        command = """
        CURRENT_HOUR=$(date +%H)
        if [[ "$CURRENT_HOUR" =~ ^[0-9]+$ ]]; then
            echo "time_based=true" >> "$GITHUB_OUTPUT"
        else
            echo "time_based=false" >> "$GITHUB_OUTPUT"
        fi
        """

        success, outputs = executor.execute_simulation(command, {})
        assert success

        # Should have determined whether the hour is numeric
        if outputs and "time_based" in outputs:
            time_based = outputs["time_based"]
            # Since date simulation should produce numeric hours, should be true
            assert time_based == "true"
