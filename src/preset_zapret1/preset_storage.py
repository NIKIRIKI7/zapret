from __future__ import annotations

# preset_zapret1/preset_storage.py
"""Storage layer for Zapret 1 preset system.

Presets stored in: %APPDATA%/zapret/presets_v1/
Selected preset state is managed by the core selection service.
The selected source preset is also the direct launch file.
"""
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, TYPE_CHECKING

from log import log
from .preset_model import DEFAULT_PRESET_ICON_COLOR, normalize_preset_icon_color_v1

if TYPE_CHECKING:
    from .preset_model import PresetV1

def _core_engine_id() -> str:
    return "winws1"


def _core_paths():
    from core.services import get_app_paths

    return get_app_paths().engine_paths(_core_engine_id()).ensure_directories()


def get_presets_dir_v1() -> Path:
    return _core_paths().presets_dir


def _sanitize_filename(name: str) -> str:
    dangerous = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\0']
    safe_name = name
    for char in dangerous:
        safe_name = safe_name.replace(char, '_')
    return safe_name[:100]


def _parse_metadata_from_header_v1(header: str) -> Tuple[str, str, str, str]:
    created = datetime.now().isoformat()
    modified = datetime.now().isoformat()
    description = ""
    icon_color = DEFAULT_PRESET_ICON_COLOR

    for line in (header or "").split('\n'):
        created_match = re.match(r'#\s*Created:\s*(.+)', line, re.IGNORECASE)
        if created_match:
            created = created_match.group(1).strip()
        modified_match = re.match(r'#\s*Modified:\s*(.+)', line, re.IGNORECASE)
        if modified_match:
            modified = modified_match.group(1).strip()
        desc_match = re.match(r'#\s*Description:\s*(.*)', line, re.IGNORECASE)
        if desc_match:
            description = desc_match.group(1).strip()
        icon_color_match = re.match(r'#\s*IconColor:\s*(.+)', line, re.IGNORECASE)
        if icon_color_match:
            icon_color = normalize_preset_icon_color_v1(icon_color_match.group(1).strip())

    return created, modified, description, icon_color


def _parse_template_origin_from_header_v1(header: str) -> Optional[str]:
    for line in (header or "").split('\n'):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            break
        match = re.match(r'#\s*TemplateOrigin:\s*(.+)', line, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            return value or None
    return None


def _load_preset_from_path_v1(preset_path: Path) -> Optional["PresetV1"]:
    from .preset_model import PresetV1, CategoryConfigV1
    from preset_zapret2.txt_preset_parser import parse_preset_file

    if not preset_path.exists():
        log(f"V1 preset not found: {preset_path}", "WARNING")
        return None

    try:
        data = parse_preset_file(preset_path)
        file_stem = Path(preset_path).stem
        preset = PresetV1(
            name=data.name if data.name != "Unnamed" else file_stem,
            base_args=data.base_args,
        )
        preset.created, preset.modified, preset.description, preset.icon_color = \
            _parse_metadata_from_header_v1(data.raw_header)
        try:
            setattr(preset, "_template_origin", _parse_template_origin_from_header_v1(data.raw_header))
        except Exception:
            pass

        for block in data.categories:
            cat_name = block.category
            if cat_name not in preset.categories:
                preset.categories[cat_name] = CategoryConfigV1(
                    name=cat_name,
                    filter_mode=block.filter_mode,
                )
            cat = preset.categories[cat_name]
            if block.protocol == "tcp":
                cat.tcp_args = block.strategy_args
                cat.tcp_port = block.port
                cat.tcp_enabled = True
                cat.filter_mode = block.filter_mode
            elif block.protocol == "udp":
                cat.udp_args = block.strategy_args
                cat.udp_port = block.port
                cat.udp_enabled = True
                if not cat.filter_mode:
                    cat.filter_mode = block.filter_mode

        # Infer strategy_id from args
        try:
            from .strategy_inference import infer_strategy_id_from_args
            for cat_name, cat in preset.categories.items():
                if cat.tcp_args and cat.tcp_args.strip():
                    inferred_id = infer_strategy_id_from_args(
                        category_key=cat_name,
                        args=cat.tcp_args,
                        protocol="tcp",
                    )
                    if inferred_id != "none":
                        cat.strategy_id = inferred_id
                        continue
                if cat.udp_args and cat.udp_args.strip():
                    inferred_id = infer_strategy_id_from_args(
                        category_key=cat_name,
                        args=cat.udp_args,
                        protocol="udp",
                    )
                    if inferred_id != "none":
                        cat.strategy_id = inferred_id
        except Exception:
            pass

        log(f"Loaded V1 preset '{file_stem}': {len(preset.categories)} categories", "DEBUG")
        return preset

    except Exception as e:
        log(f"Error loading V1 preset '{file_stem}': {e}", "ERROR")
        return None
def save_preset_v1(preset: "PresetV1") -> bool:
    import os
    from preset_zapret2.txt_preset_parser import PresetData, CategoryBlock, generate_preset_file
    from preset_zapret2.base_filter import build_category_base_filter_lines

    source_file_name = str(getattr(preset, "_source_file_name", "") or "").strip()
    candidate = Path(source_file_name).name if source_file_name else ""
    if not candidate:
        safe_name = _sanitize_filename(str(getattr(preset, "name", "") or "Preset"))
        candidate = f"{safe_name}.txt"
    if not candidate.lower().endswith(".txt"):
        candidate = f"{candidate}.txt"
    preset_path = get_presets_dir_v1() / candidate

    try:
        data = PresetData(name=preset.name, base_args=preset.base_args)

        icon_color = normalize_preset_icon_color_v1(getattr(preset, "icon_color", DEFAULT_PRESET_ICON_COLOR))
        preset.icon_color = icon_color

        # Preserve BuiltinVersion if the preset file already carries one
        # (so version-based auto-updates can still compare on next startup).
        existing_builtin_version: Optional[str] = None
        existing_template_origin: Optional[str] = None
        if preset_path.exists():
            try:
                from preset_zapret2.preset_defaults import _extract_builtin_version
                existing_builtin_version = _extract_builtin_version(
                    preset_path.read_text(encoding="utf-8", errors="replace")
                )
                existing_template_origin = _parse_template_origin_from_header_v1(
                    preset_path.read_text(encoding="utf-8", errors="replace")
                )
            except Exception:
                pass

        header_lines = [f"# Preset: {preset.name}"]
        template_origin = str(getattr(preset, "_template_origin", "") or "").strip() or existing_template_origin
        if template_origin:
            header_lines.append(f"# TemplateOrigin: {template_origin}")
        if existing_builtin_version:
            header_lines.append(f"# BuiltinVersion: {existing_builtin_version}")
        header_lines.extend([
            f"# Created: {preset.created}",
            f"# Modified: {datetime.now().isoformat()}",
            f"# IconColor: {icon_color}",
            f"# Description: {preset.description}",
        ])
        data.raw_header = "\n".join(header_lines)

        for cat_name, cat in preset.categories.items():
            if cat.tcp_enabled and cat.has_tcp():
                args_lines = build_category_base_filter_lines(cat_name, cat.filter_mode)
                if not args_lines:
                    filter_file_relative = cat.get_hostlist_file() if cat.filter_mode == "hostlist" else cat.get_ipset_file()
                    args_lines = [f"--filter-tcp={cat.tcp_port}"]
                    if cat.filter_mode in ("hostlist", "ipset"):
                        args_lines.append(f"--{cat.filter_mode}={filter_file_relative}")
                custom_port = str(cat.tcp_port or "").strip()
                if custom_port:
                    for i, line in enumerate(args_lines):
                        low = line.lower()
                        if low.startswith("--filter-tcp="):
                            args_lines[i] = f"--filter-tcp={custom_port}"
                        elif low.startswith("--filter-l7="):
                            args_lines[i] = f"--filter-l7={custom_port}"
                for line in cat.tcp_args.strip().split('\n'):
                    if line.strip():
                        args_lines.append(line.strip())
                block = CategoryBlock(
                    category=cat_name,
                    protocol="tcp",
                    filter_mode=cat.filter_mode,
                    filter_file="",
                    port=cat.tcp_port,
                    args='\n'.join(args_lines),
                    strategy_args=cat.tcp_args,
                )
                data.categories.append(block)

            if cat.udp_enabled and cat.has_udp():
                args_lines = build_category_base_filter_lines(cat_name, cat.filter_mode)
                if not args_lines:
                    filter_file_relative = cat.get_ipset_file() if cat.filter_mode == "ipset" else cat.get_hostlist_file()
                    args_lines = [f"--filter-udp={cat.udp_port}"]
                    if cat.filter_mode in ("hostlist", "ipset"):
                        args_lines.append(f"--{cat.filter_mode}={filter_file_relative}")
                custom_port = str(cat.udp_port or "").strip()
                if custom_port:
                    for i, line in enumerate(args_lines):
                        low = line.lower()
                        if low.startswith("--filter-udp="):
                            args_lines[i] = f"--filter-udp={custom_port}"
                        elif low.startswith("--filter-l7="):
                            args_lines[i] = f"--filter-l7={custom_port}"
                for line in cat.udp_args.strip().split('\n'):
                    if line.strip():
                        args_lines.append(line.strip())
                block = CategoryBlock(
                    category=cat_name,
                    protocol="udp",
                    filter_mode=cat.filter_mode,
                    filter_file="",
                    port=cat.udp_port,
                    args='\n'.join(args_lines),
                    strategy_args=cat.udp_args,
                )
                data.categories.append(block)

        data.deduplicate_categories()
        success = generate_preset_file(data, preset_path, atomic=True)
        if success:
            log(f"Saved V1 preset '{preset.name}' to {preset_path}", "DEBUG")
        else:
            log(f"Failed to save V1 preset '{preset.name}'", "ERROR")
        return success

    except PermissionError as e:
        log(f"Cannot write V1 preset file: {e}", "ERROR")
        raise
    except Exception as e:
        log(f"Error saving V1 preset '{preset.name}': {e}", "ERROR")
        return False
