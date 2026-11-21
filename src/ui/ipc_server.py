"""Loopback socket server that lets the CLI control the running desktop app."""

import logging
from typing import Dict, Optional

from PySide6.QtCore import QObject, QTimer
from PySide6.QtNetwork import QHostAddress, QTcpServer, QTcpSocket

from src.core import ipc

logger = logging.getLogger(__name__)
_REQUEST_TIMEOUT_MS = 3000


class IpcServer(QObject):
    """Accept one-line JSON requests on 127.0.0.1 and answer through `handler`.

    Everything runs on the GUI thread (Qt delivers socket events there), so the
    handler can safely touch widgets.
    """

    def __init__(self, handler: ipc.Handler, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._handler = handler
        self._token = ipc.new_token()
        self._server = QTcpServer(self)
        self._server.newConnection.connect(self._on_connection)
        self._buffers: Dict[QTcpSocket, bytearray] = {}
        self._alive: set = set()

    @property
    def port(self) -> int:
        return self._server.serverPort()

    def start(self) -> bool:
        if not self._server.listen(QHostAddress.LocalHost, 0):
            logger.error("IPC server could not listen: %s", self._server.errorString())
            return False
        ipc.write_endpoint(self.port, self._token)
        logger.info("IPC server listening on 127.0.0.1:%s", self.port)
        return True

    def stop(self) -> None:
        self._server.close()
        ipc.remove_endpoint(self._token)

    def _on_connection(self) -> None:
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            self._buffers[sock] = bytearray()
            self._alive.add(sock)
            sock.readyRead.connect(lambda s=sock: self._on_ready(s))
            sock.disconnected.connect(lambda s=sock: self._drop(s))
            QTimer.singleShot(_REQUEST_TIMEOUT_MS, lambda s=sock: self._drop(s, abort=True))

    def _on_ready(self, sock: QTcpSocket) -> None:
        buffer = self._buffers.get(sock)
        if buffer is None:
            return
        buffer.extend(bytes(sock.readAll()))
        if len(buffer) > ipc.MAX_MESSAGE_BYTES:
            self._drop(sock, abort=True)
            return
        if b"\n" in buffer:
            line = bytes(buffer).split(b"\n", 1)[0]
            sock.write(ipc.process_request(line, self._token, self._handler))
            sock.flush()
            self._buffers.pop(sock, None)
            sock.disconnectFromHost()

    def _drop(self, sock: QTcpSocket, abort: bool = False) -> None:
        """Forget a connection exactly once (called on disconnect, size limit or timeout)."""
        if sock not in self._alive:
            return
        self._alive.discard(sock)
        self._buffers.pop(sock, None)
        try:
            if abort:
                sock.abort()
            sock.deleteLater()
        except RuntimeError:  # already deleted
            pass
