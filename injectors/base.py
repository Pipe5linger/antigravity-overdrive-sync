class BaseInjector:
    """Abstract interface defining the requirements for ULM Memory Injectors."""
    
    def __init__(self, target_file=None):
        self.target_file = target_file
        
    def inject(self, db=None, dry_run=False, project_tag=None) -> bool:
        """
        Parses master memory/persona state, formats the appropriate payload,
        and atomically injects it into the target configuration / prompt file.
        """
        raise NotImplementedError("Injectors must implement inject.")
