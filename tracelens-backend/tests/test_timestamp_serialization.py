from datetime import datetime, timedelta, timezone

from fastapi.encoders import jsonable_encoder

from app.serialization import clean


def test_database_datetimes_are_serialized_as_utc_without_changing_the_instant():
    naive_database_time = datetime(2026, 10, 24, 10, 0, 0)
    offset_database_time = datetime(
        2026, 10, 24, 15, 30, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))
    )

    result = jsonable_encoder(
        clean(
            {
                "_id": "removed",
                "created_at": naive_database_time,
                "timeline": [{"timestamp": offset_database_time}],
            }
        )
    )

    assert "_id" not in result
    assert result["created_at"] == "2026-10-24T10:00:00+00:00"
    assert result["timeline"][0]["timestamp"] == "2026-10-24T10:00:00+00:00"
    assert naive_database_time.tzinfo is None
    assert offset_database_time.utcoffset() == timedelta(hours=5, minutes=30)
