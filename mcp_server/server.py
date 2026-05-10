import base64
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP, Image
import iclone_client as ic
import manual

mcp = FastMCP("iclone-mcp")


@mcp.tool()
def get_manual_index() -> str:
    """Return the list of all available iClone RLPy API class names grouped by category.
    Format: Category/ClassName (e.g. Scene/RIAvatar, Animation/RISkeletonComponent).
    Call this first to discover available classes before calling get_manual_entry."""
    names = manual.get_index()
    if not names:
        return "(Manual index not yet available)"
    return "\n".join(names)


@mcp.tool()
def get_manual_entry(name: str) -> str:
    """Return the full reference page for a specific RLPy API class.
    Use get_manual_index to get valid names (format: Category/ClassName).
    Example: get_manual_entry('Scene/RIAvatar')"""
    entry = manual.get_entry(name)
    if entry is None:
        return f"Entry '{name}' not found. Call get_manual_index to see available names."
    return entry


@mcp.tool()
def search_manual(keyword: str) -> str:
    """Search across all iClone RLPy API reference pages for a keyword.
    Returns matching class names and the lines containing the keyword.
    Useful for finding which class has a specific method or property."""
    return manual.search(keyword)


@mcp.tool()
def execute_python(code: str, error_mode: str = "minimal") -> str:
    """Execute Python code inside iClone via the RLPy API.
    Returns result and stdout on success, or error info on failure.
    error_mode: 'minimal' (default) returns type+message only to save tokens.
                'verbose' returns full traceback and local variables."""
    r = ic.execute_python(code, error_mode)
    if r["status"] == "ok":
        parts = []
        if r.get("result") is not None:
            parts.append(f"result: {r['result']}")
        if r.get("stdout"):
            parts.append(f"stdout:\n{r['stdout']}")
        return "\n".join(parts) if parts else "(no output)"
    else:
        parts = [f"error: {r['type']}: {r['msg']}"]
        if "traceback" in r:
            parts.append(f"traceback:\n{r['traceback']}")
        if "locals" in r:
            parts.append(f"locals: {r['locals']}")
        return "\n".join(parts)


@mcp.tool()
def get_screenshot(x: int = 0, y: int = 0, width: int = 1280, height: int = 720, screen: int = 0) -> Image:
    """Capture a screenshot of the iClone viewport.
    Returns an image showing the current iClone screen state."""
    r = ic.get_screenshot(x, y, width, height, screen)
    if r["status"] != "ok":
        raise RuntimeError(f"Screenshot failed: {r.get('msg', 'unknown error')}")
    return Image(data=base64.b64decode(r["image"]), format="png")


if __name__ == "__main__":
    mcp.run()
