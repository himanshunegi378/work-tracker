"""Run any function on a background thread and report the result through Qt signals."""

import logging
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

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


class _Relay(QObject):
    """Receives one worker's outcome on the GUI thread.

    Worker signals connected to bare closures have no Qt receiver: if the worker's signal
    object is destroyed while a result is still queued, Qt delivers the event to a dead
    object and the app segfaults. This QObject lives on the GUI thread and outlives the
    call, so the hand-over is safe.
    """

    def __init__(self, on_done: Callable[[Any], None], on_error: Callable[[str], None], parent: QObject):
        super().__init__(parent)
        self._on_done, self._on_error = on_done, on_error

    @Slot(object)
    def done(self, result: Any) -> None:
        try:
            self._on_done(result)
        finally:
            self.deleteLater()

    @Slot(str)
    def failed(self, message: str) -> None:
        try:
            self._on_error(message)
        finally:
            self.deleteLater()


def run_in_background(
    fn: Callable[[], Any],
    on_done: Callable[[Any], None],
    on_error: Callable[[str], None],
    parent: QObject,
) -> None:
    """Run `fn()` on the thread pool, then call `on_done(result)` or `on_error(message)` on the GUI thread.

    `parent` must be a QObject living on the GUI thread (usually the presenter).
    """
    worker = CallWorker(fn)
    relay = _Relay(on_done, on_error, parent)
    worker.signals.result_ready.connect(relay.done)
    worker.signals.error_occurred.connect(relay.failed)
    QThreadPool.globalInstance().start(worker)
