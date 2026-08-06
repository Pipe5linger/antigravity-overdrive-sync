import unittest
from datetime import datetime, timezone
from core.temporal_degradation import TemporalDegradation

class TestTemporalDegradation(unittest.TestCase):
    def test_exponential_decay_half_life(self):
        """Test that weight is exactly halved after one half-life period."""
        td = TemporalDegradation(half_life_days=30)
        initial_weight = 1.0
        timestamp = datetime.now(timezone.utc).timestamp() - (30 * 24 * 60 * 60)
        new_weight = td.calculate_weight(initial_weight, timestamp)
        self.assertAlmostEqual(new_weight, 0.5, places=2)

    def test_pinned_facts_do_not_decay(self):
        """Test that pinned facts maintain their weight regardless of time."""
        td = TemporalDegradation(half_life_days=30)
        fact = {
            "weight": 1.0,
            "pinned": True,
            "created_at": datetime.now(timezone.utc).timestamp() - (60 * 24 * 60 * 60)
        }
        new_weight, should_delete = td.apply(fact)
        self.assertEqual(new_weight, 1.0)
        self.assertFalse(should_delete)

    def test_pruning_threshold(self):
        """Test that facts are marked for deletion when they drop below threshold."""
        td = TemporalDegradation(half_life_days=30, threshold=0.2)
        initial_weight = 1.0
        timestamp = datetime.now(timezone.utc).timestamp() - (90 * 24 * 60 * 60)
        weight = td.calculate_weight(initial_weight, timestamp)
        self.assertTrue(weight < 0.2)
        self.assertTrue(td.should_delete(weight))

if __name__ == "__main__":
    unittest.main()