from dataclasses import asdict
from datetime import datetime
from typing import List, Optional
from models.log import Log
from persistence.storage import StorageInterface

class LogManager:
    """Manage locally stored activity logs for the legacy offline flow."""

    def __init__(self, storage: StorageInterface):
        """Load persisted logs into memory so reads stay fast."""
        self.storage = storage
        self._logs: List[Log] = []
        self._sync_load()

    def _sync_load(self):
        """Rebuild the in-memory cache from the backing storage implementation."""
        data = self.storage.load()
        self._logs = [
            Log(
                description=item.get("description", ""),
                project_name=item.get("project_name", ""),
                activity_name=item.get("activity_name", ""),
                timestamp=item.get("timestamp") or datetime.now().isoformat(),
            )
            for item in data
        ]

    def add_log(self, project_name: str, description: str, activity_name: str = ""):
        """Append a new log entry and persist the updated log list immediately."""
        log = Log(
            project_name=project_name,
            description=description,
            activity_name=activity_name,
        )
        self._logs.append(log)
        self.storage.save([asdict(l) for l in self._logs])
        return log

    def get_logs_for_project(self, project_name: str) -> List[Log]:
        """Return only the logs associated with a single project name."""
        return [l for l in self._logs if l.project_name == project_name]

    def get_last_log(self) -> Optional[Log]:
        """Returns the most recent log entry for smart pre-filling."""
        if not self._logs:
            return None
        # Assuming logs are appended, the last one is the latest.
        # If not, we could sort by timestamp.
        return self._logs[-1]

    def get_all_logs(self) -> List[Log]:
        """Expose the full in-memory log collection in insertion order."""
        return self._logs
