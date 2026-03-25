import json
from abc import ABC, abstractmethod
from typing import List, Any
from pathlib import Path

class StorageInterface(ABC):
    """Abstract contract for list-based persistence backends."""

    @abstractmethod
    def save(self, data: List[Any]):
        """Persist a complete collection snapshot."""
        pass

    @abstractmethod
    def load(self) -> List[Any]:
        """Load the last saved collection snapshot."""
        pass

class JSONStorage(StorageInterface):
    """Persist structured list data to a local JSON file."""

    def __init__(self, file_path: str):
        """Remember the file path used for future load and save calls."""
        self.file_path = Path(file_path)

    def save(self, data: List[Any]):
        """Serialize the provided collection to disk as formatted JSON."""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except IOError as e:
            print(f"Error saving to {self.file_path}: {e}")

    def load(self) -> List[Any]:
        """Return the stored JSON collection, or an empty list when unavailable."""
        if not self.file_path.exists():
            return []
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            print(f"Error loading from {self.file_path}")
            return []
