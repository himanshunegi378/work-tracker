"""Run any function on a background thread and report the result through Qt signals."""

import logging
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

logger = logging.getLogger(__name__)


class _Signals(QObject):
    result_ready = Signal(object)
    error_occurred = Signal(str)


class CallWorker(QRunnable):
    """Call `fn()` off the GUI thread. Never touch widgets inside `fn`."""

    def __init__(self, fn: Callable[[], Any]):
        super().__init__()
        self.fn = fn
        self.signals = _Signals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.result_ready.emit(self.fn())
        except Exception as exc:  # noqa: BLE001 - shown to the user by the presenter
            logger.exception("Background call failed")
            self.signals.error_occurred.emit(str(exc) or exc.__class__.__name__)
