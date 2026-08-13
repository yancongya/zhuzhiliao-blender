"""Live one-shot sound trigger for the zhuzhiliao Blender case.

Run this file once after opening the blend.  It watches the rod transform and
plays one sound when a new movement gesture starts.  Continuous movement does
not retrigger until the rod has settled for ``sound_settle_seconds``.
"""

from __future__ import annotations

import math
import struct
import time
import wave
from pathlib import Path

import aud
import bpy
from bpy.app.handlers import persistent


ROD_NAME = "甩杆"
CONTROL_NAME = "声音触发控制器"
HANDLER_KEY = "zhuzhiliao_sound_trigger"
DEFAULT_SOUND = Path(__file__).with_name("zhuzhiliao-move.wav")

_device = None
_sound = None
_sound_path = None
_last_matrix = None
_last_motion_at = 0.0
_moving = False


def _ensure_default_sound(path: Path) -> None:
    """Create a short neutral chirp so the module works before sound replacement."""
    if path.exists():
        return
    sample_rate = 44_100
    duration = 0.16
    frames = []
    for index in range(int(sample_rate * duration)):
        t = index / sample_rate
        envelope = min(1.0, t / 0.012) * max(0.0, 1.0 - t / duration) ** 2
        frequency = 980.0 + 520.0 * (t / duration)
        sample = 0.24 * envelope * math.sin(2.0 * math.pi * frequency * t)
        frames.append(struct.pack("<h", int(max(-1.0, min(1.0, sample)) * 32767)))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"".join(frames))


def _control():
    obj = bpy.data.objects.get(CONTROL_NAME)
    if obj is None:
        obj = bpy.data.objects.new(CONTROL_NAME, None)
        bpy.context.scene.collection.objects.link(obj)
        obj.empty_display_type = "PLAIN_AXES"
        obj.hide_viewport = True
        obj.hide_render = True
    defaults = {
        "启用声音": True,
        "音量": 0.65,
        "移动阈值": 0.0015,
        "静止复位秒数": 0.28,
        "音效路径": str(DEFAULT_SOUND),
        "触发次数": 0,
        "说明": "摇杆由静止进入运动时播放一次；持续运动不重复，静止后再次移动才重触发。",
    }
    for key, value in defaults.items():
        if key not in obj:
            obj[key] = value
    return obj


def _matrix_distance(a, b) -> float:
    location_delta = (a.translation - b.translation).length
    rotation_delta = a.to_quaternion().rotation_difference(b.to_quaternion()).angle
    return location_delta + rotation_delta


def _load_sound(path: str):
    global _device, _sound, _sound_path
    if _device is None:
        _device = aud.Device()
    if _sound is None or _sound_path != path:
        _sound = aud.Sound(path)
        _sound_path = path
    return _sound


def _play(control) -> None:
    path = bpy.path.abspath(str(control.get("音效路径", DEFAULT_SOUND)))
    if not Path(path).exists():
        return
    handle = _device.play(_load_sound(path)) if _device else None
    if handle is None:
        handle = aud.Device().play(_load_sound(path))
    handle.volume = max(0.0, min(1.0, float(control.get("音量", 0.65))))


@persistent
def _on_depsgraph_update(_scene, depsgraph):
    global _last_matrix, _last_motion_at, _moving
    rod = bpy.data.objects.get(ROD_NAME)
    control = _control()
    if rod is None:
        return
    matrix = rod.matrix_world.copy()
    if _last_matrix is None:
        _last_matrix = matrix
        return
    changed = any(update.id == rod for update in depsgraph.updates)
    distance = _matrix_distance(matrix, _last_matrix)
    _last_matrix = matrix
    if not changed or distance < float(control.get("移动阈值", 0.0015)):
        return
    now = time.monotonic()
    _last_motion_at = now
    if bool(control.get("启用声音", True)) and not _moving:
        _play(control)
        control["触发次数"] = int(control.get("触发次数", 0)) + 1
        control["最后触发时间"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _moving = True


def _settle_timer():
    global _last_matrix, _last_motion_at, _moving
    control = bpy.data.objects.get(CONTROL_NAME)
    rod = bpy.data.objects.get(ROD_NAME)
    if control and rod:
        matrix = rod.matrix_world.copy()
        if _last_matrix is None:
            _last_matrix = matrix
        else:
            distance = _matrix_distance(matrix, _last_matrix)
            _last_matrix = matrix
            if distance >= float(control.get("移动阈值", 0.0015)):
                _last_motion_at = time.monotonic()
                if bool(control.get("启用声音", True)) and not _moving:
                    _play(control)
                    control["触发次数"] = int(control.get("触发次数", 0)) + 1
                    control["最后触发时间"] = time.strftime("%Y-%m-%d %H:%M:%S")
                _moving = True
    settle = float(control.get("静止复位秒数", 0.28)) if control else 0.28
    if _moving and time.monotonic() - _last_motion_at >= settle:
        _moving = False
    return 0.05


def unregister():
    handlers = bpy.app.handlers.depsgraph_update_post
    handlers[:] = [handler for handler in handlers if getattr(handler, "_zhuzhiliao_key", None) != HANDLER_KEY]


def register():
    global _device, _sound, _sound_path, _last_matrix, _moving
    unregister()
    control = _control()
    sound_path = Path(bpy.path.abspath(str(control["音效路径"])))
    if sound_path == DEFAULT_SOUND:
        _ensure_default_sound(sound_path)
    _device = aud.Device()
    _sound = None
    _sound_path = None
    rod = bpy.data.objects.get(ROD_NAME)
    _last_matrix = rod.matrix_world.copy() if rod else None
    _moving = False
    # Polling is intentional: transform updates can be consumed by Blender's
    # dependency graph before a post-update handler sees a stable delta.
    if not bpy.app.timers.is_registered(_settle_timer):
        bpy.app.timers.register(_settle_timer, first_interval=0.05, persistent=True)


register()
