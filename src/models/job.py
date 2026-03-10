from dataclasses import dataclass, field
from typing import Callable
import time

@dataclass
class Job:
    name: str
    task_func: Callable
    interval_seconds: int
    last_run: float = field(default_factory=time.time)

    def is_due(self) -> bool:
        """Checks if the job is due for execution based on its interval."""
        return (time.time() - self.last_run) >= self.interval_seconds

    def set_due_now(self):
        """Offsets the last_run so the job is due immediately."""
        self.last_run = time.time() - self.interval_seconds

    def update_last_run(self):
        """Updates the timestamp of the last execution."""
        self.last_run = time.time()
