from dataclasses import dataclass

@dataclass
class Project:
    """Represent a locally stored project entry."""

    name: str
    description: str
    status: str = "active"
