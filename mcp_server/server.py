import base64
import json
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP, Image
import iclone_client as ic
import manual

mcp = FastMCP("iclone-mcp")


def _fmt(r: dict) -> str:
    if r.get("status") == "error":
        out = f"error: {r.get('type')}: {r.get('msg')}"
        extra = {k: v for k, v in r.items() if k not in ("status", "type", "msg")}
        if extra:
            out += "\n" + json.dumps(extra, indent=2, ensure_ascii=False)
        return out
    body = {k: v for k, v in r.items() if k != "status"}
    return json.dumps(body, indent=2, ensure_ascii=False) if body else "(ok)"


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


# --- Phase 1: scene queries (read-only, safe — preferred over execute_python) ---

@mcp.tool()
def list_avatars() -> str:
    """List all avatars in the current iClone scene (name and object type)."""
    return _fmt(ic.call("list_avatars"))


@mcp.tool()
def get_selection() -> str:
    """List the objects currently selected in iClone."""
    return _fmt(ic.call("get_selection"))


@mcp.tool()
def list_motions() -> str:
    """List body motion clips on the timeline for each avatar in the scene."""
    return _fmt(ic.call("list_motions"))


@mcp.tool()
def get_scene_summary() -> str:
    """Summary of the iClone scene: avatars, props, lights, cameras, current camera,
    fps, project length, current time. Useful for matching timeline/units downstream."""
    return _fmt(ic.call("get_scene_summary"))


# --- Phase 2: FBX export (the pipeline bridge to Blender) ---

@mcp.tool()
def list_fbx_export_options() -> str:
    """List every available FBX export flag (options/options2/options3),
    texture sizes, texture formats, and built-in presets. Use this to discover
    valid flag names before calling export_avatar_fbx, e.g. when re-exporting
    with different settings after a Blender import looked wrong."""
    return _fmt(ic.call("list_fbx_export_options"))


# NOTE: FBX export itself is done by a human in iClone's UI — exporting via this
# plugin crashes iClone. These tools only bracket that manual step.

@mcp.tool()
def get_export_recipe(avatar: str = "", out_handle: str = "") -> str:
    """Get an FBX export recipe for a human to follow in iClone: an auto-managed
    output directory, the exact filename to save as, and recommended export flags.
    avatar: avatar name; empty = currently selected avatar.
    out_handle: optional output directory; empty = auto-managed spool dir.
    Tell the human the target_fbx path and the recommended options, then after
    they export, call make_export_manifest with that path."""
    params = {}
    if avatar:
        params["avatar"] = avatar
    if out_handle:
        params["out_handle"] = out_handle
    return _fmt(ic.call("get_export_recipe", **params))


@mcp.tool()
def make_export_manifest(fbx_path: str, avatar: str = "") -> str:
    """After a human exported an FBX from iClone, build a handoff manifest for the
    Blender MCP: avatar name, fbx path, textures dir, fps, frame range, plus a
    JSON sidecar written next to the FBX. Pass the path the human exported to."""
    params = {"fbx_path": fbx_path}
    if avatar:
        params["avatar"] = avatar
    return _fmt(ic.call("make_export_manifest", **params))


@mcp.tool()
def get_last_export_manifest() -> str:
    """Return the manifest from the most recent make_export_manifest call."""
    return _fmt(ic.call("get_last_export_manifest"))


if __name__ == "__main__":
    mcp.run()
