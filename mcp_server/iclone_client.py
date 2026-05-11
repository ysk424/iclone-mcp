import json
import socket

HOST = "localhost"
PORT = 54321
TIMEOUT = 10


def _send(request: dict, timeout: float = TIMEOUT) -> dict:
    with socket.create_connection((HOST, PORT), timeout=timeout) as s:
        s.sendall(json.dumps(request).encode("utf-8"))
        data = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
            try:
                return json.loads(data.decode("utf-8"))
            except json.JSONDecodeError:
                continue
    return {"status": "error", "type": "ConnectionError", "msg": "no response"}


def execute_python(code: str, error_mode: str = "minimal") -> dict:
    return _send({"cmd": "exec", "code": code, "error_mode": error_mode})


def get_screenshot(x: int = 0, y: int = 0, w: int = 1280, h: int = 720, screen: int = 0) -> dict:
    return _send({"cmd": "screenshot", "x": x, "y": y, "w": w, "h": h, "screen": screen})


def call(cmd: str, timeout: float = TIMEOUT, **params) -> dict:
    req = {"cmd": cmd}
    req.update(params)
    return _send(req, timeout=timeout)


def ping() -> bool:
    try:
        r = _send({"cmd": "ping"})
        return r.get("result") == "pong"
    except Exception:
        return False
