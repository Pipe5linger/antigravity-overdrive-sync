import os

class BaseParser:
    """Abstract interface defining the requirements for ULM Log Parsers."""
    
    def __init__(self, source_dir=None):
        self.source_dir = source_dir
        
    def extract_transcript(self, filepath, session_id):
        """
        Parses a single conversation log file.
        Should return a standard list of message turns.
        """
        raise NotImplementedError("Parsers must implement extract_transcript.")
        
    def fetch_new_logs(self):
        """
        Crawls the target log directory and returns normalized payloads.
        Standard payload schema:
        [
            {
                "chat_id": str,
                "last_mutated": ISO timestamp,
                "messages": [ {"sender": str, "timestamp": str, "text": str} ]
            }
        ]
        """
        raise NotImplementedError("Parsers must implement fetch_new_logs.")
