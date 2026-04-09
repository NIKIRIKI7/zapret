from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from config import LISTS_FOLDER, NETROGAT_PATH, OTHER_USER_PATH
from log import log


@dataclass(slots=True)
class HostlistFolderInfo:
    folder_exists: bool
    hostlist_files_count: int
    ipset_files_count: int
    hostlist_lines: int
    ipset_lines: int
    folder: str


@dataclass(slots=True)
class HostlistEntriesState:
    entries: list[str]
    base_set: set[str] | None = None


class HostlistPageController:
    @staticmethod
    def _is_ipset_file_name(file_name: str) -> bool:
        lower = (file_name or "").lower()
        return lower.startswith("ipset-") or "ipset" in lower or "subnet" in lower

    @staticmethod
    def _count_lines(folder: str, file_names: list[str], *, max_files: int, skip_comments: bool) -> int:
        total = 0
        for file_name in file_names[:max_files]:
            try:
                path = os.path.join(folder, file_name)
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    if skip_comments:
                        total += sum(1 for line in fh if line.strip() and not line.startswith("#"))
                    else:
                        total += sum(1 for _ in fh)
            except Exception:
                continue
        return total

    def load_folder_info(self) -> HostlistFolderInfo:
        if not os.path.exists(LISTS_FOLDER):
            return HostlistFolderInfo(False, 0, 0, 0, 0, LISTS_FOLDER)

        txt_files = [name for name in os.listdir(LISTS_FOLDER) if name.endswith(".txt")]
        ipset_files = [name for name in txt_files if self._is_ipset_file_name(name)]
        hostlist_files = [name for name in txt_files if name not in ipset_files]

        return HostlistFolderInfo(
            folder_exists=True,
            hostlist_files_count=len(hostlist_files),
            ipset_files_count=len(ipset_files),
            hostlist_lines=self._count_lines(LISTS_FOLDER, hostlist_files, max_files=12, skip_comments=False),
            ipset_lines=self._count_lines(LISTS_FOLDER, ipset_files, max_files=12, skip_comments=True),
            folder=LISTS_FOLDER,
        )

    @staticmethod
    def open_lists_folder() -> None:
        os.startfile(LISTS_FOLDER)

    @staticmethod
    def rebuild_hostlists() -> None:
        from utils.hostlists_manager import startup_hostlists_check

        startup_hostlists_check()

    @staticmethod
    def load_domains_entries() -> HostlistEntriesState:
        from utils.hostlists_manager import ensure_hostlists_exist

        ensure_hostlists_exist()
        entries: list[str] = []
        if os.path.exists(OTHER_USER_PATH):
            with open(OTHER_USER_PATH, "r", encoding="utf-8") as fh:
                entries = [line.strip() for line in fh if line.strip()]
        return HostlistEntriesState(entries=entries)

    @staticmethod
    def save_domains_entries(entries: list[str]) -> bool:
        from utils.hostlists_manager import rebuild_other_files

        os.makedirs(os.path.dirname(OTHER_USER_PATH), exist_ok=True)
        with open(OTHER_USER_PATH, "w", encoding="utf-8") as fh:
            fh.write("\n".join(entries) + ("\n" if entries else ""))
        try:
            rebuild_other_files()
        except Exception:
            pass
        return True

    @staticmethod
    def open_domains_user_file() -> None:
        from utils.hostlists_manager import ensure_hostlists_exist

        ensure_hostlists_exist()
        if os.path.exists(OTHER_USER_PATH):
            subprocess.run(["explorer", "/select,", OTHER_USER_PATH])
        else:
            os.makedirs(os.path.dirname(OTHER_USER_PATH), exist_ok=True)
            subprocess.run(["explorer", os.path.dirname(OTHER_USER_PATH)])

    @staticmethod
    def reset_domains_file() -> bool:
        from utils.hostlists_manager import reset_other_file_from_template

        return bool(reset_other_file_from_template())

    @staticmethod
    def load_ipset_all_entries() -> HostlistEntriesState:
        from utils.ipsets_manager import (
            IPSET_ALL_USER_PATH,
            ensure_ipset_all_user_file,
            get_ipset_all_base_set,
        )

        ensure_ipset_all_user_file()
        entries: list[str] = []
        if os.path.exists(IPSET_ALL_USER_PATH):
            with open(IPSET_ALL_USER_PATH, "r", encoding="utf-8") as fh:
                entries = [line.strip() for line in fh if line.strip()]
        return HostlistEntriesState(entries=entries, base_set=get_ipset_all_base_set())

    @staticmethod
    def save_ipset_all_entries(entries: list[str]) -> bool:
        from utils.ipsets_manager import IPSET_ALL_USER_PATH, sync_ipset_all_after_user_change

        os.makedirs(os.path.dirname(IPSET_ALL_USER_PATH), exist_ok=True)
        with open(IPSET_ALL_USER_PATH, "w", encoding="utf-8") as fh:
            fh.write("\n".join(entries) + ("\n" if entries else ""))
        return bool(sync_ipset_all_after_user_change())

    @staticmethod
    def open_ipset_all_user_file() -> None:
        from utils.ipsets_manager import IPSET_ALL_USER_PATH, ensure_ipset_all_user_file

        ensure_ipset_all_user_file()
        if os.path.exists(IPSET_ALL_USER_PATH):
            subprocess.run(["explorer", "/select,", IPSET_ALL_USER_PATH])
        else:
            os.makedirs(os.path.dirname(IPSET_ALL_USER_PATH), exist_ok=True)
            subprocess.run(["explorer", os.path.dirname(IPSET_ALL_USER_PATH)])

    @staticmethod
    def load_netrogat_entries() -> HostlistEntriesState:
        from utils.netrogat_manager import ensure_netrogat_user_file, get_netrogat_base_set, load_netrogat

        ensure_netrogat_user_file()
        return HostlistEntriesState(entries=load_netrogat(), base_set=get_netrogat_base_set())

    @staticmethod
    def save_netrogat_entries(domains: list[str]) -> bool:
        from utils.netrogat_manager import save_netrogat

        return bool(save_netrogat(domains))

    @staticmethod
    def open_netrogat_user_file() -> None:
        from utils.netrogat_manager import NETROGAT_USER_PATH, ensure_netrogat_user_file

        ensure_netrogat_user_file()
        if NETROGAT_USER_PATH and os.path.exists(NETROGAT_USER_PATH):
            subprocess.run(["explorer", "/select,", NETROGAT_USER_PATH])
        else:
            subprocess.run(["explorer", LISTS_FOLDER])

    @staticmethod
    def open_netrogat_final_file() -> None:
        from utils.netrogat_manager import ensure_netrogat_exists

        ensure_netrogat_exists()
        if NETROGAT_PATH and os.path.exists(NETROGAT_PATH):
            subprocess.run(["explorer", "/select,", NETROGAT_PATH])
        else:
            subprocess.run(["explorer", LISTS_FOLDER])

    @staticmethod
    def add_missing_netrogat_defaults() -> int:
        from utils.netrogat_manager import ensure_netrogat_base_defaults

        return int(ensure_netrogat_base_defaults())

    @staticmethod
    def load_ipset_ru_entries() -> HostlistEntriesState:
        from utils.ipsets_manager import (
            IPSET_RU_USER_PATH,
            ensure_ipset_ru_user_file,
            get_ipset_ru_base_set,
        )

        ensure_ipset_ru_user_file()
        entries: list[str] = []
        if os.path.exists(IPSET_RU_USER_PATH):
            with open(IPSET_RU_USER_PATH, "r", encoding="utf-8") as fh:
                entries = [line.strip() for line in fh if line.strip()]
        return HostlistEntriesState(entries=entries, base_set=get_ipset_ru_base_set())

    @staticmethod
    def save_ipset_ru_entries(entries: list[str]) -> bool:
        from utils.ipsets_manager import IPSET_RU_USER_PATH, sync_ipset_ru_after_user_change

        os.makedirs(os.path.dirname(IPSET_RU_USER_PATH), exist_ok=True)
        with open(IPSET_RU_USER_PATH, "w", encoding="utf-8") as fh:
            fh.write("\n".join(entries) + ("\n" if entries else ""))
        return bool(sync_ipset_ru_after_user_change())

    @staticmethod
    def open_ipset_ru_user_file() -> None:
        from utils.ipsets_manager import IPSET_RU_USER_PATH, ensure_ipset_ru_user_file

        ensure_ipset_ru_user_file()
        if IPSET_RU_USER_PATH and os.path.exists(IPSET_RU_USER_PATH):
            subprocess.run(["explorer", "/select,", IPSET_RU_USER_PATH])
        else:
            subprocess.run(["explorer", LISTS_FOLDER])

    @staticmethod
    def open_ipset_ru_final_file() -> None:
        from utils.ipsets_manager import IPSET_RU_PATH, rebuild_ipset_ru_files

        rebuild_ipset_ru_files()
        if IPSET_RU_PATH and os.path.exists(IPSET_RU_PATH):
            subprocess.run(["explorer", "/select,", IPSET_RU_PATH])
        else:
            subprocess.run(["explorer", LISTS_FOLDER])
