import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugin"))

from executor import exec_code


def test_simple_expression():
    r = exec_code("1 + 1")
    assert r["status"] == "ok"
    assert r["result"] == "2"


def test_stdout_capture():
    r = exec_code("print('hello')")
    assert r["status"] == "ok"
    assert r["stdout"] == "hello\n"


def test_multi_line():
    r = exec_code("x = 10\nx * 2")
    assert r["status"] == "ok"
    assert r["result"] == "20"


def test_error_minimal():
    r = exec_code("undefined_var", error_mode="minimal")
    assert r["status"] == "error"
    assert r["type"] == "NameError"
    assert "traceback" not in r
    assert "locals" not in r


def test_error_verbose():
    r = exec_code("undefined_var", error_mode="verbose")
    assert r["status"] == "error"
    assert r["type"] == "NameError"
    assert "traceback" in r
    assert "line" in r


def test_syntax_error():
    r = exec_code("def (broken")
    assert r["status"] == "error"
    assert r["type"] == "SyntaxError"


def test_no_result_returns_none():
    r = exec_code("x = 42")
    assert r["status"] == "ok"
    assert r["result"] is None


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
