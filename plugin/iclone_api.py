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

def _ok(**kw):
    d = {"status": "ok"}
    d.update(kw)
    return d


def _err(exc, **kw):
    d = {"status": "error", "type": type(exc).__name__, "msg": str(exc)}
    d.update(kw)
    return d


def _spool_root():
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    path = os.path.join(base, "iclone-mcp", "spool")
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


def get_scene_summary(_req):
    try:
        summary = {
            "avatars": [a.GetName() for a in RLPy.RScene.GetAvatars()],
            "props": [p.GetName() for p in RLPy.RScene.GetProps()],
            "lights": [l.GetName() for l in RLPy.RScene.GetLights()],
            "cameras": [c.GetName() for c in RLPy.RScene.GetCameras()],
        }
        try:
            cam = RLPy.RScene.GetCurrentCamera()
            summary["current_camera"] = cam.GetName() if cam else None
        except Exception:
            summary["current_camera"] = None
        # fps
        for getter in ("GetFps",):
            try:
                summary["fps"] = RLPy.RGlobal.__dict__.get(getter) and getattr(RLPy.RGlobal, getter)()
            except Exception:
                pass
        try:
            summary["fps"] = RLPy.RGlobal.GetFps()
        except Exception:
            summary.setdefault("fps", None)
        # project length / frame range (best effort, API varies by version)
        try:
            length = RLPy.RGlobal.GetProjectLength()
            fps = summary.get("fps")
            end_frame = None
            try:
                end_frame = length.GetFrameIndex(fps) if fps else None
            except Exception:
                end_frame = None
            summary["project_length_ms"] = length.GetValue() if hasattr(length, "GetValue") else str(length)
            summary["end_frame"] = end_frame
        except Exception:
            pass
        try:
            t = RLPy.RGlobal.GetTime()
            summary["current_time_ms"] = t.GetValue() if hasattr(t, "GetValue") else str(t)
        except Exception:
            pass
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


def _build_flags(names, table, none_value, label):
    val = none_value
    bad = []
    for n in names or []:
        if n in table:
            val = val | table[n]
        else:
            bad.append(n)
    if bad:
        raise ValueError("unknown {} flag(s): {}; valid: {}".format(
            label, bad, sorted(k for k in table if k != "_None")))
    return val


_LAST_MANIFEST = {"value": None}


def get_last_export_manifest(_req):
    if _LAST_MANIFEST["value"] is None:
        return _ok(manifest=None)
    return _ok(manifest=_LAST_MANIFEST["value"])


def export_avatar_fbx(req):
    try:
        avatar_name = req.get("avatar")
        avatar = _find_avatar(avatar_name)
        if avatar is None:
            return _err(ValueError("avatar not found: {!r}; scene avatars: {}".format(
                avatar_name, [a.GetName() for a in RLPy.RScene.GetAvatars()])))

        preset = req.get("preset")
        opts = list(req.get("options") or [])
        opts2 = list(req.get("options2") or [])
        opts3 = list(req.get("options3") or [])
        tex_size = req.get("texture_size")
        tex_fmt = req.get("texture_format")
        motion_path = req.get("motion_path") or ""

        if preset:
            p = {"blender": _PRESET_BLENDER}.get(preset)
            if p is None:
                return _err(ValueError("unknown preset: {!r}".format(preset)))
            opts = list(p.get("options", [])) + opts
            opts2 = list(p.get("options2", [])) + opts2
            opts3 = list(p.get("options3", [])) + opts3
            tex_size = tex_size or p.get("texture_size")
            tex_fmt = tex_fmt or p.get("texture_format")

        tex_size = tex_size or "Original"
        tex_fmt = tex_fmt or "Default"

        f1 = _build_flags(opts, _OPT1(), RLPy.EExportFbxOptions__None, "options")
        f2 = _build_flags(opts2, _OPT2(), RLPy.EExportFbxOptions2__None, "options2")
        f3 = _build_flags(opts3, _OPT3(), RLPy.EExportFbxOptions3__None, "options3")

        ts_table = _TEXSIZE()
        tf_table = _TEXFMT()
        if tex_size not in ts_table:
            return _err(ValueError("unknown texture_size: {!r}; valid: {}".format(tex_size, sorted(ts_table))))
        if tex_fmt not in tf_table:
            return _err(ValueError("unknown texture_format: {!r}; valid: {}".format(tex_fmt, sorted(tf_table))))
        ts_val = ts_table[tex_size]
        tf_val = tf_table[tex_fmt]

        out_handle = req.get("out_handle")
        if out_handle:
            out_dir = out_handle
            os.makedirs(out_dir, exist_ok=True)
        else:
            out_dir = _new_spool_dir(avatar.GetName())
        fbx_path = os.path.join(out_dir, avatar.GetName() + ".fbx")

        status = RLPy.RFileIO.ExportFbxFile(
            avatar, fbx_path, f1, f2, f3, ts_val, tf_val, motion_path)
        ok = status == RLPy.RStatus.Success

        # scene metadata for downstream (Blender)
        fps = None
        try:
            fps = RLPy.RGlobal.GetFps()
        except Exception:
            pass
        end_frame = None
        length_ms = None
        try:
            length = RLPy.RGlobal.GetProjectLength()
            length_ms = length.GetValue() if hasattr(length, "GetValue") else None
        except Exception:
            pass

        textures_dir = None
        for cand in ("textures", "texture", avatar.GetName() + ".fbm"):
            p = os.path.join(out_dir, cand)
            if os.path.isdir(p):
                textures_dir = p
                break

        manifest = {
            "avatar_name": avatar.GetName(),
            "fbx": fbx_path,
            "out_dir": out_dir,
            "textures_dir": textures_dir,
            "fps": fps,
            "project_length_ms": length_ms,
            "end_frame": end_frame,
            "applied_options": {"options": opts, "options2": opts2, "options3": opts3,
                                "texture_size": tex_size, "texture_format": tex_fmt,
                                "motion_path": motion_path or None, "preset": preset},
            "next": "blender-mcp",
        }
        _LAST_MANIFEST["value"] = manifest

        if not ok:
            return _err(RuntimeError("ExportFbxFile returned Failure"), manifest=manifest)
        return _ok(handle=out_dir, fbx_path=fbx_path, manifest=manifest)
    except Exception as e:
        return _err(e)


# ---------------------------------------------------------------------------
# command table
# ---------------------------------------------------------------------------

COMMANDS = {
    "list_avatars": list_avatars,
    "get_selection": get_selection,
    "list_motions": list_motions,
    "get_scene_summary": get_scene_summary,
    "list_fbx_export_options": list_fbx_export_options,
    "get_last_export_manifest": get_last_export_manifest,
    "export_avatar_fbx": export_avatar_fbx,
}
