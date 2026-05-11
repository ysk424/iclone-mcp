import json
import socket
import threading

from executor import exec_code

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 54321
RECV_SIZE = 65536


def handle_client(conn):
    try:
        data = b""
        while True:
            chunk = conn.recv(RECV_SIZE)
            if not chunk:
                break
            data += chunk
            try:
                request = json.loads(data.decode("utf-8"))
                response = dispatch(request)
                conn.sendall(json.dumps(response).encode("utf-8"))
                break
            except json.JSONDecodeError:
                continue
    except Exception as e:
        try:
            conn.sendall(json.dumps({"status": "error", "type": "ServerError", "msg": str(e)}).encode("utf-8"))
        except Exception:
            pass
    finally:
        conn.close()


def dispatch(request):
    cmd = request.get("cmd")
    if cmd == "ping":
        return {"status": "ok", "result": "pong"}
    if cmd == "exec":
        code = request.get("code", "")
        error_mode = request.get("error_mode", "minimal")
        return exec_code(code, error_mode)
    if cmd == "screenshot":
        return _screenshot(request)
    # dedicated RLPy API commands (imported lazily so non-iClone test envs work)
    try:
        import iclone_api
    except Exception as e:
        return {"status": "error", "type": "ImportError", "msg": f"iclone_api unavailable: {e}"}
    handler = iclone_api.COMMANDS.get(cmd)
    if handler is not None:
        try:
            return handler(request)
        except Exception as e:
            return {"status": "error", "type": type(e).__name__, "msg": str(e)}
    return {"status": "error", "type": "UnknownCommand", "msg": f"unknown cmd: {cmd}"}


def _screenshot(request):
    try:
        import shiboken2
        from PySide2 import QtGui, QtWidgets
        import RLPy

        x = request.get("x", 0)
        y = request.get("y", 0)
        w = request.get("w", 1280)
        h = request.get("h", 720)
        screen_index = request.get("screen", 0)

        screens = QtWidgets.QApplication.screens()
        if screen_index >= len(screens):
            return {"status": "error", "type": "ValueError", "msg": "screen index out of range"}

        screen = screens[screen_index]
        pixmap = screen.grabWindow(0, x, y, w, h)

        import io, base64
        buf = io.BytesIO()
        # QPixmap -> PNG bytes via QBuffer
        from PySide2.QtCore import QBuffer, QIODevice
        qbuf = QBuffer()
        qbuf.open(QIODevice.WriteOnly)
        pixmap.save(qbuf, "PNG")
        png_bytes = bytes(qbuf.data())
        encoded = base64.b64encode(png_bytes).decode("ascii")
        return {"status": "ok", "image": encoded, "width": pixmap.width(), "height": pixmap.height()}
    except Exception as e:
        return {"status": "error", "type": type(e).__name__, "msg": str(e)}


def start_server(host=DEFAULT_HOST, port=DEFAULT_PORT):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(5)

    def _accept_loop():
        while True:
            try:
                conn, _ = server.accept()
                t = threading.Thread(target=handle_client, args=(conn,), daemon=True)
                t.start()
            except Exception:
                break

    t = threading.Thread(target=_accept_loop, daemon=True)
    t.start()
    return server
