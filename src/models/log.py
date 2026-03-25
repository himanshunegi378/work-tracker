from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Log:
    """Represent one locally recorded work log entry."""

    description: str
    project_name: str
    activity_name: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
