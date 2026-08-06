# CtrlNote

Быстрые заметки в [Obsidian](https://obsidian.md) по горячей клавише.

**Ctrl+Alt+N** → написал / нарисовал / вставил картинку / наговорил → `.md` в vault.

## Скачать (Windows)

→ **[CtrlNote-Setup.exe](https://github.com/emaling85/CtrlNote/releases/latest/download/CtrlNote-Setup.exe)**  
(релизы: [Releases](https://github.com/emaling85/CtrlNote/releases))

Ставится в `%LOCALAPPDATA%\CtrlNote`, ярлыки на стол и в Пуск. При первом запуске укажи папку vault.

## Возможности

- Трей, один экземпляр, автозапуск
- Горячая клавиша, автопапка, шаблоны
- Markdown: Ctrl+B / Ctrl+I / списки по Enter
- Рисунок (✎) → PNG в Obsidian
- Голос (local Whisper / OpenAI), daily note

## Разработка

```powershell
.\run.bat
```

Тесты: `.\.venv\Scripts\python.exe -m unittest discover -s . -p "test_*.py" -v`  
Сборка установщика: `build_installer.bat` → `dist\installer\CtrlNote-Setup.exe` (в git не кладётся — только в Releases)

Android MVP: папка [`android/`](android/).

Лендинг: [`site/`](site/).

## Лицензия

Исходники закрыты; Setup.exe можно ставить и скидывать друзьям для личного пользования — см. [LICENSE](LICENSE).
