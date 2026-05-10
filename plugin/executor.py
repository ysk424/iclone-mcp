import ast
import io
import sys
import traceback


def exec_code(code, error_mode="minimal"):
    stdout_buf = io.StringIO()
    namespace = {}
    old_stdout = sys.stdout
    sys.stdout = stdout_buf

    try:
        tree = ast.parse(code, mode="exec")
        last_expr = None
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            last_expr = ast.Expression(body=tree.body.pop().value)
            ast.fix_missing_locations(last_expr)

        compiled = compile(tree, "<iclone_exec>", "exec")
        exec(compiled, namespace)

        result = None
        if last_expr is not None:
            result = eval(compile(last_expr, "<iclone_exec>", "eval"), namespace)

        return {
            "status": "ok",
            "result": _safe_repr(result),
            "stdout": stdout_buf.getvalue(),
        }
    except Exception as e:
        return _format_error(e, error_mode)
    finally:
        sys.stdout = old_stdout


def _safe_repr(value):
    if value is None:
        return None
    try:
        return repr(value)
    except Exception:
        return "<unrepresentable>"


def _format_error(exc, error_mode):
    base = {
        "status": "error",
        "type": type(exc).__name__,
        "msg": str(exc),
    }
    if error_mode == "verbose":
        tb = traceback.format_exc()
        base["traceback"] = tb
        frame = sys.exc_info()[2]
        if frame is not None:
            while frame.tb_next:
                frame = frame.tb_next
            base["line"] = frame.tb_lineno
            try:
                base["locals"] = {k: repr(v) for k, v in frame.tb_frame.f_locals.items()}
            except Exception:
                pass
    return base
