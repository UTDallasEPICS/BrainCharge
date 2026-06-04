# runtime_platform.py
#
# Detect whether BrainCharge is running on Jetson hardware or a PC,
# and resolve feature flags (Arduino, CV, etc.) for each mode.
#
# Override detection:
#   config.json  →  "runtime_mode": "auto" | "jetson" | "pc"
#   environment  →  BRAINCHARGE_RUNTIME=jetson|pc|auto

from __future__ import annotations

import os
import platform
from typing import Any, Literal

RuntimeMode = Literal["jetson", "pc"]
RuntimeSetting = Literal["auto", "jetson", "pc"]


def _read_device_tree_model() -> str:
    for path in (
        "/proc/device-tree/model",
        "/sys/firmware/devicetree/base/model",
    ):
        try:
            with open(path, "rb") as handle:
                return handle.read().decode("utf-8", errors="ignore").strip("\x00")
        except OSError:
            continue
    return ""


def is_jetson_device() -> bool:
    """Return True when running on NVIDIA Jetson (Orin Nano, etc.)."""
    if os.path.exists("/etc/nv_tegra_release"):
        return True

    model = _read_device_tree_model().lower()
    if "jetson" in model or "tegra" in model:
        return True

    if os.environ.get("JETSON_MODEL_NAME"):
        return True

    return False


def _normalize_runtime_setting(value: str) -> RuntimeSetting:
    normalized = value.strip().lower()
    if normalized in ("jetson", "robot", "full"):
        return "jetson"
    if normalized in ("pc", "desktop", "test", "testing"):
        return "pc"
    return "auto"


def resolve_runtime_mode(config: dict | None = None) -> RuntimeMode:
    """Resolve active runtime: jetson (full robot) or pc (voice testing)."""
    config = config or {}
    setting = _normalize_runtime_setting(
        os.environ.get("BRAINCHARGE_RUNTIME")
        or config.get("runtime_mode", "auto")
    )
    if setting == "jetson":
        return "jetson"
    if setting == "pc":
        return "pc"
    return "jetson" if is_jetson_device() else "pc"


def resolve_feature(
    config: dict,
    key: str,
    jetson_default: bool,
    pc_default: bool,
) -> bool:
    """Use an explicit config value when set; otherwise pick the runtime default."""
    if key in config:
        return bool(config[key])
    mode = resolve_runtime_mode(config)
    return jetson_default if mode == "jetson" else pc_default


def get_runtime_profile(config: dict | None = None) -> dict[str, Any]:
    config = config or {}
    setting = _normalize_runtime_setting(
        os.environ.get("BRAINCHARGE_RUNTIME")
        or config.get("runtime_mode", "auto")
    )
    mode = resolve_runtime_mode(config)
    os_name = platform.system()
    machine = platform.machine()
    jetson_hw = is_jetson_device()

    return {
        "runtime_mode_setting": setting,
        "runtime_mode": mode,
        "jetson_hardware_detected": jetson_hw,
        "is_jetson": mode == "jetson",
        "is_pc": mode == "pc",
        "os_name": os_name,
        "machine": machine,
        "connect_arduino": resolve_feature(config, "connect_arduino", True, False),
        "enable_cv": resolve_feature(config, "enable_cv", True, False),
    }


def describe_runtime(profile: dict[str, Any]) -> str:
    setting = profile["runtime_mode_setting"]
    mode = profile["runtime_mode"]
    hw = profile["jetson_hardware_detected"]

    if setting == "auto":
        if hw:
            return f"Jetson (auto-detected hardware, {mode} profile)"
        return f"PC (auto-detected, {mode} profile)"

    label = "Jetson robot" if mode == "jetson" else "PC testing"
    return f"{label} (runtime_mode={setting!r})"
