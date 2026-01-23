"""
Pipeline Scheduling for Alur Framework.
Enable cron-based scheduling via Glue SCHEDULED triggers.
"""

from typing import Callable, Optional, Dict
from dataclasses import dataclass
from functools import wraps


@dataclass
class Schedule:
    """Represents a pipeline schedule."""

    pipeline_name: str
    cron: str
    enabled: bool = True
    timezone: str = "UTC"
    description: Optional[str] = None
    max_concurrent_runs: int = 1


class ScheduleRegistry:
    """Global registry for pipeline schedules."""

    _schedules: Dict[str, Schedule] = {}

    @classmethod
    def register(cls, schedule: Schedule) -> None:
        """
        Register a schedule for a pipeline.

        Args:
            schedule: Schedule instance to register

        Raises:
            ValueError: If a schedule for this pipeline is already registered
        """
        if schedule.pipeline_name in cls._schedules:
            raise ValueError(
                f"Schedule for pipeline '{schedule.pipeline_name}' is already registered. "
                "Each pipeline can only have one schedule."
            )
        cls._schedules[schedule.pipeline_name] = schedule

    @classmethod
    def get(cls, pipeline_name: str) -> Optional[Schedule]:
        """
        Get schedule for a specific pipeline.

        Args:
            pipeline_name: Name of the pipeline

        Returns:
            Schedule instance or None if not found
        """
        return cls._schedules.get(pipeline_name)

    @classmethod
    def get_all(cls) -> Dict[str, Schedule]:
        """Get all registered schedules."""
        return cls._schedules.copy()

    @classmethod
    def get_enabled(cls) -> Dict[str, Schedule]:
        """Get only enabled schedules."""
        return {
            name: schedule
            for name, schedule in cls._schedules.items()
            if schedule.enabled
        }

    @classmethod
    def clear(cls) -> None:
        """Clear all schedules (useful for testing and code generation)."""
        cls._schedules.clear()


def schedule(
    cron: str,
    enabled: bool = True,
    timezone: str = "UTC",
    description: Optional[str] = None,
    max_concurrent_runs: int = 1
):
    """
    Decorator to schedule a pipeline for automatic execution.

    Generates Glue SCHEDULED triggers during Terraform deployment.
    Must be applied BEFORE @pipeline decorator.

    Args:
        cron: AWS Glue cron expression (6 fields)
              Format: "minute hour day-of-month month day-of-week year"
              Examples:
                - "0 2 * * ? *" - Daily at 2 AM UTC
                - "0 */4 * * ? *" - Every 4 hours
                - "0 9 ? * MON-FRI *" - Weekdays at 9 AM
        enabled: Whether schedule is active (default: True)
        timezone: Timezone for documentation purposes (Glue triggers use UTC)
        description: Human-readable description of the schedule
        max_concurrent_runs: Maximum concurrent executions (default: 1)

    Example:
        @schedule(cron="0 2 * * ? *", description="Daily ingestion")
        @pipeline(sources={}, target=OrdersBronze)
        def ingest_orders():
            return load_to_bronze(...)

    Note:
        AWS Glue uses 6-field cron format, same as EventBridge, different from Unix cron (5 fields).
        Use '?' for either day-of-month or day-of-week (not both).
    """
    from alur.scheduling.validators import validate_cron_expression

    # Validate cron expression format
    validate_cron_expression(cron)

    def decorator(func: Callable) -> Callable:
        # Get pipeline name from function
        pipeline_name = func.__name__

        # Create schedule instance
        sched = Schedule(
            pipeline_name=pipeline_name,
            cron=cron,
            enabled=enabled,
            timezone=timezone,
            description=description or f"Scheduled execution of {pipeline_name}",
            max_concurrent_runs=max_concurrent_runs
        )

        # Register schedule
        ScheduleRegistry.register(sched)

        # Attach schedule to function (dual-storage pattern)
        func._alur_schedule = sched

        return func

    return decorator


__all__ = [
    "Schedule",
    "ScheduleRegistry",
    "schedule",
]
