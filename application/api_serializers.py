from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from domain.entities import Line, LineStop


def json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    return value


def line_stop_to_api(line_stop: LineStop) -> dict[str, Any]:
    stop = line_stop.stop
    return {
        "id": str(line_stop.id),
        "line_id": str(line_stop.line_id),
        "stop_id": str(line_stop.stop_id),
        "name": stop.name if stop else None,
        "city": stop.city if stop else None,
        "district": stop.district if stop else None,
        "latitude": json_value(stop.latitude) if stop else None,
        "longitude": json_value(stop.longitude) if stop else None,
        "landmark": stop.landmark if stop else None,
        "order": line_stop.stop_order,
        "stop_order": line_stop.stop_order,
        "is_pickup_allowed": line_stop.is_pickup_allowed,
        "is_dropoff_allowed": line_stop.is_dropoff_allowed,
        "scheduled_offset_minutes": line_stop.scheduled_offset_minutes,
        "created_at": json_value(line_stop.created_at),
        "updated_at": json_value(stop.updated_at) if stop else None,
    }


def line_to_api(line: Line, stops: list[LineStop] | None = None) -> dict[str, Any]:
    return {
        "id": str(line.id),
        "code": line.code,
        "name": line.name,
        "origin_name": line.origin_name,
        "destination_name": line.destination_name,
        "default_duration_minutes": line.default_duration_minutes,
        "default_price": json_value(line.default_price),
        "status": line.status.value,
        "notes": line.notes,
        "created_at": json_value(line.created_at),
        "updated_at": json_value(line.updated_at),
        "stops": [line_stop_to_api(stop) for stop in stops] if stops is not None else [],
    }


def trip_row_to_api(row: dict[str, Any]) -> dict[str, Any]:
    driver_name = " ".join(
        part
        for part in [row.get("driver_first_name"), row.get("driver_last_name")]
        if part
    )
    planned_start = row.get("planned_start_datetime")
    planned_end = row.get("planned_end_datetime")
    price = row.get("base_price") or 0

    return {
        "id": str(row["id"]),
        "line_id": str(row["line_id"]),
        "departure_city": row.get("origin_name"),
        "arrival_city": row.get("destination_name"),
        "departure_time": json_value(planned_start),
        "arrival_time": json_value(planned_end or planned_start),
        "trip_date": json_value(row.get("trip_date")),
        "price": json_value(price),
        "base_price": json_value(row.get("base_price")),
        "available_seats": row.get("capacity_available"),
        "total_seats": row.get("capacity_total"),
        "capacity_total": row.get("capacity_total"),
        "capacity_blocked": row.get("capacity_blocked"),
        "capacity_booked": row.get("capacity_booked"),
        "capacity_available": row.get("capacity_available"),
        "driver_id": str(row["driver_id"]) if row.get("driver_id") else None,
        "driver_name": driver_name,
        "driver_phone": row.get("driver_phone"),
        "vehicle_id": str(row["vehicle_id"]),
        "vehicle_number": row.get("plate_number"),
        "vehicle": {
            "id": str(row["vehicle_id"]),
            "vehicle_code": row.get("vehicle_code"),
            "plate_number": row.get("plate_number"),
            "brand": row.get("brand"),
            "model": row.get("model"),
        },
        "line": {
            "id": str(row["line_id"]),
            "code": row.get("line_code"),
            "name": row.get("line_name"),
            "origin_name": row.get("origin_name"),
            "destination_name": row.get("destination_name"),
        },
        "partner": {
            "id": str(row["partner_id"]),
            "name": row.get("partner_name"),
        },
        "status": row["status"],
        "created_at": json_value(row.get("created_at")),
        "updated_at": json_value(row.get("updated_at")),
    }

