import json
from abc import ABC, abstractmethod
from typing import List, Any
from pathlib import Path

class StorageInterface(ABC):
    @abstractmethod
    def save(self, data: List[Any]):
        """Persists the data."""
        pass

    @abstractmethod
    def load(self) -> List[Any]:
        """Loads and returns the data."""
        pass

class JSONStorage(StorageInterface):
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)

    def save(self, data: List[Any]):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except IOError as e:
            print(f"Error saving to {self.file_path}: {e}")

    def load(self) -> List[Any]:
        if not self.file_path.exists():
            return []
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            print(f"Error loading from {self.file_path}")
            return []
