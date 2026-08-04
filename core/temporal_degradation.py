import math
from datetime import datetime, timezone

class TemporalDegradation:
    """
    Handles the exponential decay of memory weight over time.
    Facts lose weight as they age, eventually being pruned if they fall below a threshold,
    unless they are explicitly pinned.
    """
    def __init__(self, half_life_days=30, threshold=0.2):
        self.half_life_days = half_life_days
        self.threshold = threshold
        # Seconds in the half-life period
        self.half_life_seconds = half_life_days * 24 * 60 * 60

    def calculate_weight(self, initial_weight: float, timestamp: float) -> float:
        """
        Calculate the decayed weight of a fact based on its creation timestamp.
        Formula: W = W0 * (0.5 ^ (t / half_life))
        """
        if initial_weight is None:
            initial_weight = 1.0
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).timestamp()

        now = datetime.now(timezone.utc).timestamp()
        elapsed_seconds = now - timestamp
        
        if elapsed_seconds <= 0:
            return initial_weight
        
        # Exponential decay based on half-life
        decay_factor = 0.5 ** (elapsed_seconds / self.half_life_seconds)
        return initial_weight * decay_factor

    def should_delete(self, weight: float) -> bool:
        """Returns True if the weight has dropped below the pruning threshold."""
        return weight < self.threshold

    def apply(self, fact: dict) -> tuple[float, bool]:
        """
        Processes a fact and returns (new_weight, should_delete).
        Pinned facts are immune to decay.
        """
        if fact.get("pinned") is True:
            return fact.get("weight", 1.0), False
        
        initial_weight = fact.get("weight", 1.0)
        # Default to now if timestamp is missing or None
        timestamp = fact.get("created_at")
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).timestamp()
        
        new_weight = self.calculate_weight(initial_weight, timestamp)
        delete_fact = self.should_delete(new_weight)
        
        return new_weight, delete_fact