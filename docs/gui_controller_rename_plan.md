# GUI Controller Rename Plan

Дата фиксации: 2026-04-11

Этот документ описывает не конечный архитектурный контракт, а безопасный план миграции для слоя `controller` в GUI. Его задача не "сразу всё переписать", а дать понятный порядок действий, при котором проект не скатится в хаос из-за одновременного переименования, переноса файлов и переписывания логики.

Обновление состояния: 2026-04-12

На дату обновления план остаётся актуальным по стратегии, но уже не полностью совпадает со старой картой путей. За прошедший рефакторинг проект заметно сдвинулся в сторону feature-local UI-структуры. Это значит:

- naming-first стратегия остаётся канонической;
- часть folder-move этапа уже фактически произошла;
- дальше нельзя опираться на старую картину `src/ui/pages/...` как на единственный живой UI-слой;
- план нужно читать как живой маршрут миграции, а не как замороженный список старых путей.

## Зачем нужен план

Сейчас слово `controller` в проекте используется для нескольких разных ролей сразу:

- controller окна;
- presenter страницы;
- coordinator продуктового сценария;
- runtime-координатор живого процесса;
- service диагностики или действий.

Из-за этого одно и то же слово скрывает разные обязанности. Новичку трудно понять, чем файл реально владеет: интерфейсом, workflow, runtime-состоянием или только подготовкой данных для показа.

## Главная цель

- Сначала выровнять язык архитектуры.
- Потом выровнять имена классов и файлов.
- Только после этого при необходимости переносить файлы по новым папкам.
- И только в самом конце разрезать большие смешанные классы на более узкие слои.

Ключевой принцип такой:

`смысловая ясность -> переименование -> перенос -> внутренняя декомпозиция`

## Текущий статус проекта на 2026-04-12

На текущий момент уже видны реальные structural shifts, которые надо учитывать в следующих итерациях.

### Что уже произошло

- UI для нескольких фич уже переехал ближе к самим фичам.
- В проекте появились feature-local UI-пакеты:
  - `src/updater/ui`
  - `src/donater/ui`
  - `src/dns/ui`
  - `src/hosts/ui`
  - `src/lists/ui`
  - `src/log/ui`
  - `src/blockcheck/ui`
  - `src/telegram_proxy/ui`
- Старый `src/core/hostlist_page_controller.py` удалён.
- Его роль сейчас живёт в `src/lists/controller.py` как `HostlistPageController`.

### Что ещё не произошло

- Большинство ключевых controller-имён всё ещё старые:
  - `DPIController`
  - `PremiumPageController`
  - `UpdatePageController`
  - `UpdatePageViewController`
  - `ControlPageController`
  - `ConnectionPageController`
  - и другие page/feature controller-классы
- Значит проблема терминологии остаётся живой даже после уже выполненных переносов по папкам.

### Практический вывод

- Для уже переехавших фич приоритетом становится не новый folder move, а naming-only очистка.
- Старые ссылки на `src/ui/pages/...` внутри этого плана надо трактовать как исторический контекст, если у фичи уже появился свой `feature/ui` слой.
- Для новых итераций нужно опираться на текущие feature-local точки входа страниц, а не на старые общие страницы из `src/ui/pages`.

## Что нельзя делать

- Нельзя одновременно переименовывать класс, переносить файл и переписывать внутреннюю логику того же слоя.
- Нельзя оставлять рядом старое и новое имя "временно для совместимости", если срез миграции уже завершён.
- Нельзя проводить одну миграцию сразу через `update`, `premium`, `dpi`, `dns` и `telegram_proxy` одновременно.
- Нельзя возвращать новый слой в расплывчатое имя `controller`, если роль уже можно назвать точнее.
- Нельзя считать этап завершённым, если по проекту ещё остались старые импорты прежнего имени.

## Словарь ролей

### Presenter

Слой, который подготавливает данные и планы отображения для страницы.

Признаки:

- возвращает `Plan`, `State`, `Result`;
- решает, какой текст, статус или визуальное состояние показать;
- не должен быть владельцем системного процесса;
- не должен быть владельцем файлового runtime.

### WorkflowService

Слой, который координирует сценарий конкретной фичи.

Признаки:

- связывает экран, сервисы, операции и результаты;
- управляет шагами сценария;
- может работать с данными фичи;
- не должен быть владельцем глобального UI-окна.

### RuntimeCoordinator

Слой, который владеет живым жизненным циклом процесса или фонового runtime.

Признаки:

- потоки;
- запуск и остановка;
- retry, restart, transition;
- контроль актуального runtime-состояния.

### WindowController / WindowService

Слой управления главным окном и общими UI-механиками окна.

Признаки:

- геометрия окна;
- закрытие;
- общие уведомления;
- общие действия окна.

### DiagnosticsService / ActionService

Узкие прикладные слои для диагностики или отдельных действий.

Признаки:

- не владеют всей фичей целиком;
- решают ограниченный набор операций;
- их имя должно отражать конкретную обязанность.

## Приоритет миграции

### Волна 1. Самые путаные и центральные имена

- `dpi.runtime.controller.DPIController` -> `DpiRuntimeCoordinator`
- `donater.premium_page_controller.PremiumPageController` -> `PremiumPagePresenter`
- `updater.update_page_controller.UpdatePageController` -> `UpdateWorkflowCoordinator`
- `updater.update_page_view_controller.UpdatePageViewController` -> `UpdatePagePresenter`
- `ui.control_page_controller.ControlPageController` -> `ControlPagePresenter`
- `ui.connection_page_controller.ConnectionPageController` -> `ConnectionPagePresenter`

### Волна 2. Остальные page-level presenter слои

- `ui.about_page_controller.AboutPageController` -> `AboutPagePresenter`
- `ui.appearance_page_controller.AppearancePageController` -> `AppearanceSettingsPresenter`
- `dpi.dpi_settings_page_controller.DpiSettingsPageController` -> `DpiSettingsPresenter`

### Волна 3. Feature workflow слои

- `dns.network_page_controller.NetworkPageController` -> `NetworkSettingsWorkflowService`
- `dns.dns_check_page_controller.DNSCheckPageController` -> `DnsCheckWorkflowService`
- `hosts.page_controller.HostsPageController` -> `HostsWorkflowService`
- `lists.controller.HostlistPageController` -> `HostlistWorkflowService`
- `blockcheck.page_controller.BlockcheckPageController` -> `BlockcheckCoordinator`
- `blockcheck.strategy_scan_page_controller.StrategyScanPageController` -> `StrategyScanCoordinator`
- `orchestra.page_controller.OrchestraPageController` -> `OrchestraWorkflowService`

### Волна 4. Telegram proxy и узкие сервисные слои

- `telegram_proxy.page_runtime_controller.TelegramProxyRuntimeController` -> оставить или уточнить как `TelegramProxyRuntimeWorkflow`
- `telegram_proxy.page_actions_controller.TelegramProxyPageActionsController` -> `TelegramProxyActionService`
- `telegram_proxy.page_settings_controller.TelegramProxySettingsController` -> `TelegramProxySettingsService`
- `telegram_proxy.diagnostics_controller.TelegramProxyDiagnosticsController` -> `TelegramProxyDiagnosticsService`

### Волна 5. Только после выровненных имён

- физический перенос файлов по более точным папкам;
- вынос больших классов в отдельные `presentation`, `runtime`, `workflow`, `diagnostics` слои;
- удаление старых расплывчатых мест без fallback-алиасов.

## Рекомендуемый порядок работы

### Этап 1. Naming-only

На этом этапе меняются только:

- имя класса;
- при необходимости имя файла;
- импорты и use-site'ы.

На этом этапе не меняются:

- алгоритмы;
- runtime-поведение;
- файловая модель;
- состав public API шире, чем нужно для переименования.

### Этап 2. Повторный поиск по проекту

После каждого завершённого среза обязательно делать:

- поиск старого имени через `rg`;
- проверку, что не осталось старых импортов;
- проверку, что не появились два имени для одной и той же роли.

### Этап 3. Folder move

Только после успешного naming-only этапа для конкретной фичи допускается:

- перенос в более точную папку;
- обновление путей импорта;
- повторный поиск старых путей.

Исключение для текущего состояния проекта:

- если у фичи уже существует устойчивый feature-local UI слой, например `updater/ui`, `donater/ui`, `dns/ui`, `hosts/ui`, `lists/ui`, `log/ui`, `blockcheck/ui`, `telegram_proxy/ui`, то для этой фичи folder-move этап считается частично выполненным;
- в таких срезах следующим приоритетом становится выравнивание имён и ролей, а не дополнительный перенос файлов ради самого переноса.

### Этап 4. Responsibility split

Только после стабильного переименования и переноса допускается:

- выделение presenter из workflow;
- выделение runtime-ядра из page-level класса;
- вынос диагностики и действий в отдельные узкие сервисы.

## Рекомендуемые итерации

### Итерация A. Update

Цель:

- показать образцовый пример разделения `workflow` и `presentation`.

Шаги:

- переименовать `UpdatePageController`;
- переименовать `UpdatePageViewController`;
- обновить все импорты;
- убедиться, что экран обновлений в `src/updater/ui/page.py` собирается и читается без старых имён.

### Итерация B. Premium

Цель:

- выровнять page-level presentation слой Premium.

Шаги:

- переименовать `PremiumPageController`;
- обновить use-site'ы в `src/donater/ui/page.py` и связанных workflow-модулях;
- убедиться, что не осталось старого имени в импортах.

### Итерация C. DPI runtime

Цель:

- явно назвать runtime-ядро как runtime-слой, а не как общий controller.

Шаги:

- переименовать `DPIController`;
- обновить все use-site'ы в `managers`, `dpi`, `startup`, `runtime_preset_switch_policy` и связанных местах;
- отдельно проверить, что внешнее поведение запуска и остановки не поменялось.

### Итерация D. UI presenters

Цель:

- сделать слой `src/ui` читаемым как presentation/page слой.

Шаги:

- переименовать `ControlPageController`, `ConnectionPageController`, `AboutPageController`, `AppearancePageController`;
- обновить page use-site'ы;
- убедиться, что `ui` теперь читается как слой экранного поведения, а не как набор абстрактных controller-ов.

### Итерация E. Feature workflows

Цель:

- назвать feature-классы по их реальной роли.

Шаги:

- идти фичами по одной: сначала `dns`, потом `hosts`, потом `lists`, потом `blockcheck`, потом `orchestra`;
- не смешивать эти срезы между собой в одном коммите без необходимости.

## Текущие точки входа, на которые надо ориентироваться при миграции

Ниже перечислены не все use-site'ы, а главные живые точки входа страниц, которые уже показывают новую структуру проекта.

- `update` -> `src/updater/ui/page.py`
- `premium` -> `src/donater/ui/page.py`
- `network/dns` -> `src/dns/ui/page.py`
- `hosts` -> `src/hosts/ui/page.py`
- `lists/hostlist` -> `src/lists/ui/hostlist_page.py`
- `logs` -> `src/log/ui/page.py`
- `blockcheck` -> `src/blockcheck/ui/page.py`
- `telegram_proxy` -> `src/telegram_proxy/ui/page.py`

Эти пути важнее старых ссылок на `src/ui/pages/...`, если между ними есть расхождение.

## Критерии завершения каждого среза

Срез считается завершённым только если:

- новое имя отражает фактическую роль класса;
- все use-site'ы обновлены;
- поиск по старому имени не находит живых импортов и ссылок в исходниках;
- не оставлено временных alias-обёрток;
- изменённые файлы проходят хотя бы `compileall`;
- в отчёте зафиксировано, что именно было переименовано и что сознательно не входило в этот срез.

## Минимальная проверка после каждого среза

- `python -m compileall` по изменённым файлам;
- `rg` по старому и новому имени;
- узкая ручная проверка точки входа, связанной с фичей;
- отдельная запись о том, что не удалось проверить в WSL из-за Windows-first окружения.

## Места повышенного риска

- `dpi/runtime/controller.py`
- `ui/pages/direct_user_presets_page_controller.py`
- `ui/pages/zapret2/strategy_detail_page_controller.py`
- `updater/update_page_controller.py`
- `lists/controller.py`

Это не повод откладывать миграцию, но повод не смешивать rename-этап с глубокой внутренней переработкой.

## Что план больше не предполагает по умолчанию

- Не предполагается, что вся page-level UI логика будет жить только в `src/ui/pages`.
- Не предполагается, что перенос папок является обязательным первым шагом для каждой фичи.
- Не предполагается, что старые пути из раннего состояния проекта остаются каноническими после появления feature-local UI пакетов.

## Ожидаемый результат

После завершения плана проект должен читаться так:

- `ui` содержит окно, presentation и page-level инфраструктуру;
- feature-папки содержат workflow и предметные сценарии;
- runtime-папки явно обозначают жизненный цикл процессов;
- диагностика и узкие действия вынесены в отдельные сервисные слои;
- слово `controller` используется только там, где оно действительно помогает, а не скрывает несколько ролей сразу.

## Связанные документы

- `docs/gui_architecture_contract.md`
- `docs/gui_build_runtime_contract.md`

Этот план не заменяет архитектурный контракт. Он описывает, в каком порядке прийти к более чистой и предсказуемой терминологии без разрушения текущего рабочего кода.
