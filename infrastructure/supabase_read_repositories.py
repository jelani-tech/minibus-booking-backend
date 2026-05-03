from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text

from domain.entities import Line, LineStop, Stop, StopStatus
from domain.supabase_mapping import line_from_row, trip_from_row
from models.public import db


class SupabaseLineRepository:
    def list_active(self) -> list[Line]:
        rows = db.session.execute(
            text(
                """
                select *
                from public.lines
                where status = 'active'
                order by name
                """
            )
        ).mappings()
        return [line_from_row(dict(row)) for row in rows]

    def get(self, line_id: UUID) -> Line | None:
        row = (
            db.session.execute(
                text(
                    """
                    select *
                    from public.lines
                    where id = cast(:line_id as uuid)
                    """
                ),
                {"line_id": str(line_id)},
            )
            .mappings()
            .first()
        )
        return line_from_row(dict(row)) if row else None

    def get_stops(self, line_id: UUID) -> list[LineStop]:
        rows = db.session.execute(
            text(
                """
                select
                    ls.id,
                    ls.line_id,
                    ls.stop_id,
                    ls.stop_order,
                    ls.is_pickup_allowed,
                    ls.is_dropoff_allowed,
                    ls.scheduled_offset_minutes,
                    ls.created_at,
                    s.name as stop_name,
                    s.city,
                    s.district,
                    s.latitude,
                    s.longitude,
                    s.landmark,
                    s.status as stop_status,
                    s.created_at as stop_created_at,
                    s.updated_at as stop_updated_at
                from public.line_stops ls
                join public.stops s on s.id = ls.stop_id
                where ls.line_id = cast(:line_id as uuid)
                  and s.status = 'active'
                order by ls.stop_order
                """
            ),
            {"line_id": str(line_id)},
        ).mappings()

        line_stops: list[LineStop] = []
        for row_proxy in rows:
            row = dict(row_proxy)
            stop = Stop(
                id=row["stop_id"],
                name=row["stop_name"],
                city=row.get("city"),
                district=row.get("district"),
                latitude=row.get("latitude"),
                longitude=row.get("longitude"),
                landmark=row.get("landmark"),
                status=StopStatus(row["stop_status"]),
                created_at=row.get("stop_created_at"),
                updated_at=row.get("stop_updated_at"),
            )
            line_stops.append(
                LineStop(
                    id=row["id"],
                    line_id=row["line_id"],
                    stop_id=row["stop_id"],
                    stop_order=row["stop_order"],
                    is_pickup_allowed=row["is_pickup_allowed"],
                    is_dropoff_allowed=row["is_dropoff_allowed"],
                    scheduled_offset_minutes=row["scheduled_offset_minutes"],
                    created_at=row.get("created_at"),
                    stop=stop,
                )
            )
        return line_stops


class SupabaseTripRepository:
    def search(
        self,
        *,
        line_id: UUID | None = None,
        origin_name: str | None = None,
        destination_name: str | None = None,
        trip_date: date | None = None,
    ) -> list[dict[str, Any]]:
        clauses = [
            "t.status in ('scheduled', 'boarding')",
            "t.capacity_available > 0",
        ]
        params: dict[str, Any] = {}

        if line_id:
            clauses.append("t.line_id = cast(:line_id as uuid)")
            params["line_id"] = str(line_id)
        if origin_name:
            clauses.append("l.origin_name ilike :origin_name")
            params["origin_name"] = f"%{origin_name}%"
        if destination_name:
            clauses.append("l.destination_name ilike :destination_name")
            params["destination_name"] = f"%{destination_name}%"
        if trip_date:
            clauses.append("t.trip_date = :trip_date")
            params["trip_date"] = trip_date.isoformat()

        where_sql = " and ".join(clauses)
        rows = db.session.execute(
            text(
                f"""
                select
                    t.*,
                    l.code as line_code,
                    l.name as line_name,
                    l.origin_name,
                    l.destination_name,
                    p.name as partner_name,
                    v.vehicle_code,
                    v.plate_number,
                    v.brand,
                    v.model,
                    d.first_name as driver_first_name,
                    d.last_name as driver_last_name,
                    d.phone as driver_phone
                from public.trips t
                join public.lines l on l.id = t.line_id
                join public.partners p on p.id = t.partner_id
                join public.vehicles v on v.id = t.vehicle_id
                left join public.drivers d on d.id = t.driver_id
                where {where_sql}
                order by t.planned_start_datetime
                """
            ),
            params,
        ).mappings()
        return [dict(row) for row in rows]

    def get(self, trip_id: UUID) -> dict[str, Any] | None:
        row = (
            db.session.execute(
                text(
                    """
                    select
                        t.*,
                        l.code as line_code,
                        l.name as line_name,
                        l.origin_name,
                        l.destination_name,
                        p.name as partner_name,
                        v.vehicle_code,
                        v.plate_number,
                        v.brand,
                        v.model,
                        d.first_name as driver_first_name,
                        d.last_name as driver_last_name,
                        d.phone as driver_phone
                    from public.trips t
                    join public.lines l on l.id = t.line_id
                    join public.partners p on p.id = t.partner_id
                    join public.vehicles v on v.id = t.vehicle_id
                    left join public.drivers d on d.id = t.driver_id
                    where t.id = cast(:trip_id as uuid)
                    """
                ),
                {"trip_id": str(trip_id)},
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def get_domain(self, trip_id: UUID):
        row = self.get(trip_id)
        return trip_from_row(row) if row else None
