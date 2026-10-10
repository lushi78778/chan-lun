# -*- coding: utf-8 -*-
"""课108精确构造: 同级同因果中枢的第一个三类点, 确认时间前缀。"""
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
from chan import FormationEvent, formation_state


def event(kind, dt, level="day", center="c1"):
    return FormationEvent(kind, dt, level, center)


class TestFormation(unittest.TestCase):
    def setUp(self):
        self.first = event("buy1", 2, center=None)

    def test_waiting(self):
        self.assertEqual(formation_state(None, None, [], 1).phase, "waiting")
        state = formation_state(self.first, "c1", [], 1)
        self.assertEqual(state.phase, "waiting")
        self.assertIsNone(state.start_dt)

    def test_first_point_starts_even_without_center(self):
        state = formation_state(self.first, None, [], 2)
        self.assertTrue(state.in_formation)
        self.assertEqual(state.start_dt, 2)
        self.assertIsNone(state.end_dt)

    def test_buy3_completes_bottom(self):
        state = formation_state(self.first, "c1", [event("buy3", 4)], 4)
        self.assertEqual((state.kind, state.phase, state.end_dt), ("bottom", "completed", 4))
        self.assertFalse(state.in_formation)

    def test_sell3_fails_bottom_and_terminal_sticks(self):
        events = [event("sell3", 4), event("buy3", 6)]
        state = formation_state(self.first, "c1", events, 8)
        self.assertEqual((state.phase, state.end_dt), ("failed", 4))

    def test_top_mirror(self):
        first = event("sell1", 2, center=None)
        for kind, phase in [("sell3", "completed"), ("buy3", "failed")]:
            self.assertEqual(formation_state(first, "c1", [event(kind, 4)], 4).phase, phase)

    def test_unrelated_events_do_not_close(self):
        events = [event("sell3", 1), event("sell3", 3, level="week"),
                  event("sell3", 4, center="other"), event("buy1", 5)]
        self.assertTrue(formation_state(self.first, "c1", events, 5).in_formation)

    def test_future_confirmed_event_hidden(self):
        events = [event("buy3", 7)]
        self.assertTrue(formation_state(self.first, "c1", events, 6).in_formation)
        self.assertEqual(formation_state(self.first, "c1", events, 7).phase, "completed")

    def test_every_confirmed_prefix_matches_as_of(self):
        events = [event("sell3", 3, center="other"), event("buy3", 5), event("sell3", 8)]
        for dt in range(1, 10):
            visible = [e for e in events if e.confirmed_dt <= dt]
            self.assertEqual(formation_state(self.first, "c1", events, dt),
                             formation_state(self.first, "c1", visible, dt))

    def test_same_confirmation_is_ambiguous(self):
        for kinds in [("buy3", "sell3"), ("buy3", "buy3")]:
            with self.assertRaises(ValueError):
                formation_state(self.first, "c1", [event(k, 4) for k in kinds], 4)

    def test_order_rejected_without_sorting(self):
        with self.assertRaises(ValueError):
            formation_state(self.first, "c1", [event("buy3", 6), event("sell3", 4)], 8)

    def test_identity_required_and_consistent(self):
        for center in ["", 1]:
            with self.assertRaises(ValueError):
                formation_state(self.first, center, [], 4)
        with self.assertRaises(ValueError):
            formation_state(self.first, "c1", [event("buy3", 4, center=None)], 4)
        with self.assertRaises(ValueError):
            formation_state(event("buy1", 2), "other", [], 4)

    def test_invalid_event_and_first_point(self):
        for bad in [event("buy2", 4), event("buy3", None), event("buy3", 4, level=""), {}]:
            with self.assertRaises(ValueError):
                formation_state(self.first, "c1", [bad], 4)
        with self.assertRaises(ValueError):
            formation_state(event("buy3", 2), "c1", [], 4)

    def test_time_representation(self):
        day = datetime(2026, 1, 1)
        state = formation_state(event("buy1", day, center=None), "c1",
                                [event("buy3", day + timedelta(days=2))], day + timedelta(days=3))
        self.assertEqual(state.phase, "completed")
        with self.assertRaises(ValueError):
            formation_state(self.first, "c1", [event("buy3", day)], 4)
        with self.assertRaises(ValueError):
            formation_state(self.first, "c1", [], None)

    def test_result_immutable_and_snapshot_owned(self):
        events = [event("buy3", 4)]
        state = formation_state(self.first, "c1", events, 4)
        with self.assertRaises(AttributeError):
            state.phase = "failed"
        snapshot = state.to_dict()
        snapshot["boundary_event"]["kind"] = "sell3"
        self.assertEqual(state.boundary_event.kind, "buy3")
        self.assertEqual(events, [event("buy3", 4)])

    def test_nonfinite_time_rejected(self):
        for dt in [float("nan"), float("inf"), True]:
            with self.assertRaises(ValueError):
                formation_state(event("buy1", dt, center=None), "c1", [], 4)
            with self.assertRaises(ValueError):
                formation_state(self.first, "c1", [], dt)

    def test_event_iterator_captured_once(self):
        events = (event("buy3", dt) for dt in [4])
        self.assertEqual(formation_state(self.first, "c1", events, 4).phase, "completed")


if __name__ == "__main__":
    unittest.main()
