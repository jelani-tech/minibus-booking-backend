import unittest
from datetime import datetime, timedelta, timezone
from services.booking_lifecycle import lifecycle, payable, sale_open


class BookingLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
        self.row = dict(status='scheduled', booking_status='pending', payment_status='pending',
                        booking_created_at=self.now, expires_at=self.now + timedelta(minutes=15),
                        planned_start_datetime=self.now + timedelta(hours=2),
                        planned_end_datetime=self.now + timedelta(hours=3))

    def test_sales_and_expiry_boundaries_are_exclusive(self):
        self.assertTrue(payable(self.row, self.now))
        self.assertFalse(payable(self.row, self.row['expires_at']))
        self.assertFalse(sale_open(self.row, self.row['planned_start_datetime']))
        self.row['booking_close_at'] = self.now
        self.assertFalse(sale_open(self.row, self.now))

    def test_boarding_is_not_a_sales_state(self):
        self.row['status'] = 'boarding'
        self.assertFalse(payable(self.row, self.now))

    def test_ticket_needs_payment_and_one_valid_window(self):
        self.row.update(booking_status='confirmed', payment_status='paid')
        departure = self.row['planned_start_datetime']
        self.assertFalse(lifecycle(self.row, self.now)['can_board'])
        self.assertTrue(lifecycle(self.row, departure - timedelta(minutes=30))['can_board'])
        self.assertFalse(lifecycle(self.row, departure + timedelta(minutes=15))['can_board'])
        self.row['payment_status'] = 'pending'
        self.assertFalse(lifecycle(self.row, departure)['can_board'])

    def test_used_ticket_and_finished_journey_are_distinct_from_payment(self):
        self.row.update(booking_status='boarded', payment_status='paid')
        self.assertEqual(lifecycle(self.row, self.now)['ticket_status'], 'used')
        end = self.row['planned_end_datetime']
        self.assertEqual(lifecycle(self.row, end)['journey_status'], 'completed')
        self.row['booking_status'] = 'confirmed'
        self.assertEqual(lifecycle(self.row, end)['journey_status'], 'no_show')

    def test_cancelled_trip_disables_all_actions(self):
        self.row.update(status='cancelled', booking_status='confirmed', payment_status='paid')
        state = lifecycle(self.row, self.now)
        self.assertEqual(state['journey_status'], 'cancelled')
        for key in ('can_pay', 'can_cancel', 'can_board', 'can_show_ticket'):
            self.assertFalse(state[key])

    def test_naive_timestamps_are_treated_as_utc(self):
        self.row['planned_start_datetime'] = self.row['planned_start_datetime'].replace(tzinfo=None)
        self.assertTrue(payable(self.row, self.now))
