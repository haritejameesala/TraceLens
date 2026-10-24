"""Serialization helpers that do not require a live database connection."""
from datetime import datetime, timezone


def clean(doc):
    """Remove MongoDB's internal ID and normalize all datetimes to UTC.

    Naive datetimes returned by MongoDB are interpreted as UTC, matching the
    application's UTC storage contract. The original input object is not mutated.
    """
    if doc is None:
        return None

    def normalize_datetimes(value):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        if isinstance(value, dict):
            return {key: normalize_datetimes(item) for key, item in value.items()}
        if isinstance(value, list):
            return [normalize_datetimes(item) for item in value]
        if isinstance(value, tuple):
            return [normalize_datetimes(item) for item in value]
        return value

    result = dict(doc)
    result.pop("_id", None)
    return normalize_datetimes(result)
