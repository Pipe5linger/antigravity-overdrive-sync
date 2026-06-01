class BaseInjector:
    """Abstract interface defining the requirements for ULM Memory Injectors."""
    
    def __init__(self, target_file=None):
        self.target_file = target_file
        
    def inject(self, sync_data, dry_run=False):
        """
        Parses master sync_state.yaml data, formats the appropriate payload,
        and atomically injects it into the target configuration / prompt file.
        """
        raise NotImplementedError("Injectors must implement inject.")
