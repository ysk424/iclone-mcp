"""Fetch IC8 Python API wiki pages and build manual/index.json."""
import json
import re
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE_URL = "https://wiki.reallusion.com/IC_Python_API:RLPy_{}"

CLASSES = {
    "Mathematics": [
        "RMath", "RVector2", "RVector3", "RVector4", "RMatrix3",
        "RQuaternion", "RTransform", "RRgb", "RColor",
    ],
    "System": [
        "RStatus", "RTime", "RVariant", "RFileIO", "RGlobal",
        "RPyTimer", "RApplication",
    ],
    "Scene": [
        "RIBase", "RIObject", "RINode", "RIMaterialComponent", "RIProp",
        "RIAvatar", "RICamera", "RIParticle", "RILight", "RISpotLight",
        "RIPointLight", "RIDirectionalLight", "RScene",
    ],
    "Animation": [
        "RDataBlock", "RKey", "RControl", "RFloatControl", "RTransformControl",
        "RlClip", "RISkeletonComponent", "RVisemeSmoothOption",
        "RIVisemeComponent", "RIMorphComponent", "RIHikEffectorComponent",
        "RIFaceComponent",
    ],
    "MotionCapture": [
        "RPositionSetting", "RRotationSetting", "RDeviceSetting",
        "RIDeviceBase", "RBodySetting", "RIBodyDevice", "RHandSetting",
        "RIHandDevice", "RFacialSetting", "RIFacialDevice", "RIMocapManager",
    ],
    "Events": [
        "RCallback", "RWinMessageCallback", "RDialogCallback",
        "REventCallback", "REventHandler", "RPyTimerCallback", "RIEventListener",
    ],
    "UI": ["RIDialog", "RIDockWidget", "RUi"],
    "Media": [
        "RIAudioObject", "RAudioRecorder", "RAudio", "RAudioRecorderCallback",
    ],
    "Networking": [
        "RTcpCallback", "RTcpClient", "RUdpCallback", "RUdpClient",
    ],
}

def strip_html(html: str) -> str:
    # Remove scripts and styles
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    # Extract main content between mw-content-text div
    m = re.search(r'<div[^>]+id="mw-content-text"[^>]*>(.*?)<div[^>]+class="[^"]*printfooter', html, re.DOTALL)
    if m:
        html = m.group(1)
    # Convert headers
    html = re.sub(r'<h2[^>]*>.*?<span[^>]*>(.*?)</span>.*?</h2>', r'\n## \1\n', html, flags=re.DOTALL)
    html = re.sub(r'<h3[^>]*>.*?<span[^>]*>(.*?)</span>.*?</h3>', r'\n### \1\n', html, flags=re.DOTALL)
    html = re.sub(r'<h4[^>]*>(.*?)</h4>', r'\n#### \1\n', html, flags=re.DOTALL)
    # Convert code blocks
    html = re.sub(r'<pre[^>]*>(.*?)</pre>', lambda m: '\n```python\n' + re.sub(r'<[^>]+>', '', m.group(1)) + '\n```\n', html, flags=re.DOTALL)
    # Convert table rows to readable format
    html = re.sub(r'<tr[^>]*>', '\n', html)
    html = re.sub(r'<th[^>]*>(.*?)</th>', r'| \1 ', html, flags=re.DOTALL)
    html = re.sub(r'<td[^>]*>(.*?)</td>', r'| \1 ', html, flags=re.DOTALL)
    # Convert links
    html = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'\2', html, flags=re.DOTALL)
    # Remove remaining tags
    html = re.sub(r'<[^>]+>', '', html)
    # Decode HTML entities
    html = html.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    html = html.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
    html = html.replace('&#160;', ' ').replace('&rarr;', '->').replace('&larr;', '<-')
    # Clean up whitespace
    html = re.sub(r'\n{3,}', '\n\n', html)
    html = re.sub(r'[ \t]+\n', '\n', html)
    return html.strip()


def fetch(class_name: str) -> str:
    url = BASE_URL.format(class_name)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        return strip_html(html)
    except urllib.error.HTTPError as e:
        return f"(HTTP {e.code}: {url})"
    except Exception as e:
        return f"(Error: {e})"


def main():
    out_path = Path(__file__).parent.parent / "manual" / "index.json"
    index = {}

    total = sum(len(v) for v in CLASSES.values())
    done = 0
    for category, names in CLASSES.items():
        for name in names:
            done += 1
            print(f"[{done}/{total}] {category}/{name} ...", end=" ", flush=True)
            content = fetch(name)
            # Store with category prefix for easy browsing
            key = f"{category}/{name}"
            index[key] = content
            lines = content.count('\n')
            print(f"{lines} lines")
            time.sleep(0.3)

    out_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDone. {len(index)} entries saved to {out_path}")


if __name__ == "__main__":
    main()
