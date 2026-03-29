from __future__ import annotations

# presets/preset_storage.py
"""Storage layer for preset system.

Handles reading/writing preset files to disk.

Presets are stored in a stable per-user directory (Windows):
  %APPDATA%\\zapret\\presets_v2

This avoids reliance on the installation folder location.
Selected source preset state is managed by the core selection service.
"""
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, TYPE_CHECKING

from log import log
from .preset_model import DEFAULT_PRESET_ICON_COLOR, normalize_preset_icon_color

if TYPE_CHECKING:
    from .preset_model import Preset

def _core_engine_id() -> str:
    return "winws2"


def _core_paths():
    from core.services import get_app_paths

    return get_app_paths().engine_paths(_core_engine_id()).ensure_directories()


def get_presets_dir() -> Path:
    """
    Returns path to the direct_zapret2 source presets directory.
    """
    return _core_paths().presets_dir


def get_user_settings_path() -> Path:
    """
    Returns path to user settings file.

    This stores user-specific settings related to preset UX.

    Returns:
        Path to %APPDATA%/zapret/presets_v2/user_settings.json
    """
    return get_presets_dir() / "user_settings.json"


def _sanitize_filename(name: str) -> str:
    """
    Sanitizes filename by removing dangerous characters.

    Args:
        name: Original filename

    Returns:
        Safe filename
    """
    # Remove path separators and other dangerous chars
    dangerous = ['/', '\\', ':', '*', '?', '"', '<', '>', '|', '\0']
    safe_name = name
    for char in dangerous:
        safe_name = safe_name.replace(char, '_')
    # Limit length
    return safe_name[:100]


def _load_preset_from_path(preset_path: Path) -> Optional[Preset]:
    from .block_semantics import (
        SEMANTIC_STATUS_STRUCTURED_SUPPORTED,
        analyze_block_semantics,
        extract_structured_out_range,
        extract_structured_send,
        extract_structured_syndata,
    )
    from .preset_model import Preset, CategoryConfig, SyndataSettings
    from .txt_preset_parser import (
        PresetData,
        extract_strategy_args_preserving_helpers,
        parse_preset_file,
    )

    if not preset_path.exists():
        log(f"Preset not found: {preset_path}", "WARNING")
        return None

    data: PresetData = parse_preset_file(preset_path)

    try:
        # Convert to Preset model
        file_stem = Path(preset_path).stem
        preset = Preset(
            name=data.name if data.name != "Unnamed" else file_stem,
            base_args=data.base_args,
        )

        # Parse metadata from raw_header
        preset.created, preset.modified, preset.description, preset.icon_color = _parse_metadata_from_header(data.raw_header)
        try:
            setattr(preset, "_template_origin", _parse_template_origin_from_header(data.raw_header))
        except Exception:
            pass

        # Convert category blocks to CategoryConfig
        # Also track full block args (filter-stripped but syndata/send-inclusive) for inference.
        # This is needed so basic-mode strategies that embed syndata/send in their args
        # are correctly identified on reload (block.strategy_args strips those lines).
        _full_args_for_inference: dict = {}  # cat_name -> (tcp_full, udp_full)

        for block in data.categories:
            cat_name = block.category

            # Store raw block text for lossless round-trip save.
            # Multiple CategoryBlocks can share the same raw_args (e.g., a block
            # with multiple --hostlist= lines creates one CategoryBlock per list).
            # We deduplicate by raw_text to avoid writing the same --new block
            # multiple times when saving.
            raw_text = getattr(block, "raw_args", "") or getattr(block, "args", "")
            # Check if this exact raw_text was already stored (shared block)
            already_stored = any(rt == raw_text for _, _, rt in preset._raw_blocks)
            if already_stored:
                # Add this category to the existing entry's category set
                for idx, (cats, proto, rt) in enumerate(preset._raw_blocks):
                    if rt == raw_text:
                        cats.add(cat_name)
                        break
            else:
                preset._raw_blocks.append(({cat_name}, block.protocol, raw_text))

            # Get or create category config
            if cat_name not in preset.categories:
                # Normalize filter_file: ensure it has a relative path prefix
                raw_filter_file = getattr(block, "filter_file", "") or ""
                if raw_filter_file and "/" not in raw_filter_file and "\\" not in raw_filter_file:
                    raw_filter_file = f"lists/{raw_filter_file}"
                preset.categories[cat_name] = CategoryConfig(
                    name=cat_name,
                    filter_mode=block.filter_mode,
                    filter_file=raw_filter_file,
                )

            cat = preset.categories[cat_name]
            raw_strategy_args = extract_strategy_args_preserving_helpers(
                block.args or "",
                category_key=cat_name,
                filter_mode=block.filter_mode,
            )

            # Restore structured advanced settings only when the semantic layer says
            # the block is structurally editable. Raw-only and invalid tokens stay
            # in raw strategy_args and must not be partially hydrated.
            block_text_for_semantics = str(raw_text or getattr(block, "args", "") or "")
            block_semantics = analyze_block_semantics(block_text_for_semantics)
            if block.protocol == "tcp":
                base = SyndataSettings.get_defaults().to_dict()
                base["enabled"] = False
                base["send_enabled"] = False
                base["out_range"] = 0
                base["out_range_mode"] = "n"

                if block_semantics.out_range.status == SEMANTIC_STATUS_STRUCTURED_SUPPORTED:
                    base.update(extract_structured_out_range(block_text_for_semantics))
                if block_semantics.syndata.status == SEMANTIC_STATUS_STRUCTURED_SUPPORTED:
                    base.update(extract_structured_syndata(block_text_for_semantics))
                if block_semantics.send.status == SEMANTIC_STATUS_STRUCTURED_SUPPORTED:
                    base.update(extract_structured_send(block_text_for_semantics))
                cat.syndata_tcp = SyndataSettings.from_dict(base)
            elif block.protocol == "udp":
                base = SyndataSettings.get_defaults_udp().to_dict()
                base["out_range"] = 0
                base["out_range_mode"] = "n"

                if block_semantics.out_range.status == SEMANTIC_STATUS_STRUCTURED_SUPPORTED:
                    base.update(extract_structured_out_range(block_text_for_semantics))
                cat.syndata_udp = SyndataSettings.from_dict(base)

            # Set args based on protocol
            if block.protocol == "tcp":
                cat.tcp_args = block.strategy_args
                cat.tcp_args_raw = raw_strategy_args
                cat.tcp_port = block.port
                cat.tcp_enabled = True
                # TCP filter_mode takes priority over UDP
                cat.filter_mode = block.filter_mode
                # Compute filter-stripped but syndata/send-inclusive args for inference
                try:
                    from .txt_preset_parser import extract_strategy_args_incl_syndata
                    full_tcp = extract_strategy_args_incl_syndata(
                        block.args,
                        category_key=cat_name,
                        filter_mode=block.filter_mode,
                    )
                    prev = _full_args_for_inference.get(cat_name, ("", ""))
                    _full_args_for_inference[cat_name] = (full_tcp, prev[1])
                except Exception:
                    pass
            elif block.protocol == "udp":
                cat.udp_args = block.strategy_args
                cat.udp_args_raw = raw_strategy_args
                cat.udp_port = block.port
                cat.udp_enabled = True
                # UDP sets filter_mode only if TCP didn't set it
                if not cat.filter_mode:
                    cat.filter_mode = block.filter_mode

        # ✅ INFERENCE: Determine strategy_id from args for all categories
        # This is needed because preset files store args but not strategy_id
        from .strategy_inference import infer_strategy_id_from_args

        try:
            from strategy_menu.strategies_registry import get_current_strategy_set
            current_strategy_set = get_current_strategy_set()
        except Exception:
            current_strategy_set = None

        for cat_name, cat in preset.categories.items():
            # Use full args (syndata/send inclusive, filter stripped) for inference when
            # available so that basic-mode strategies embedding syndata/send are found.
            tcp_full, _ = _full_args_for_inference.get(cat_name, ("", ""))

            # Try TCP first (most common)
            if cat.tcp_args and cat.tcp_args.strip():
                inferred_id = infer_strategy_id_from_args(
                    category_key=cat_name,
                    args=tcp_full if tcp_full and tcp_full.strip() else cat.tcp_args,
                    protocol="tcp",
                    strategy_set=current_strategy_set,
                )
                if inferred_id != "none":
                    cat.strategy_id = inferred_id
                    continue

            # Try UDP if TCP didn't work or is empty
            if cat.udp_args and cat.udp_args.strip():
                inferred_id = infer_strategy_id_from_args(
                    category_key=cat_name,
                    args=cat.udp_args,
                    protocol="udp",
                    strategy_set=current_strategy_set,
                )
                if inferred_id != "none":
                    cat.strategy_id = inferred_id

        log(f"Loaded preset '{file_stem}': {len(preset.categories)} categories", "DEBUG")
        return preset

    except Exception as e:
        log(f"Error loading preset '{file_stem}': {e}", "ERROR")
        return None
def _parse_metadata_from_header(header: str) -> Tuple[str, str, str, str]:
    """
    Parses created/modified/description/icon_color metadata from header comments.

    Args:
        header: Raw header string

    Returns:
        Tuple of (created, modified, description, icon_color)
    """
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
            icon_color = normalize_preset_icon_color(icon_color_match.group(1).strip())

    return created, modified, description, icon_color


def _parse_builtin_version_from_header(header: str) -> Optional[str]:
    """Parses `# BuiltinVersion: X.Y` from header comments."""
    for line in (header or "").split('\n'):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            break
        match = re.match(r'#\s*BuiltinVersion:\s*(.+)', line, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            return value or None
    return None


def _parse_template_origin_from_header(header: str) -> Optional[str]:
    for line in (header or "").split('\n'):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            break
        match = re.match(r'#\s*TemplateOrigin:\s*(.+)', line, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            return value or None
    return None


def _read_existing_builtin_version(path: Path) -> Optional[str]:
    """Reads BuiltinVersion from existing preset file (if present)."""
    try:
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8", errors="replace")
        return _parse_builtin_version_from_header(content)
    except Exception:
        return None


def _read_existing_template_origin(path: Path) -> Optional[str]:
    try:
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8", errors="replace")
        return _parse_template_origin_from_header(content)
    except Exception:
        return None


def save_preset(preset: Preset) -> bool:
    """
    Saves preset to file.

    Uses atomic write (temp file + rename) for safety.

    Args:
        preset: Preset object to save

    Returns:
        True if successful
    """
    from .txt_preset_parser import PresetData, CategoryBlock, generate_preset_file

    source_file_name = str(getattr(preset, "_source_file_name", "") or "").strip()
    candidate = Path(source_file_name).name if source_file_name else ""
    if not candidate:
        safe_name = _sanitize_filename(str(getattr(preset, "name", "") or "Preset"))
        candidate = f"{safe_name}.txt"
    if not candidate.lower().endswith(".txt"):
        candidate = f"{candidate}.txt"
    preset_path = get_presets_dir() / candidate

    try:
        # Convert Preset to PresetData
        data = PresetData(
            name=preset.name,
            base_args=preset.base_args,
        )

        icon_color = normalize_preset_icon_color(getattr(preset, "icon_color", DEFAULT_PRESET_ICON_COLOR))
        preset.icon_color = icon_color

        # Build raw header. Preserve BuiltinVersion if this file already has it
        # so versioned auto-updates can compare against local state correctly.
        builtin_version = _read_existing_builtin_version(preset_path)
        template_origin = str(getattr(preset, "_template_origin", "") or "").strip() or _read_existing_template_origin(preset_path)
        header_lines = [f"# Preset: {preset.name}"]
        if template_origin:
            header_lines.append(f"# TemplateOrigin: {template_origin}")
        if builtin_version:
            header_lines.append(f"# BuiltinVersion: {builtin_version}")
        header_lines.extend(
            [
                f"# Created: {preset.created}",
                f"# Modified: {datetime.now().isoformat()}",
                f"# IconColor: {icon_color}",
                f"# Description: {preset.description}",
            ]
        )
        data.raw_header = "\n".join(header_lines)

        # Convert categories to CategoryBlocks
        for cat_name, cat in preset.categories.items():
            # TCP block
            if cat.tcp_enabled and cat.has_tcp():
                from .base_filter import build_category_base_filter_lines
                base_filter_lines = build_category_base_filter_lines(cat_name, cat.filter_mode)

                args_lines = list(base_filter_lines)
                if not args_lines:
                    filter_file_relative = cat.get_filter_file()
                    args_lines = [f"--filter-tcp={cat.tcp_port}"]
                    if cat.filter_mode in ("hostlist", "ipset"):
                        args_lines.append(f"--{cat.filter_mode}={filter_file_relative}")
                # Use get_full_tcp_args() to include syndata/send/out-range
                full_tcp_args = cat.get_full_tcp_args()
                for line in full_tcp_args.strip().split('\n'):
                    if line.strip():
                        args_lines.append(line.strip())

                block = CategoryBlock(
                    category=cat_name,
                    protocol="tcp",
                    filter_mode=cat.filter_mode if cat.filter_mode in ("hostlist", "ipset") else "",
                    filter_file="",
                    port=cat.tcp_port,
                    args='\n'.join(args_lines),
                    strategy_args=cat.tcp_args,
                )
                data.categories.append(block)

            # UDP block
            if cat.udp_enabled and cat.has_udp():
                from .base_filter import build_category_base_filter_lines
                base_filter_lines = build_category_base_filter_lines(cat_name, cat.filter_mode)

                args_lines = list(base_filter_lines)
                if not args_lines:
                    filter_file_relative = cat.get_filter_file()
                    args_lines = [f"--filter-udp={cat.udp_port}"]
                    if cat.filter_mode in ("hostlist", "ipset"):
                        args_lines.append(f"--{cat.filter_mode}={filter_file_relative}")
                # Use get_full_udp_args() to include out-range (UDP has no syndata/send)
                full_udp_args = cat.get_full_udp_args()
                for line in full_udp_args.strip().split('\n'):
                    if line.strip():
                        args_lines.append(line.strip())

                block = CategoryBlock(
                    category=cat_name,
                    protocol="udp",
                    filter_mode=cat.filter_mode if cat.filter_mode in ("hostlist", "ipset") else "",
                    filter_file="",
                    port=cat.udp_port,
                    args='\n'.join(args_lines),
                    strategy_args=cat.udp_args,
                )
                data.categories.append(block)

        # Deduplicate categories before writing
        data.deduplicate_categories()

        # Write file
        success = generate_preset_file(data, preset_path, atomic=True)

        if success:
            log(f"Saved preset '{preset.name}' to {preset_path}", "DEBUG")
        else:
            log(f"Failed to save preset '{preset.name}'", "ERROR")

        return success

    except PermissionError as e:
        log(f"Cannot write preset file (locked by winws2?): {e}", "ERROR")
        raise
    except Exception as e:
        log(f"Error saving preset '{preset.name}': {e}", "ERROR")
        return False


# ============================================================================
# DELETE/RENAME OPERATIONS
# ============================================================================
def import_preset(src_path: Path, name: Optional[str] = None) -> bool:
    """
    Imports preset from external file.

    Args:
        src_path: Source file path
        name: Optional name for imported preset (uses filename if None)

    Returns:
        True if imported successfully
    """
    src_path = Path(src_path)

    if not src_path.exists():
        log(f"Cannot import: file '{src_path}' not found", "WARNING")
        return False

    # Determine name
    if name is None:
        name = src_path.stem

    try:
        candidate = Path(str(name or "").strip()).name or "Preset.txt"
        if not candidate.lower().endswith(".txt"):
            candidate = f"{candidate}.txt"
        dest_path = get_presets_dir() / candidate
        shutil.copy2(src_path, dest_path)
        log(f"Imported preset '{name}' from {src_path}", "DEBUG")
        return True
    except Exception as e:
        log(f"Error importing preset: {e}", "ERROR")
        return False
