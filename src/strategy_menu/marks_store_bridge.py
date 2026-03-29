from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable, Optional, Set, Tuple

from config import get_zapret_userdata_dir
from log import log


MarkKey = Tuple[str, str]  # (target_key, strategy_id)


def _get_marks_dir() -> Path:
    base = ""
    try:
        base = (get_zapret_userdata_dir() or "").strip()
    except Exception:
        base = ""

    if not base:
        appdata = (os.environ.get("APPDATA") or "").strip()
        if appdata:
            base = os.path.join(appdata, "zapret")

    if not base:
        raise RuntimeError("APPDATA is required for strategy marks storage")

    # Keep the existing direct_zapret2 marks location so current file-based data
    # continues to work after the strategy_menu split.
    return Path(base) / "direct_zapret2"


def _parse_marks_lines(lines: Iterable[str]) -> Set[MarkKey]:
    out: Set[MarkKey] = set()
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "\t" not in line:
            continue
        cat, sid = line.split("\t", 1)
        cat = cat.strip()
        sid = sid.strip()
        if cat and sid:
            out.add((cat, sid))
    return out


def _format_marks_lines(keys: Set[MarkKey]) -> str:
    parts = [f"{cat}\t{sid}" for cat, sid in sorted(keys, key=lambda x: (x[0].lower(), x[1].lower()))]
    return ("\n".join(parts) + "\n") if parts else ""


@dataclass
class DirectZapret2MarksStore:
    work_path: Path
    notwork_path: Path
    _work: Optional[Set[MarkKey]] = None
    _notwork: Optional[Set[MarkKey]] = None

    @classmethod
    def default(cls) -> "DirectZapret2MarksStore":
        base = _get_marks_dir()
        return cls(work_path=base / "work.txt", notwork_path=base / "notwork.txt")

    def reset_cache(self) -> None:
        self._work = None
        self._notwork = None

    def _ensure_loaded(self) -> None:
        if self._work is not None and self._notwork is not None:
            return
        self._work = set()
        self._notwork = set()

        if self.work_path.exists():
            self._work = _parse_marks_lines(self.work_path.read_text(encoding="utf-8", errors="ignore").splitlines())
        if self.notwork_path.exists():
            self._notwork = _parse_marks_lines(self.notwork_path.read_text(encoding="utf-8", errors="ignore").splitlines())

        self._notwork.difference_update(self._work)

    def get_mark(self, target_key: str, strategy_id: str) -> Optional[bool]:
        self._ensure_loaded()
        key = (target_key, strategy_id)
        if key in self._work:
            return True
        if key in self._notwork:
            return False
        return None

    def set_mark(self, target_key: str, strategy_id: str, is_working: Optional[bool]) -> None:
        self._ensure_loaded()
        key = (target_key, strategy_id)
        self._work.discard(key)
        self._notwork.discard(key)
        if is_working is True:
            self._work.add(key)
        elif is_working is False:
            self._notwork.add(key)
        self._save()

    def export_ratings(self) -> dict[str, dict[str, str]]:
        self._ensure_loaded()
        ratings: dict[str, dict[str, str]] = {}
        for cat, sid in self._work:
            ratings.setdefault(cat, {})[sid] = "working"
        for cat, sid in self._notwork:
            ratings.setdefault(cat, {})[sid] = "broken"
        return ratings

    def replace_from_ratings(self, ratings: dict) -> None:
        self._work = set()
        self._notwork = set()
        for cat, per_cat in (ratings or {}).items():
            if not isinstance(cat, str) or not isinstance(per_cat, dict):
                continue
            for sid, rating in per_cat.items():
                if not isinstance(sid, str):
                    continue
                key = (cat, sid)
                if rating == "working":
                    self._work.add(key)
                elif rating == "broken":
                    self._notwork.add(key)
        self._notwork.difference_update(self._work)
        self._save()

    def clear_all(self) -> None:
        self._work = set()
        self._notwork = set()
        self._save()

    def _save(self) -> None:
        base = self.work_path.parent
        base.mkdir(parents=True, exist_ok=True)
        self.work_path.write_text(_format_marks_lines(self._work or set()), encoding="utf-8")
        self.notwork_path.write_text(_format_marks_lines(self._notwork or set()), encoding="utf-8")


@dataclass
class DirectZapret2FavoritesStore:
    favorites_path: Path
    _favorites: Optional[Set[MarkKey]] = None

    @classmethod
    def default(cls) -> "DirectZapret2FavoritesStore":
        base = _get_marks_dir()
        return cls(favorites_path=base / "favorites.txt")

    def reset_cache(self) -> None:
        self._favorites = None

    def _ensure_loaded(self) -> None:
        if self._favorites is not None:
            return
        self._favorites = set()
        if self.favorites_path.exists():
            self._favorites = _parse_marks_lines(self.favorites_path.read_text(encoding="utf-8", errors="ignore").splitlines())

    def get_favorites(self, target_key: str) -> Set[str]:
        self._ensure_loaded()
        cat = (target_key or "").strip()
        if not cat:
            return set()
        return {sid for c, sid in (self._favorites or set()) if c == cat}

    def is_favorite(self, target_key: str, strategy_id: str) -> bool:
        self._ensure_loaded()
        return (target_key, strategy_id) in (self._favorites or set())

    def set_favorite(self, target_key: str, strategy_id: str, favorite: bool) -> None:
        self._ensure_loaded()
        key = ((target_key or "").strip(), (strategy_id or "").strip())
        if not key[0] or not key[1]:
            return
        if favorite:
            self._favorites.add(key)
        else:
            self._favorites.discard(key)
        self._save()

    def export_favorites(self) -> dict[str, list[str]]:
        self._ensure_loaded()
        out: dict[str, list[str]] = {}
        for cat, sid in sorted(self._favorites or set(), key=lambda x: (x[0].lower(), x[1].lower())):
            out.setdefault(cat, []).append(sid)
        return out

    def replace_from_favorites(self, favorites: dict) -> None:
        self._favorites = set()
        for cat, sids in (favorites or {}).items():
            if not isinstance(cat, str) or not isinstance(sids, (list, tuple, set)):
                continue
            for sid in sids:
                if isinstance(sid, str) and sid.strip():
                    self._favorites.add((cat, sid.strip()))
        self._save()

    def clear_category(self, target_key: str) -> None:
        self._ensure_loaded()
        cat = str(target_key or "").strip()
        if not cat:
            return
        self._favorites = {(stored_cat, sid) for stored_cat, sid in (self._favorites or set()) if stored_cat != cat}
        self._save()

    def clear_all(self) -> None:
        self._favorites = set()
        self._save()

    def all_strategy_ids(self) -> list[str]:
        self._ensure_loaded()
        return sorted({sid for _cat, sid in (self._favorites or set())}, key=str.lower)

    def _save(self) -> None:
        base = self.favorites_path.parent
        base.mkdir(parents=True, exist_ok=True)
        self.favorites_path.write_text(_format_marks_lines(self._favorites or set()), encoding="utf-8")


_MARKS_STORE: Optional[DirectZapret2MarksStore] = None
_FAVORITES_STORE: Optional[DirectZapret2FavoritesStore] = None


def _marks_store() -> DirectZapret2MarksStore:
    global _MARKS_STORE
    if _MARKS_STORE is None:
        _MARKS_STORE = DirectZapret2MarksStore.default()
    return _MARKS_STORE


def _favorites_store() -> DirectZapret2FavoritesStore:
    global _FAVORITES_STORE
    if _FAVORITES_STORE is None:
        _FAVORITES_STORE = DirectZapret2FavoritesStore.default()
    return _FAVORITES_STORE


def get_favorites_for_target(target_key):
    """Получает избранные стратегии для target."""
    return _favorites_store().get_favorites(target_key)


def invalidate_favorites_cache():
    global _FAVORITES_STORE
    _FAVORITES_STORE = None


def get_favorite_strategies(target=None):
    """Получает избранные стратегии."""
    favorites = _favorites_store().export_favorites()
    if target:
        return favorites.get(target, [])
    return favorites


def add_favorite_strategy(strategy_id, target):
    try:
        before = _favorites_store().is_favorite(target, strategy_id)
        _favorites_store().set_favorite(target, strategy_id, True)
        if not before:
            log(f"Стратегия {strategy_id} добавлена в избранные ({target})", "DEBUG")
        return not before
    except Exception as e:
        log(f"Ошибка добавления в избранные: {e}", "ERROR")
        return False


def remove_favorite_strategy(strategy_id, target):
    try:
        before = _favorites_store().is_favorite(target, strategy_id)
        _favorites_store().set_favorite(target, strategy_id, False)
        if before:
            log(f"Стратегия {strategy_id} удалена из избранных ({target})", "DEBUG")
        return before
    except Exception as e:
        log(f"Ошибка удаления из избранных: {e}", "ERROR")
        return False


def is_favorite_strategy(strategy_id, target=None):
    sid = str(strategy_id or "").strip()
    if not sid:
        return False
    if target:
        return _favorites_store().is_favorite(target, sid)
    return sid in _favorites_store().all_strategy_ids()


def toggle_favorite_strategy(strategy_id, target):
    if is_favorite_strategy(strategy_id, target):
        remove_favorite_strategy(strategy_id, target)
        return False
    add_favorite_strategy(strategy_id, target)
    return True


def clear_favorite_strategies(target=None):
    try:
        if target:
            _favorites_store().clear_target(target)
        else:
            _favorites_store().clear_all()
        return True
    except Exception as e:
        log(f"Ошибка очистки избранных: {e}", "ERROR")
        return False


def get_all_favorite_strategies_flat():
    return _favorites_store().all_strategy_ids()


def invalidate_ratings_cache():
    global _MARKS_STORE
    _MARKS_STORE = None


def get_all_strategy_ratings() -> dict:
    return _marks_store().export_ratings()


def get_strategy_rating(strategy_id: str, target_key: str = None) -> str:
    sid = str(strategy_id or "").strip()
    if not sid:
        return None
    store = _marks_store()
    if target_key:
        mark = store.get_mark(target_key, sid)
        if mark is True:
            return "working"
        if mark is False:
            return "broken"
        return None

    for category, ratings in store.export_ratings().items():
        if sid in ratings:
            return ratings[sid]
    return None


def set_strategy_rating(strategy_id: str, rating: str, target_key: str = None) -> bool:
    if not target_key:
        log("⚠️ set_strategy_rating вызван без target_key", "WARNING")
        return False
    try:
        normalized = str(rating or "").strip().lower()
        mark: Optional[bool]
        if not normalized:
            mark = None
        elif normalized == "working":
            mark = True
        elif normalized == "broken":
            mark = False
        else:
            log(f"⚠️ set_strategy_rating получил неизвестную оценку: {rating}", "WARNING")
            return False
        _marks_store().set_mark(target_key, strategy_id, mark)
        return True
    except Exception as e:
        log(f"Ошибка сохранения оценок стратегий: {e}", "❌ ERROR")
        return False


def toggle_strategy_rating(strategy_id: str, rating: str, target_key: str = None) -> str:
    if not target_key:
        log("⚠️ toggle_strategy_rating вызван без target_key", "WARNING")
        return None
    current = get_strategy_rating(strategy_id, target_key)
    if current == rating:
        set_strategy_rating(strategy_id, None, target_key)
        return None
    set_strategy_rating(strategy_id, rating, target_key)
    return rating


def clear_all_strategy_ratings() -> bool:
    try:
        _marks_store().clear_all()
        return True
    except Exception as e:
        log(f"Ошибка очистки оценок стратегий: {e}", "❌ ERROR")
        return False
