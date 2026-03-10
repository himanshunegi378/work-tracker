from dataclasses import asdict
from typing import List, Optional
from models.log import Log
from persistence.storage import StorageInterface

class LogManager:
    def __init__(self, storage: StorageInterface):
        self.storage = storage
        self._logs: List[Log] = []
        self._sync_load()

    def _sync_load(self):
        data = self.storage.load()
        self._logs = [Log(**item) for item in data]

    def add_log(self, project_name: str, description: str):
        log = Log(project_name=project_name, description=description)
        self._logs.append(log)
        self.storage.save([asdict(l) for l in self._logs])
        return log

    def get_logs_for_project(self, project_name: str) -> List[Log]:
        return [l for l in self._logs if l.project_name == project_name]

    def get_last_log(self) -> Optional[Log]:
        """Returns the most recent log entry for smart pre-filling."""
        if not self._logs:
            return None
        # Assuming logs are appended, the last one is the latest.
        # If not, we could sort by timestamp.
        return self._logs[-1]

    def get_all_logs(self) -> List[Log]:
        return self._logs
