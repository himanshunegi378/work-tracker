from dataclasses import dataclass

@dataclass
class Project:
    name: str
    description: str
    status: str = "active"
