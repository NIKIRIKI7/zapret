from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class HomeLaunchMethodPlan:
    value: str
    info: str


@dataclass(slots=True)
class HomeDpiStatusPlan:
    value: str
    info: str
    status_color: str
    show_start: bool
    show_stop: bool


@dataclass(slots=True)
class HomeAutostartPlan:
    value: str
    info: str
    status_color: str


@dataclass(slots=True)
class HomeSubscriptionPlan:
    value: str
    info: str
    status_color: str


@dataclass(slots=True)
class HomeAutostartDispatchPlan:
    target: str
    enabled: bool


class HomePageController:
    _LAUNCH_METHOD_LABELS = {
        "direct_zapret2": "page.home.launch_method.direct_z2",
        "direct_zapret1": "page.home.launch_method.direct_z1",
        "orchestra": "page.home.launch_method.orchestra",
        "direct_zapret2_orchestra": "page.home.launch_method.orchestra_z2",
    }

    @staticmethod
    def create_autostart_worker():
        from ui.home_autostart_worker import AutostartCheckWorker

        return AutostartCheckWorker()

    def build_launch_method_plan(self, *, language: str) -> HomeLaunchMethodPlan:
        from ui.text_catalog import tr as tr_catalog

        try:
            from strategy_menu import get_strategy_launch_method

            method = (get_strategy_launch_method() or "").strip().lower()
            if method:
                label_key = self._LAUNCH_METHOD_LABELS.get(method, self._LAUNCH_METHOD_LABELS["direct_zapret2"])
                return HomeLaunchMethodPlan(
                    value=tr_catalog(label_key, language=language, default="Zapret 2"),
                    info=tr_catalog(
                        "page.home.strategy.current_method",
                        language=language,
                        default="Текущий метод запуска",
                    ),
                )
        except Exception:
            pass

        return HomeLaunchMethodPlan(
            value=tr_catalog(self._LAUNCH_METHOD_LABELS["direct_zapret2"], language=language, default="Zapret 2"),
            info=tr_catalog("page.home.strategy.current_method", language=language, default="Текущий метод запуска"),
        )

    @staticmethod
    def short_dpi_error(last_error: str) -> str:
        text = str(last_error or "").strip()
        if not text:
            return ""
        first_line = text.splitlines()[0].strip()
        if len(first_line) <= 160:
            return first_line
        return first_line[:157] + "..."

    def build_dpi_status_plan(self, *, state: str | bool, last_error: str, language: str) -> HomeDpiStatusPlan:
        from ui.text_catalog import tr as tr_catalog

        phase = str(state or "").strip().lower()
        if phase not in {"autostart_pending", "starting", "running", "stopping", "failed", "stopped"}:
            phase = "running" if bool(state) else "stopped"

        if phase == "running":
            return HomeDpiStatusPlan(
                value=tr_catalog("page.home.status.running", language=language, default="Запущен"),
                info=tr_catalog("page.home.status.bypass_active", language=language, default="Обход блокировок активен"),
                status_color="running",
                show_start=False,
                show_stop=True,
            )
        if phase == "autostart_pending":
            return HomeDpiStatusPlan(
                value="Автозапуск запланирован",
                info="Подготавливаем стартовый запуск после инициализации",
                status_color="warning",
                show_start=False,
                show_stop=False,
            )
        if phase == "starting":
            return HomeDpiStatusPlan(
                value="Запускается",
                info="Ждём подтверждение процесса winws",
                status_color="warning",
                show_start=False,
                show_stop=False,
            )
        if phase == "stopping":
            return HomeDpiStatusPlan(
                value="Останавливается",
                info="Завершаем процесс и освобождаем WinDivert",
                status_color="warning",
                show_start=False,
                show_stop=False,
            )
        if phase == "failed":
            return HomeDpiStatusPlan(
                value="Ошибка запуска",
                info=self.short_dpi_error(last_error) or "Процесс не подтвердился или завершился сразу",
                status_color="stopped",
                show_start=True,
                show_stop=False,
            )
        return HomeDpiStatusPlan(
            value=tr_catalog("page.home.status.stopped", language=language, default="Остановлен"),
            info=tr_catalog("page.home.status.press_start", language=language, default="Нажмите Запустить"),
            status_color="stopped",
            show_start=True,
            show_stop=False,
        )

    def build_autostart_status_plan(self, *, enabled: bool, language: str) -> HomeAutostartPlan:
        from ui.text_catalog import tr as tr_catalog

        if enabled:
            return HomeAutostartPlan(
                value=tr_catalog("page.home.autostart.enabled", language=language, default="Включён"),
                info=tr_catalog("page.home.autostart.with_windows", language=language, default="Запускается с Windows"),
                status_color="running",
            )
        return HomeAutostartPlan(
            value=tr_catalog("page.home.autostart.disabled", language=language, default="Отключён"),
            info=tr_catalog("page.home.autostart.manual", language=language, default="Запускайте вручную"),
            status_color="neutral",
        )

    def build_subscription_status_plan(
        self,
        *,
        is_premium: bool,
        days: int | None,
        language: str,
    ) -> HomeSubscriptionPlan:
        from ui.text_catalog import tr as tr_catalog

        if is_premium:
            if days:
                return HomeSubscriptionPlan(
                    value=tr_catalog("page.home.subscription.premium", language=language, default="Premium"),
                    info=tr_catalog(
                        "page.home.subscription.days_left",
                        language=language,
                        default="Осталось {days} дней",
                    ).format(days=days),
                    status_color="running",
                )
            return HomeSubscriptionPlan(
                value=tr_catalog("page.home.subscription.premium", language=language, default="Premium"),
                info=tr_catalog(
                    "page.home.subscription.all_features",
                    language=language,
                    default="Все функции доступны",
                ),
                status_color="running",
            )

        return HomeSubscriptionPlan(
            value=tr_catalog("page.home.subscription.free", language=language, default="Free"),
            info=tr_catalog("page.home.subscription.basic", language=language, default="Базовые функции"),
            status_color="neutral",
        )

    @staticmethod
    def build_autostart_dispatch_plan(*, has_runtime_state: bool, has_store: bool, enabled: bool) -> HomeAutostartDispatchPlan:
        if has_runtime_state:
            return HomeAutostartDispatchPlan(target="runtime", enabled=bool(enabled))
        if has_store:
            return HomeAutostartDispatchPlan(target="store", enabled=bool(enabled))
        return HomeAutostartDispatchPlan(target="page", enabled=bool(enabled))
