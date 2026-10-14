"""Unix-socket fan-out to UI clients, driven by the GLib main loop.

Everything runs on the main loop thread, so DBus signals emitted in
response to UI commands never race with DBus method handlers.
"""

import os
import socket
import sys

from gi.repository import GLib

_WATCH = GLib.IOCondition.IN | GLib.IOCondition.HUP | GLib.IOCondition.ERR


class Hub:
    def __init__(self, path, on_command, state_path=None):
        self.path = path
        self.state_path = state_path or (path.rsplit(".", 1)[0] + "-state.json")
        self.on_command = on_command
        self.clients = {}  # socket -> [watch id, read buffer]
        self.last = None   # latest state line, replayed to new clients

        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(path)
        os.chmod(path, 0o600)
        self.srv.listen(8)
        self.srv.setblocking(False)
        self._srv_watch = GLib.io_add_watch(self.srv, GLib.PRIORITY_DEFAULT,
                                            GLib.IOCondition.IN, self._accept)

    def _accept(self, *_):
        try:
            conn, _ = self.srv.accept()
        except BlockingIOError:
            return True
        conn.setblocking(False)
        wid = GLib.io_add_watch(conn, GLib.PRIORITY_DEFAULT, _WATCH, self._readable)
        self.clients[conn] = [wid, b""]
        if self.last is not None:
            self._send(conn, self.last)
        return True

    def _readable(self, conn, cond):
        if conn not in self.clients:
            return False
        try:
            chunk = conn.recv(4096) if cond & GLib.IOCondition.IN else b""
        except BlockingIOError:
            return True
        except OSError:
            chunk = b""
        if not chunk:
            self._drop(conn, remove_watch=False)
            return False
        entry = self.clients[conn]
        entry[1] += chunk
        while b"\n" in entry[1]:
            line, entry[1] = entry[1].split(b"\n", 1)
            cmd = line.decode("utf-8", "replace").strip()
            if cmd:
                try:
                    self.on_command(cmd)
                except Exception as e:  # never let a bad command kill the loop
                    print("kimpanel: command %r failed: %r" % (cmd, e), file=sys.stderr)
        return True

    def broadcast(self, line, remember=True):
        if remember:
            self.last = line
            try:
                tmp = self.state_path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(line + "\n")
                os.replace(tmp, self.state_path)
            except OSError as e:
                print("kimpanel: state file write failed: %r" % (e,), file=sys.stderr)
        for conn in list(self.clients):
            self._send(conn, line)

    def _send(self, conn, line):
        data = (line + "\n").encode("utf-8")
        try:
            if conn.send(data) != len(data):
                raise BlockingIOError
        except OSError:
            # A stalled or gone client; it reconnects and gets `last` replayed.
            self._drop(conn)

    def _drop(self, conn, remove_watch=True):
        entry = self.clients.pop(conn, None)
        if entry and remove_watch:
            GLib.source_remove(entry[0])
        conn.close()

    def close(self):
        for conn in list(self.clients):
            self._drop(conn)
        GLib.source_remove(self._srv_watch)
        self.srv.close()
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass
