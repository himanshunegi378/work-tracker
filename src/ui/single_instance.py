"""Make sure only one desktop app runs per user (stale locks from crashes are recovered)."""

from pathlib import Path

from PySide6.QtCore import QLockFile


class SingleInstance:
    def __init__(self, lock_path: Path):
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = QLockFile(str(lock_path))
        # QLockFile also checks that the owning process is alive, so a crashed
        # app's lock is taken over immediately; this is only the fallback age.
        self._lock.setStaleLockTime(60_000)

    def acquire(self) -> bool:
        """True if this process is now the single running instance."""
        return self._lock.tryLock(200)

    def release(self) -> None:
        self._lock.unlock()
