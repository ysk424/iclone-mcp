"""Layer 2 test — requires iClone running with plugin loaded."""
import json
import socket
import sys

HOST = "localhost"
PORT = 54321


def send(request):
    with socket.create_connection((HOST, PORT), timeout=5) as s:
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
    return None


def test_ping():
    r = send({"cmd": "ping"})
    assert r["status"] == "ok" and r["result"] == "pong"


def test_exec_basic():
    r = send({"cmd": "exec", "code": "1+1"})
    assert r["status"] == "ok" and r["result"] == "2"


def test_exec_error_minimal():
    r = send({"cmd": "exec", "code": "bad_var", "error_mode": "minimal"})
    assert r["status"] == "error"
    assert "traceback" not in r


def test_exec_error_verbose():
    r = send({"cmd": "exec", "code": "bad_var", "error_mode": "verbose"})
    assert r["status"] == "error"
    assert "traceback" in r


def test_screenshot():
    r = send({"cmd": "screenshot", "x": 0, "y": 0, "w": 256, "h": 256})
    assert r["status"] == "ok"
    assert "image" in r


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
