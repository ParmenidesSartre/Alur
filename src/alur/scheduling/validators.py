"""
Cron expression validation for AWS EventBridge schedules.
"""

import re


def validate_cron_expression(cron: str) -> None:
    """
    Validate AWS EventBridge cron expression format.

    AWS EventBridge uses 6-field cron format:
    cron(minute hour day-of-month month day-of-week year)

    Args:
        cron: Cron expression string

    Raises:
        ValueError: If cron expression is invalid

    Examples:
        Valid:
            - "0 2 * * ? *" - Daily at 2 AM
            - "0 */4 * * ? *" - Every 4 hours
            - "0 9 ? * MON-FRI *" - Weekdays at 9 AM
            - "15,45 * ? * * *" - At :15 and :45 every hour
            - "0 0 1 * ? *" - First day of every month

        Invalid:
            - "0 2 * * *" - Unix cron (only 5 fields)
            - "invalid" - Not a cron expression
            - "0 2 * * * * *" - Too many fields
    """
    if not cron or not isinstance(cron, str):
        raise ValueError(
            "Cron expression must be a non-empty string"
        )

    # EventBridge cron has 6 space-separated fields
    fields = cron.split()

    if len(fields) != 6:
        raise ValueError(
            f"EventBridge cron expression must have 6 fields, got {len(fields)}. "
            f"Format: 'minute hour day-of-month month day-of-week year'. "
            f"Example: '0 2 * * ? *' (daily at 2 AM UTC)"
        )

    minute, hour, day_of_month, month, day_of_week, year = fields

    # Validate individual fields (basic checks)
    _validate_field(minute, "minute", 0, 59)
    _validate_field(hour, "hour", 0, 23)
    _validate_field(day_of_month, "day-of-month", 1, 31, allow_question=True)
    _validate_field(month, "month", 1, 12, allow_names=True)
    _validate_field(day_of_week, "day-of-week", 1, 7, allow_names=True, allow_question=True)
    _validate_field(year, "year", 1970, 2199)

    # EventBridge requires '?' in either day-of-month OR day-of-week (not both)
    has_question_dom = '?' in day_of_month
    has_question_dow = '?' in day_of_week

    if not (has_question_dom or has_question_dow):
        raise ValueError(
            "EventBridge requires '?' in either day-of-month or day-of-week. "
            "Use '?' to indicate 'no specific value'. "
            f"Example: '0 2 ? * MON *' or '0 2 1 * ? *'"
        )

    if has_question_dom and has_question_dow:
        raise ValueError(
            "Cannot use '?' in both day-of-month and day-of-week. "
            "Use '?' in one and a specific value in the other."
        )


def _validate_field(
    value: str,
    field_name: str,
    min_val: int,
    max_val: int,
    allow_question: bool = False,
    allow_names: bool = False
) -> None:
    """
    Validate a single cron field.

    Args:
        value: Field value to validate
        field_name: Name of the field (for error messages)
        min_val: Minimum allowed numeric value
        max_val: Maximum allowed numeric value
        allow_question: Whether '?' is allowed
        allow_names: Whether named values are allowed (e.g., MON, JAN)
    """
    # Allow wildcards
    if value == '*':
        return

    # Allow question mark if permitted
    if allow_question and value == '?':
        return

    # Allow ranges (e.g., "1-5")
    if '-' in value and value != '-':
        parts = value.split('-')
        if len(parts) == 2:
            # Valid range format, don't validate further
            return

    # Allow lists (e.g., "1,3,5")
    if ',' in value:
        # Valid list format, don't validate further
        return

    # Allow step values (e.g., "*/5", "0-23/2")
    if '/' in value:
        # Valid step format, don't validate further
        return

    # Allow named values for month and day-of-week
    if allow_names:
        named_months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                        'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
        named_days = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']

        if value.upper() in named_months or value.upper() in named_days:
            return

        # Allow ranges with names (e.g., "MON-FRI")
        if '-' in value:
            parts = value.split('-')
            if len(parts) == 2:
                if all(p.upper() in named_days or p.upper() in named_months for p in parts):
                    return

    # Validate numeric values
    if value.isdigit():
        num = int(value)
        if num < min_val or num > max_val:
            raise ValueError(
                f"Field '{field_name}' value {num} is out of range [{min_val}-{max_val}]"
            )
        return

    # If we get here, format is unrecognized (but might still be valid EventBridge syntax)
    # We allow it through to avoid being overly restrictive
    pass


__all__ = ["validate_cron_expression"]
