# CtrlNote

Быстрые заметки в [Obsidian](https://obsidian.md) по горячей клавише на Windows (и MVP на Android).

Нажал **Ctrl+Alt+N** → написал / нарисовал / вставил картинку / наговорил → `.md` в vault.

## Возможности (Windows)

- Трей, один экземпляр, автозапуск
- Горячая клавиша, автопапка, шаблоны
- Markdown: Ctrl+B / Ctrl+I / списки по Enter
- **Рисунок (✎)** → PNG + `![[…]]` в Obsidian
- Голос (local Whisper / OpenAI), daily note
- Мастер первого запуска, Setup.exe

## Android (MVP)

Папка [`android/`](android/) — Kotlin + Compose:

- Экран заметки + paint
- Плитка в шторке быстрых настроек (Quick Settings)
- Запись в выбранную папку vault (SAF); синк с ПК — через твой Syncthing/облако

Подробнее про телефон: [`android/README.md`](android/README.md).

## Установка Windows

### Один файл для друга
1. `build_installer.bat`
2. Скинь `dist\installer\CtrlNote-Setup.exe`

### Из исходников
```powershell
.\run.bat
```

Тесты: `.\.venv\Scripts\python.exe -m unittest discover -s . -p "test_*.py" -v`

Сборка: `build_exe.bat` → `install.bat`

## Продвижение

План раздачи и тексты постов: [`PROMOTE.md`](PROMOTE.md). Лендинг: [`site/`](site/).

## Лицензия

Исходники закрыты; **Setup.exe можно использовать и скидывать друзьям** для личного пользования — см. [LICENSE](LICENSE).
