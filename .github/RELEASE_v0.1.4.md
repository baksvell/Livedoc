# Release v0.1.4

Соответствует пакету **living-doc 0.1.4** на [PyPI](https://pypi.org/project/living-doc/).

## Added

- **Anchor validation**: каждый `code_id` в анкорах Markdown должен существовать среди распарсенного кода; неизвестные ссылки дают ошибку проверки (exit 1) и блок **Unknown code_id references** / в JSON поле `unknown_anchors`.
- **Code locations in reports**: в текстовом отчёте об устаревшей доке — строка `Code: path:line` (путь от корня проекта); в JSON у `code_changes` — поля `code_file` и `code_line`; подсказка, если символ удалён из кода.

## Changed

- README и spec обновлены под валидацию и расположение кода в отчёте.

Полный список: `CHANGELOG.md` в корне репозитория.
