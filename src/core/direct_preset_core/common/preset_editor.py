from __future__ import annotations

from dataclasses import replace

from .source_preset_models import FilterProfile, ProfileSegment, SourcePreset


_POSITIVE_SELECTOR_FAMILIES = {"hostlist", "hostlist-domains", "ipset", "ipset-ip"}


def _profile_target_keys(profile: FilterProfile) -> list[str]:
    return list(profile.canonical_target_keys or ())


def _clone_profile(profile: FilterProfile, segments: list[ProfileSegment], canonical_target_keys: list[str]) -> FilterProfile:
    match_lines = [segment.text for segment in segments if segment.kind == "match"]
    action_lines = [segment.text for segment in segments if segment.kind == "action"]
    protocol_kind = profile.protocol_kind
    return FilterProfile(
        match_lines=match_lines,
        action_lines=action_lines,
        segments=segments,
        protocol_kind=protocol_kind,
        canonical_target_keys=tuple(canonical_target_keys),
    )


def split_profile_for_target(source: SourcePreset, profile_index: int, target_key: str) -> int:
    profile = source.profiles[profile_index]
    target_keys = _profile_target_keys(profile)
    if target_key not in target_keys or len(target_keys) <= 1:
        return profile_index

    shared_segments: list[ProfileSegment] = []
    residual_only_segments: list[ProfileSegment] = []
    target_segments: list[ProfileSegment] = []
    residual_segments: list[ProfileSegment] = []
    pending_neutral: list[ProfileSegment] = []

    def _flush_pending_to(bucket: list[ProfileSegment]) -> None:
        if pending_neutral:
            bucket.extend(pending_neutral)
            pending_neutral.clear()

    for segment in profile.segments:
        if segment.kind in {"comment", "blank"}:
            pending_neutral.append(segment)
            continue

        if segment.kind == "directive":
            _flush_pending_to(residual_only_segments)
            residual_only_segments.append(segment)
            continue

        if (
            segment.kind == "match"
            and segment.selector_is_positive
            and segment.selector_family in _POSITIVE_SELECTOR_FAMILIES
        ):
            if len(segment.target_keys) == 1 and target_key in segment.target_keys:
                _flush_pending_to(target_segments)
                target_segments.append(segment)
            else:
                _flush_pending_to(residual_segments)
                residual_segments.append(segment)
            continue

        if segment.kind == "action":
            continue

        _flush_pending_to(shared_segments)
        shared_segments.append(segment)

    _flush_pending_to(residual_only_segments)

    action_segments = [segment for segment in profile.segments if segment.kind == "action"]
    target_profile = _clone_profile(
        profile,
        [*shared_segments, *target_segments, *action_segments],
        [target_key],
    )
    residual_keys = [key for key in target_keys if key != target_key]
    residual_profile = _clone_profile(
        profile,
        [*residual_only_segments, *shared_segments, *residual_segments, *action_segments],
        residual_keys,
    )

    source.profiles[profile_index] = residual_profile
    source.profiles.insert(profile_index, target_profile)
    return profile_index


def replace_profile_action_lines(source: SourcePreset, profile_index: int, action_lines: list[str]) -> None:
    profile = source.profiles[profile_index]
    replacement = [ProfileSegment(kind="action", text=line) for line in action_lines if str(line).strip()]
    new_segments: list[ProfileSegment] = []
    inserted = False

    for segment in profile.segments:
        if segment.kind == "action":
            if not inserted:
                new_segments.extend(replacement)
                inserted = True
            continue
        new_segments.append(segment)

    if not inserted:
        new_segments.extend(replacement)

    source.profiles[profile_index] = replace(
        profile,
        action_lines=[line for line in action_lines if str(line).strip()],
        segments=new_segments,
    )


def replace_profile_selector_line(source: SourcePreset, profile_index: int, target_key: str, new_line: str, selector_family: str) -> None:
    profile = source.profiles[profile_index]
    segments: list[ProfileSegment] = []
    replaced = False
    for segment in profile.segments:
        if (
            segment.kind == "match"
            and segment.selector_is_positive
            and target_key in segment.target_keys
        ):
            if not replaced:
                segments.append(
                    ProfileSegment(
                        kind="match",
                        text=new_line,
                        target_keys=(target_key,),
                        selector_value=segment.selector_value,
                        selector_family=selector_family,
                        selector_is_positive=True,
                    )
                )
                replaced = True
            continue
        segments.append(segment)

    if not replaced:
        segments.append(
            ProfileSegment(
                kind="match",
                text=new_line,
                target_keys=(target_key,),
                selector_value="",
                selector_family=selector_family,
                selector_is_positive=True,
            )
        )

    source.profiles[profile_index] = _clone_profile(profile, segments, list(profile.canonical_target_keys))
