import pytest
from core.temporal_degradation import TemporalDegradation
from datetime import datetime, timezone, timedelta

def test_exponential_decay_half_life():
    """Test that weight is exactly halved after one half-life period."""
    td = TemporalDegradation(half_life_days=30)
    initial_weight = 1.0
    # Create a timestamp exactly 30 days ago
    timestamp = datetime.now(timezone.utc).timestamp() - (30 * 24 * 60 * 60)
    
    new_weight = td.calculate_weight(initial_weight, timestamp)
    assert new_weight == pytest.approx(0.5)

def test_pinned_facts_do_not_decay():
    """Test that pinned facts maintain their weight regardless of time."""
    td = TemporalDegradation(half_life_days=30)
    fact = {
        "weight": 1.0,
        "pinned": True,
        "created_at": datetime.now(timezone.utc).timestamp() - (60 * 24 * 60 * 60) # 60 days ago
    }
    
    new_weight, should_delete = td.apply(fact)
    assert new_weight == 1.0
    assert should_delete is False

def test_pruning_threshold():
    """Test that facts are marked for deletion when they drop below 20%."""
    td = TemporalDegradation(half_life_days=30, threshold=0.2)
    initial_weight = 1.0
    # After 3 half-lives (90 days), weight is 1.0 * (0.5^3) = 0.125
    timestamp = datetime.now(timezone.utc).timestamp() - (90 * 24 * 60 * 60)
    
    weight = td.calculate_weight(initial_weight, timestamp)
    assert weight < 0.2
    assert td.should_delete(weight) is True

def test_apply_decay_and_delete():
    """Test the end-to-end apply method for a non-pinned fact."""
    td = TemporalDegradation(half_life_days=30, threshold=0.2)
    fact = {
        "weight": 1.0,
        "pinned": False,
        "created_at": datetime.now(timezone.utc).timestamp() - (100 * 24 * 60 * 60) # ~100 days ago
    }
    
    new_weight, should_delete = td.apply(fact)
    assert new_weight < 0.2
    assert should_delete is True

def test_recent_facts_do_not_decay_significantly():
    """Test that very recent facts retain most of their weight."""
    td = TemporalDegradation(half_life_days=30)
    initial_weight = 1.0
    # 1 hour ago
    timestamp = datetime.now(timezone.utc).timestamp() - 3600
    
    new_weight = td.calculate_weight(initial_weight, timestamp)
    assert new_weight == pytest.approx(1.0, rel=1e-3)