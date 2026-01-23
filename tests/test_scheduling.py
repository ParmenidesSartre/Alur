"""
Tests for pipeline scheduling functionality.
"""

import pytest
from alur.scheduling import Schedule, ScheduleRegistry, schedule
from alur.scheduling.validators import validate_cron_expression


class TestCronValidation:
    """Test cron expression validation."""

    def test_valid_cron_expressions(self):
        """Test that valid cron expressions pass validation."""
        valid_crons = [
            "0 2 * * ? *",  # Daily at 2 AM
            "0 */4 * * ? *",  # Every 4 hours
            "0 9 ? * MON-FRI *",  # Weekdays at 9 AM
            "15,45 * ? * * *",  # At :15 and :45 every hour
            "0 0 1 * ? *",  # First day of every month
            "0 12 ? * SUN *",  # Every Sunday at noon
            "*/5 * * * ? *",  # Every 5 minutes
        ]

        for cron in valid_crons:
            validate_cron_expression(cron)  # Should not raise

    def test_invalid_cron_too_few_fields(self):
        """Test that Unix cron (5 fields) is rejected."""
        with pytest.raises(ValueError, match="must have 6 fields"):
            validate_cron_expression("0 2 * * *")

    def test_invalid_cron_too_many_fields(self):
        """Test that cron with too many fields is rejected."""
        with pytest.raises(ValueError, match="must have 6 fields"):
            validate_cron_expression("0 2 * * ? * *")

    def test_invalid_cron_missing_question_mark(self):
        """Test that cron without ? in day-of-month or day-of-week is rejected."""
        with pytest.raises(ValueError, match="requires '\\?' in either"):
            validate_cron_expression("0 2 * * * *")

    def test_invalid_cron_question_in_both(self):
        """Test that cron with ? in both fields is rejected."""
        with pytest.raises(ValueError, match="Cannot use '\\?' in both"):
            validate_cron_expression("0 2 ? * ? *")

    def test_invalid_cron_empty_string(self):
        """Test that empty string is rejected."""
        with pytest.raises(ValueError, match="must be a non-empty string"):
            validate_cron_expression("")

    def test_invalid_cron_non_string(self):
        """Test that non-string values are rejected."""
        with pytest.raises(ValueError, match="must be a non-empty string"):
            validate_cron_expression(None)


class TestScheduleRegistry:
    """Test ScheduleRegistry functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        ScheduleRegistry.clear()

    def test_register_schedule(self):
        """Test registering a schedule."""
        sched = Schedule(
            pipeline_name="test_pipeline",
            cron="0 2 * * ? *",
            description="Test schedule"
        )

        ScheduleRegistry.register(sched)

        assert ScheduleRegistry.get("test_pipeline") == sched
        assert "test_pipeline" in ScheduleRegistry.get_all()

    def test_register_duplicate_raises_error(self):
        """Test that registering duplicate schedule raises error."""
        sched1 = Schedule(pipeline_name="test_pipeline", cron="0 2 * * ? *")
        sched2 = Schedule(pipeline_name="test_pipeline", cron="0 3 * * ? *")

        ScheduleRegistry.register(sched1)

        with pytest.raises(ValueError, match="already registered"):
            ScheduleRegistry.register(sched2)

    def test_get_nonexistent_returns_none(self):
        """Test that getting nonexistent schedule returns None."""
        assert ScheduleRegistry.get("nonexistent") is None

    def test_get_all_returns_copy(self):
        """Test that get_all returns a copy."""
        sched = Schedule(pipeline_name="test", cron="0 2 * * ? *")
        ScheduleRegistry.register(sched)

        all_schedules = ScheduleRegistry.get_all()
        all_schedules["fake"] = None  # Modify copy

        # Original should be unchanged
        assert "fake" not in ScheduleRegistry.get_all()

    def test_get_enabled_filters_correctly(self):
        """Test that get_enabled only returns enabled schedules."""
        sched1 = Schedule(pipeline_name="enabled1", cron="0 2 * * ? *", enabled=True)
        sched2 = Schedule(pipeline_name="disabled", cron="0 3 * * ? *", enabled=False)
        sched3 = Schedule(pipeline_name="enabled2", cron="0 4 * * ? *", enabled=True)

        ScheduleRegistry.register(sched1)
        ScheduleRegistry.register(sched2)
        ScheduleRegistry.register(sched3)

        enabled = ScheduleRegistry.get_enabled()

        assert len(enabled) == 2
        assert "enabled1" in enabled
        assert "enabled2" in enabled
        assert "disabled" not in enabled

    def test_clear(self):
        """Test clearing the registry."""
        sched = Schedule(pipeline_name="test", cron="0 2 * * ? *")
        ScheduleRegistry.register(sched)

        assert len(ScheduleRegistry.get_all()) == 1

        ScheduleRegistry.clear()

        assert len(ScheduleRegistry.get_all()) == 0


class TestScheduleDecorator:
    """Test @schedule decorator."""

    def setup_method(self):
        """Clear registry before each test."""
        ScheduleRegistry.clear()

    def test_decorator_registers_schedule(self):
        """Test that decorator registers schedule in registry."""
        @schedule(cron="0 2 * * ? *", description="Test")
        def test_pipeline():
            pass

        sched = ScheduleRegistry.get("test_pipeline")
        assert sched is not None
        assert sched.pipeline_name == "test_pipeline"
        assert sched.cron == "0 2 * * ? *"
        assert sched.description == "Test"

    def test_decorator_attaches_to_function(self):
        """Test that decorator attaches schedule to function."""
        @schedule(cron="0 2 * * ? *")
        def test_pipeline():
            pass

        assert hasattr(test_pipeline, "_alur_schedule")
        assert test_pipeline._alur_schedule.pipeline_name == "test_pipeline"

    def test_decorator_with_all_parameters(self):
        """Test decorator with all parameters."""
        @schedule(
            cron="0 9 ? * MON-FRI *",
            enabled=False,
            timezone="America/New_York",
            description="Weekday morning job",
            max_concurrent_runs=2
        )
        def test_pipeline():
            pass

        sched = ScheduleRegistry.get("test_pipeline")
        assert sched.cron == "0 9 ? * MON-FRI *"
        assert sched.enabled is False
        assert sched.timezone == "America/New_York"
        assert sched.description == "Weekday morning job"
        assert sched.max_concurrent_runs == 2

    def test_decorator_with_defaults(self):
        """Test decorator with default parameters."""
        @schedule(cron="0 2 * * ? *")
        def test_pipeline():
            pass

        sched = ScheduleRegistry.get("test_pipeline")
        assert sched.enabled is True
        assert sched.timezone == "UTC"
        assert sched.max_concurrent_runs == 1
        assert "test_pipeline" in sched.description  # Auto-generated

    def test_decorator_rejects_invalid_cron(self):
        """Test that decorator rejects invalid cron expressions."""
        with pytest.raises(ValueError, match="must have 6 fields"):
            @schedule(cron="0 2 * * *")  # Unix cron (5 fields)
            def test_pipeline():
                pass

    def test_decorator_prevents_duplicate_schedules(self):
        """Test that decorating same function twice raises error."""
        @schedule(cron="0 2 * * ? *")
        def test_pipeline():
            pass

        with pytest.raises(ValueError, match="already registered"):
            @schedule(cron="0 3 * * ? *")
            def test_pipeline():
                pass


class TestScheduleDataclass:
    """Test Schedule dataclass."""

    def test_schedule_creation(self):
        """Test creating a Schedule instance."""
        sched = Schedule(
            pipeline_name="test",
            cron="0 2 * * ? *",
            enabled=True,
            timezone="UTC",
            description="Test schedule",
            max_concurrent_runs=1
        )

        assert sched.pipeline_name == "test"
        assert sched.cron == "0 2 * * ? *"
        assert sched.enabled is True
        assert sched.timezone == "UTC"
        assert sched.description == "Test schedule"
        assert sched.max_concurrent_runs == 1

    def test_schedule_defaults(self):
        """Test Schedule default values."""
        sched = Schedule(pipeline_name="test", cron="0 2 * * ? *")

        assert sched.enabled is True
        assert sched.timezone == "UTC"
        assert sched.description is None
        assert sched.max_concurrent_runs == 1
