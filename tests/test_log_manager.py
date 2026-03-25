import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from services.log_manager import LogManager


class MemoryStorage:
    def __init__(self, initial_data=None):
        self.data = list(initial_data or [])

    def save(self, data):
        self.data = list(data)

    def load(self):
        return list(self.data)


class TestLogManager(unittest.TestCase):
    def test_loads_legacy_logs_without_activity_name(self):
        storage = MemoryStorage(
            [
                {
                    "project_name": "Project A",
                    "description": "Legacy log",
                    "timestamp": "2026-03-25T09:00:00",
                }
            ]
        )

        manager = LogManager(storage)

        self.assertEqual(len(manager.get_all_logs()), 1)
        self.assertEqual(manager.get_last_log().activity_name, "")

    def test_add_log_persists_activity_name(self):
        storage = MemoryStorage()
        manager = LogManager(storage)

        manager.add_log("Project A", "Documented feature", "Documentation")

        self.assertEqual(storage.data[0]["activity_name"], "Documentation")


if __name__ == "__main__":
    unittest.main()
