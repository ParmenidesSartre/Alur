"""
EventBridge scheduling for Alur pipelines.
Users write Python code to define schedules, framework generates infrastructure.
"""

from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class Schedule:
    """Represents a pipeline schedule."""

    pipeline_name: str
    cron_expression: str
    description: Optional[str] = None
    enabled: bool = True
    timezone: str = "UTC"


class ScheduleRegistry:
    """Global registry for all pipeline schedules."""

    _schedules: Dict[str, Schedule] = {}

    @classmethod
    def register(cls, schedule: Schedule) -> None:
        """Register a schedule."""
        if schedule.pipeline_name in cls._schedules:
            raise ValueError(f"Schedule for pipeline '{schedule.pipeline_name}' already exists")

        cls._schedules[schedule.pipeline_name] = schedule

    @classmethod
    def get(cls, pipeline_name: str) -> Optional[Schedule]:
        """Get a schedule by pipeline name."""
        return cls._schedules.get(pipeline_name)

    @classmethod
    def get_all(cls) -> Dict[str, Schedule]:
        """Get all registered schedules."""
        return cls._schedules.copy()

    @classmethod
    def clear(cls) -> None:
        """Clear all schedules (useful for testing)."""
        cls._schedules.clear()


def schedule(
    cron: str,
    description: Optional[str] = None,
    enabled: bool = True,
    timezone: str = "UTC"
):
    """
    Decorator to schedule a pipeline using EventBridge.

    The decorated pipeline will run on the specified schedule.
    EventBridge rules are automatically generated during deployment.

    Args:
        cron: Cron expression (e.g., "cron(0 12 * * ? *)" for daily at noon UTC)
        description: Human-readable description of the schedule
        enabled: Whether the schedule is active
        timezone: Timezone for the schedule (default: UTC)

    Example:
        @schedule(cron="cron(0 12 * * ? *)", description="Run daily at noon")
        @pipeline(sources={"orders": OrdersSilver}, target=DailySalesGold)
        def calculate_daily_sales(orders):
            return orders.groupBy(...).agg(...)

    Common Cron Patterns (AWS EventBridge format):
        - Every 15 minutes: "cron(0/15 * * * ? *)"
        - Every hour: "cron(0 * * * ? *)"
        - Daily at 2am: "cron(0 2 * * ? *)"
        - Every Monday at 9am: "cron(0 9 ? * MON *)"
        - First day of month: "cron(0 0 1 * ? *)"

    Rate Expressions (alternative to cron):
        - Every 5 minutes: "rate(5 minutes)"
        - Every hour: "rate(1 hour)"
        - Every day: "rate(1 day)"

    Note: AWS EventBridge uses a 6-field cron format:
          minute hour day-of-month month day-of-week year
    """

    def decorator(func):
        # Get the pipeline name from the function
        pipeline_name = func.__name__

        # Check if this function is already decorated with @pipeline
        if not hasattr(func, '_alur_pipeline'):
            raise ValueError(
                f"@schedule must be used with @pipeline decorator. "
                f"Use @schedule above @pipeline for function '{pipeline_name}'"
            )

        # Validate cron expression format
        if not (cron.startswith("cron(") or cron.startswith("rate(")):
            raise ValueError(
                f"Invalid schedule expression: '{cron}'. "
                f"Must start with 'cron(' or 'rate('. "
                f"Examples: 'cron(0 12 * * ? *)', 'rate(1 hour)'"
            )

        # Create and register the schedule
        sched = Schedule(
            pipeline_name=pipeline_name,
            cron_expression=cron,
            description=description or f"Scheduled execution of {pipeline_name}",
            enabled=enabled,
            timezone=timezone
        )

        ScheduleRegistry.register(sched)

        # Attach schedule metadata to the function
        func._alur_schedule = sched

        return func

    return decorator


__all__ = [
    "schedule",
    "Schedule",
    "ScheduleRegistry",
]
