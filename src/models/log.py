from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Log:
    description: str
    project_name: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
