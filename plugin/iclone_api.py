"""Dedicated RLPy API command handlers.

These avoid arbitrary `exec` of Python inside iClone (which crashes easily).
Each handler catches its own exceptions and returns a JSON-safe dict so the
plugin process never dies.
"""

import os
import tempfile
import time

import RLPy


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _jsonable(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    # RLPy value types (RFps, RTime, RVector3, ...) — try common accessors
    for m in ("GetValue", "ToFloat", "ToInt"):
        f = getattr(v, m, None)
        if callable(f):
            try:
                return _jsonable(f())
            except Exception:
                pass
    try:
        return float(v)
    except Exception:
        pass
    return repr(v)


def _ok(**kw):
    d = {"status": "ok"}
    d.update({k: _jsonable(v) for k, v in kw.items()})
    return d


def _err(exc, **kw):
    d = {"status": "error", "type": type(exc).__name__, "msg": str(exc)}
    d.update({k: _jsonable(v) for k, v in kw.items()})
    return d


def _spool_root():
    # somewhere a human can actually navigate to from a Save dialog
    home = os.path.expanduser("~")
    docs = os.path.join(home, "Documents")
    base = docs if os.path.isdir(docs) else (os.environ.get("LOCALAPPDATA") or tempfile.gettempdir())
    path = os.path.join(base, "iclone-mcp-spool")
    os.makedirs(path, exist_ok=True)
    return path


def _new_spool_dir(name):
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in (name or "export"))
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(_spool_root(), "{}_{}".format(stamp, safe))
    os.makedirs(path, exist_ok=True)
    return path


def _obj_type_name(obj):
    try:
        t = obj.GetType()
    except Exception:
        return type(obj).__name__
    # RLPy exposes EObjectType_* constants; map back to a readable name
    for attr in dir(RLPy):
        if attr.startswith("EObjectType_") and getattr(RLPy, attr) == t:
            return attr[len("EObjectType_"):]
    return str(t)


def _find_avatar(name):
    avatars = RLPy.RScene.GetAvatars()
    if not name:
        sel = RLPy.RScene.GetSelectedObjects()
        for o in sel:
            if o in avatars:
                return o
        if len(avatars) == 1:
            return avatars[0]
        if avatars:
            return avatars[0]
        return None
    for a in avatars:
        if a.GetName() == name:
            return a
    return None


# ---------------------------------------------------------------------------
# Phase 1 — read-only scene queries
# ---------------------------------------------------------------------------

def list_avatars(_req):
    try:
        out = []
        for a in RLPy.RScene.GetAvatars():
            out.append({
                "name": a.GetName(),
                "type": _obj_type_name(a),
            })
        return _ok(avatars=out, count=len(out))
    except Exception as e:
        return _err(e)


def get_selection(_req):
    try:
        out = []
        for o in RLPy.RScene.GetSelectedObjects():
            out.append({"name": o.GetName(), "type": _obj_type_name(o)})
        return _ok(selection=out, count=len(out))
    except Exception as e:
        return _err(e)


def list_motions(_req):
    try:
        out = []
        for a in RLPy.RScene.GetAvatars():
            sk = a.GetSkeletonComponent()
            clips = []
            try:
                n = sk.GetClipCount()
            except Exception:
                n = 0
            for i in range(n):
                try:
                    c = sk.GetClip(i)
                    if c is None:
                        continue
                    clips.append({
                        "index": i,
                        "name": c.GetName(),
                    })
                except Exception:
                    pass
            out.append({"avatar": a.GetName(), "clips": clips})
        return _ok(motions=out)
    except Exception as e:
        return _err(e)


def _scene_names(getter):
    try:
        fn = getattr(RLPy.RScene, getter, None)
        if fn is None:
            return None
        return [o.GetName() for o in fn()]
    except Exception:
        return None


def _fps_value():
    try:
        return float(RLPy.RGlobal.GetFps().ToFloat())
    except Exception:
        try:
            return float(RLPy.RGlobal.GetFps())
        except Exception:
            return None


def _frame_of(rtime):
    try:
        return RLPy.RGlobal.GetFps().GetFrameIndex(rtime)
    except Exception:
        return None


def get_scene_summary(_req):
    try:
        summary = {
            "avatars": _scene_names("GetAvatars"),
            "props": _scene_names("GetProps"),
            "lights": _scene_names("GetLights"),
            "cameras": _scene_names("GetCameras"),
        }
        try:
            cam = RLPy.RScene.GetCurrentCamera()
            summary["current_camera"] = cam.GetName() if cam else None
        except Exception:
            summary["current_camera"] = None
        summary["fps"] = _fps_value()
        try:
            summary["end_frame"] = _frame_of(RLPy.RGlobal.GetProjectLength())
        except Exception:
            summary["end_frame"] = None
        try:
            summary["current_frame"] = _frame_of(RLPy.RGlobal.GetTime())
        except Exception:
            summary["current_frame"] = None
        return _ok(summary=summary)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# Phase 2 — FBX export
# ---------------------------------------------------------------------------

def _collect_enum(prefix):
    out = {}
    for attr in dir(RLPy):
        if attr.startswith(prefix):
            out[attr[len(prefix):]] = getattr(RLPy, attr)
    return out


_OPT1 = lambda: _collect_enum("EExportFbxOptions_")
_OPT2 = lambda: _collect_enum("EExportFbxOptions2_")
_OPT3 = lambda: _collect_enum("EExportFbxOptions3_")
_TEXSIZE = lambda: _collect_enum("EExportTextureSize_")
_TEXFMT = lambda: _collect_enum("EExportTextureFormat_")


# Starting-point preset for Blender import. Tuned by trial on real hardware.
_PRESET_BLENDER = {
    "options": [
        "RemoveAllUnused",
        "ExportPbrTextureAsImageInOneDirectory",
        "ExportRootMotion",
    ],
    "options2": [
        "YUp",
        "RenameDuplicateMaterialName",
        "RenameDuplicateBoneName",
        "RenameDuplicateMorphName",
    ],
    "options3": [
        "ExportJson",
    ],
    "texture_size": "Original",
    "texture_format": "Default",
}


def list_fbx_export_options(_req):
    try:
        def base(prefix, table):
            return sorted(k for k in table if k and k != "_None")
        return _ok(
            options=base("EExportFbxOptions_", _OPT1()),
            options2=base("EExportFbxOptions2_", _OPT2()),
            options3=base("EExportFbxOptions3_", _OPT3()),
            texture_size=sorted(_TEXSIZE().keys()),
            texture_format=sorted(_TEXFMT().keys()),
            presets={"blender": _PRESET_BLENDER},
        )
    except Exception as e:
        return _err(e)


# NOTE: exporting FBX from this plugin crashes iClone (heavy RLPy call from the
# TCP worker thread / clashing with the export progress UI). So the export is
# done by a human in iClone's UI; the tools below only (a) tell the human where
# to export and with what settings, and (b) build a handoff manifest afterwards.

def get_export_recipe(req):
    """Suggest an output directory, filename and FBX export flags for a human to use."""
    try:
        avatar = _find_avatar(req.get("avatar"))
        if avatar is None:
            return _err(ValueError("avatar not found: {!r}; scene avatars: {}".format(
                req.get("avatar"), [a.GetName() for a in RLPy.RScene.GetAvatars()])))
        name = avatar.GetName()
        out_dir = req.get("out_handle") or _new_spool_dir(name)
        os.makedirs(out_dir, exist_ok=True)
        fbx_path = os.path.join(out_dir, name + ".fbx")
        return _ok(
            avatar_name=name,
            target_dir=out_dir,
            target_fbx=fbx_path,
            recommended=_PRESET_BLENDER,
            note=("In iClone: select '{}', File > Export > FBX, save to the path "
                  "in target_fbx, and enable the options under 'recommended'. "
                  "Then call make_export_manifest with that path.").format(name),
        )
    except Exception as e:
        return _err(e)


_LAST_MANIFEST = {"value": None}


def make_export_manifest(req):
    """After a human exported an FBX, gather scene metadata + file layout into a
    manifest (and write it as JSON next to the FBX) for the Blender MCP."""
    try:
        fbx_path = req.get("fbx_path")
        if not fbx_path:
            return _err(ValueError("fbx_path is required"))
        if not os.path.isfile(fbx_path):
            return _err(ValueError("file not found: {}".format(fbx_path)))
        out_dir = os.path.dirname(fbx_path)
        stem = os.path.splitext(os.path.basename(fbx_path))[0]

        avatar = _find_avatar(req.get("avatar") or stem)
        avatar_name = avatar.GetName() if avatar else (req.get("avatar") or stem)

        texture_dirs = []
        for cand in (stem + ".fbm", "textures", "texture", "Texture"):
            p = os.path.join(out_dir, cand)
            if os.path.isdir(p):
                texture_dirs.append(p)
        textures_dir = texture_dirs[0] if texture_dirs else None

        json_sidecar = None
        cand = os.path.join(out_dir, stem + ".json")
        if os.path.isfile(cand):
            json_sidecar = cand

        try:
            end_frame = _frame_of(RLPy.RGlobal.GetProjectLength())
        except Exception:
            end_frame = None

        manifest = _jsonable({
            "source": "iclone",
            "avatar_name": avatar_name,
            "fbx": fbx_path,
            "out_dir": out_dir,
            "textures_dir": textures_dir,
            "texture_dirs": texture_dirs,
            "iclone_json_sidecar": json_sidecar,
            "fps": _fps_value(),
            "end_frame": end_frame,
            "next": "blender-mcp",
        })
        _LAST_MANIFEST["value"] = manifest
        manifest_path = os.path.join(out_dir, stem + ".iclone_manifest.json")
        try:
            import json as _json
            with open(manifest_path, "w", encoding="utf-8") as f:
                _json.dump(manifest, f, indent=2, ensure_ascii=False)
            manifest["manifest_path"] = manifest_path
        except Exception:
            pass
        return _ok(manifest=manifest)
    except Exception as e:
        return _err(e)


def get_last_export_manifest(_req):
    return _ok(manifest=_LAST_MANIFEST["value"])


# ---------------------------------------------------------------------------
# command table
# ---------------------------------------------------------------------------

COMMANDS = {
    "list_avatars": list_avatars,
    "get_selection": get_selection,
    "list_motions": list_motions,
    "get_scene_summary": get_scene_summary,
    "list_fbx_export_options": list_fbx_export_options,
    "get_export_recipe": get_export_recipe,
    "make_export_manifest": make_export_manifest,
    "get_last_export_manifest": get_last_export_manifest,
}
