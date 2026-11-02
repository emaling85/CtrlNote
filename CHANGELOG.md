# Changelog

All notable changes to CtrlNote. Versions follow [Semantic Versioning](https://semver.org/).

## [1.3.0] — 2026-11-02

### Added
- **CtrlNote Trader edition** — a separate download with a built-in trading journal.
  - `Ctrl+Alt+T` opens a trade window: pick **Profit / Loss / Breakeven** first (keys `1` `2` `3`), then fill in the details.
  - Memecoin-friendly fields: ticker, contract address (auto-filled from the clipboard), entry/exit in SOL, market cap in/out (`120K → 450K`), stop, platform, risk.
  - Live PnL in **SOL, USD and %** — the SOL price is fetched automatically and can be edited.
  - Tap-to-select chips for setups, emotions and mistakes. Every list is editable: **+ add** a chip, right-click to remove it.
  - Execution rating ★1–5 and chart screenshots via `Ctrl+V`.
  - One note per trade with Obsidian properties (frontmatter), saved to `Trades/YYYY-MM/`.
  - Auto-generated **📊 Trade journal** note: today / week / month / all-time stats, results by day, by setup, by mistake and by emotion. No plugins required.
  - Today's PnL and win rate in the window header, plus an **anti-tilt warning** after 3 losses in a row.
- Language picker as the first step of the first-run wizard (defaults to the Windows language).
- `build_release.py` builds both installers in one go.
- GitHub Actions workflow that runs the test suite on every push.

### Changed
- The first-run wizard is now fully translated (it was English-only before).
- Changing the language in Settings also updates the trade window.
- Tests moved to `tests/`.
- License changed to **MIT**.

### Fixed
- Reinstalling or updating no longer wipes `templates.json`, recordings and journal chip lists. Before, only `config.json` was kept.
- `install.bat` no longer deletes your settings when copying a new build over an old one.
- The installer closes a running CtrlNote before replacing its files.

## [1.2.0] — 2026-08-06

### Added
- English / Russian UI with a language switch in Settings.
- Visual Markdown in the editor: **bold** / *italic* as you type (`Ctrl+B` / `Ctrl+I`), lists continue on `Enter`.
- Offline voice input with local Whisper. The voice language is set separately from the UI language.
- Paste a screenshot into the drawing canvas as a background.

## [1.1.2] — 2026-08-06

### Fixed
- Edge cases in vault paths, API key encryption and the installer.
- Faster startup: heavy UI is loaded after the first frame.

## [1.1.1] — 2026-08-06

### Security
- Notes and attachments can never be written outside the selected vault.
- The OpenAI API key is encrypted with Windows DPAPI. It is never stored as plain text.

## [1.1.0] — 2026-08-06

### Added
- Drawing window (pen, eraser, shapes, fill) that inserts a PNG into the note.
- Android MVP: a quick-settings tile and a capture screen.
- Landing page on GitHub Pages.

## [1.0.0] — 2026-08-03

### Added
- First release: a Windows tray app with a global hotkey (`Ctrl+Alt+N`) that saves quick notes into an Obsidian vault.
- Folder picker, auto-folder from the active window, templates, image paste, daily note links.
- `CtrlNote-Setup.exe` installer.

[1.3.0]: https://github.com/emaling85/CtrlNote/releases/tag/v1.3.0
[1.2.0]: https://github.com/emaling85/CtrlNote/releases/tag/v1.2.0
[1.1.2]: https://github.com/emaling85/CtrlNote/releases/tag/v1.1.2
