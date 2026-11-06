# Управление мышью: draw.io и профиль Visio

Ветка `codex/visio-controls` создана от `dev` форка `coodi/drawio-codex`.
Ветки `master` в форке нет. Режим импорта/экспорта Visio в исходниках есть;
отдельного профиля управления Visio на этой базе не было.

## Что включить

В обычном редакторе: **Дополнительно → Управление мышью → Visio**.
В минимальных темах пункт доступен внутри меню настроек. Вернуть исходное
управление можно пунктом **draw.io**. Переключение немедленное, выбор сохраняется
в настройках браузера, если сохранение настроек разрешено. Сам документ
от переключения не меняется. Параметр URL `local=1` в draw.io отключает
сохранение настроек: при нём профиль выбирается только на текущий сеанс. Неизвестные сохранённые значения дают draw.io.

Профиль ориентирован на жесты настольного Visio для Windows:

| Жест | Профиль Visio |
| --- | --- |
| Колесо без Ctrl | Прокрутка, а не масштабирование |
| Ctrl + колесо | Масштабирование |
| Ctrl + Shift + левый щелчок | Приближение |
| Ctrl + Shift + левое перетаскивание | Масштабирование по рамке, в том числе поверх фигур |
| Ctrl + Shift + правый щелчок | Отдаление без контекстного меню |
| Ctrl + Shift + правое перетаскивание | Панорамирование без изменения масштаба |
| Ctrl + Shift + W | Вписать диаграмму в окно |

Для жестов навигации используется физическая клавиша Ctrl и на macOS.
Штатные сочетания draw.io с Cmd для операций над объектами не переназначаются.
Профиль не заменяет инструменты Pointer/Text/Connector, меню и ленту Visio.
Горячие клавиши браузера могут перехватываться самим браузером.
Щелчковое приближение/отдаление использует штатный центр масштаба draw.io;
масштаб по рамке использует выделенную область.

Во время редактирования текста, открытого диалога или активного свободного
рисования Ctrl+Shift-жесты не перехватываются. Esc отменяет рамку масштаба.
Отпускание модификаторов после начала жеста не превращает рамку в выделение.
Обычные правый и средний drag, а также Space+drag остаются доступны.

## Сравнение документации

Проверено 6 ноября 2026 года. Ниже сравниваются конкретные документированные
жесты; версии desktop/web и инструмент под курсором имеют значение.
Обозначение «drag» означает удерживание кнопки мыши и перетаскивание.

| Операция | Visio | draw.io | Inkscape | Illustrator |
| --- | --- | --- | --- | --- |
| Копия мышью | Ctrl+drag [V2] | Ctrl+drag [D] | Ctrl+drag в Selector ограничивает направление, а не дублирует [I1] | Alt+drag; добавить Shift для ограничения направления [A1] |
| Движение по оси | Shift+drag [V3] | Shift+drag в выбранной версии исходников; не нужно менять | Ctrl+drag [I1] | Shift+drag [A1] |
| Пропорции при изменении размера | Не переопределяются этим профилем: проверенные статьи не задают здесь полный контракт | Shift+drag маркера [D] | Ctrl+drag маркера [I1] | Shift+drag маркера; Alt — от центра; Shift+Alt — вместе [A2] |
| Навигация модификаторами | Ctrl+колесо; Ctrl+Shift+кнопки мыши и рамка [V1] | Зависит от zoomWheel; Alt или Ctrl+Shift+колесо описаны в справке [D] | +/− без Ctrl; Ctrl+стрелки — прокрутка [I3] | См. отдельный Zoom/Hand tool; это не эквивалент Ctrl+Shift-жестов Visio |
| Alt при работе с объектами | Не вводим неподтверждённые назначения | Отключение привязки во время движения/resize, выбор под фигурой, работа с контейнерами; контекст важен [D] | Alt в рамке включает выбор касанием; с уже выделенными объектами может перемещать выделение [I1] | Копия при движении [A1]; масштаб от центра при resize [A2] |
| Термин «clone» | Здесь речь о независимой копии | Справка называет Ctrl+drag clone/duplicate [D] | Clone связан с оригиналом; Alt+D создаёт его, Alt+Shift+D разрывает связь [I2] | В рассмотренной операции Alt+drag создаёт копию [A1] |

Отсюда решение: не добавлять Illustrator-подобный Alt+drag к профилю Visio,
не превращать Ctrl+drag в связанный clone Inkscape, сохранить существующие
копирование, ограничение движения и операции Alt в draw.io. Меняются именно
конфликтующие жесты навигации. Чтобы создать копию по оси, начните Ctrl+drag,
затем добавьте Shift; Ctrl+Shift, зажатые **до** начала drag, означают рамку
масштаба в профиле Visio.

Для resize групп, соединителей и контейнеров сохраняется поведение draw.io:
это не полная эмуляция всех инструментов Visio. Подтверждённый эффект Alt
в PowerPoint не переносится автоматически на Visio.

## Источники

- [V1: Microsoft — Zoom and pan](https://support.microsoft.com/en-us/visio/zoom-and-pan-in-a-diagram).
- [V2: Microsoft — Select, copy, and move shapes (web)](https://support.microsoft.com/en-us/visio/select-copy-and-move-shapes-in-visio-for-the-web).
- [V3: Microsoft — Select, move, resize, rotate](https://support.microsoft.com/en-us/visio/select-move-resize-and-rotate-shapes).
- [V4: Microsoft — Keyboard shortcuts](https://support.microsoft.com/en-us/accessibility/visio/keyboard-shortcuts-for-visio).
- [D: draw.io — Mouse + keyboard shortcuts](https://www.drawio.com/docs/reference/shortcuts/modifier-shortcuts-in-diagrams/).
- [I1: Inkscape Beginners’ Guide — Selector](https://inkscape-manuals.readthedocs.io/en/latest/selector-tool.html).
- [I2: Inkscape project wiki — Clones](https://wiki.inkscape.org/wiki/Scratchpad_cloningtutorial).
- [I3: Inkscape project wiki — Illustrator users](https://wiki.inkscape.org/wiki/IllustratorUsers).
- [A1: Adobe — Duplicate objects](https://helpx.adobe.com/illustrator/desktop/manage-objects/edit-objects/duplicate-objects.html).
- [A2: Adobe — Scale objects](https://helpx.adobe.com/illustrator/desktop/manage-objects/reshape-transform-objects/scale-objects.html).

Основная страница Inkscape keys.html вернула 403 при проверке, поэтому
сравнение ограничено доступными руководством Selector и wiki проекта.
В них нет единого современного контракта всех Ctrl+Shift+Alt+mouse-комбинаций.

## Реализация и проверка

`js/diagramly/ControlProfiles.js` загружается после приложения и до `App.main`
из `bootstrap.js`, включая `dev=1`. Пересборка `app.min.js` для изменения
этого модуля не требуется. Модификации локальны экземпляру редактора;
прототипы mxGraph и значения zoomWheel не изменяются.

```bash
node --check src/main/webapp/js/diagramly/ControlProfiles.js
node --check src/main/webapp/js/bootstrap.js
node --test tests/control-profiles.test.cjs
python3 -m http.server 45801 --bind 127.0.0.1 --directory src/main/webapp
```

Открыть `http://127.0.0.1:45801/index.html?offline=1&mode=device&ui=kennedy&lang=ru`.
Проверить переключатель, колесо, рамку и правую кнопку; затем вернуться
в draw.io и перезагрузить страницу для проверки сохранённого выбора.

Node-тесты выполняют код с изолированными адаптерами редактора. Они проверяют
политику колеса, рамку в обоих направлениях, отпускание модификаторов,
отмену жестов, правый drag с возвратом в исходную точку, fallback,
настройки, меню, блокировку при text/dialog/freehand и удаление слушателя.
Они не заменяют проверку реальных мышей/тачпадов на Windows/macOS.
