"""Transport lifecycle: UTC deadlines and server-owned action availability."""
from datetime import datetime, timedelta, timezone

HOLD_MINUTES = 15

def utc(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def sales_close(row):
    departure = utc(row.get("planned_start_datetime"))
    close = utc(row.get("booking_close_at"))
    return min(departure, close) if departure and close else departure

def sale_open(row, now=None):
    now = now or datetime.now(timezone.utc)
    close = sales_close(row)
    return row.get("status") == "scheduled" and close is not None and now < close

def expiry(row):
    deadline = utc(row.get("expires_at"))
    created = utc(row.get("booking_created_at") or row.get("created_at"))
    return deadline or (created + timedelta(minutes=HOLD_MINUTES) if created else None)

def payable(row, now=None):
    now = now or datetime.now(timezone.utc)
    deadline = expiry(row)
    return (row.get("booking_status") == "pending" and deadline is not None
            and now < deadline and sale_open(row, now))

def lifecycle(row, now=None):
    now = now or datetime.now(timezone.utc)
    status = row.get("booking_status")
    departure = utc(row.get("planned_start_datetime"))
    end = utc(row.get("planned_end_datetime"))
    finished = row.get("status") == "completed" or (end is not None and now >= end)
    paid = row.get("payment_status") == "paid"
    used = status in ("boarded", "completed")
    if status == "cancelled" or row.get("status") == "cancelled":
        journey = "cancelled"
    elif status == "expired" or (status == "pending" and not payable(row, now)):
        journey = "expired"
    elif finished or status in ("completed", "no_show"):
        journey = "completed" if used else "no_show"
    elif used:
        journey = "boarded"
    elif departure and now >= departure:
        journey = "in_progress"
    elif row.get("status") == "boarding":
        journey = "boarding"
    else:
        journey = "upcoming"
    # A ticket may be displayed before boarding, but can only be consumed in
    # the boarding window. Missing end time never creates an unlimited window.
    ticket_end = min(end, departure + timedelta(minutes=15)) if end and departure else (
        departure + timedelta(minutes=15) if departure else None)
    active = (status == "confirmed" and paid and departure is not None
              and row.get("status") in ("scheduled", "boarding")
              and ticket_end is not None and now < ticket_end and not finished)
    ticket = "used" if used else ("valid" if active else "expired")
    return {
        "journey_status": journey, "ticket_status": ticket,
        "can_pay": payable(row, now),
        "can_cancel": (status in ("pending", "confirmed") and journey in ("upcoming", "boarding")
                       and departure is not None and now < departure - timedelta(minutes=60)),
        "can_show_ticket": active,
        "can_board": active and now >= departure - timedelta(minutes=30),
    }
