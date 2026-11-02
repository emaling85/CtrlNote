"""
Журнал трейдера: сделка → markdown-карточка в vault + сводный «Журнал сделок».

Здесь только логика (без окон): расчёт PnL, запись файла, чтение старых сделок,
статистика для шапки окна и редактируемые списки чипов (сетапы, эмоции, ошибки).
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib import request

from config import APP_DIR
from note_saver import sanitize_filename, unique_path
from vault_paths import resolve_under_vault, safe_attachment_name

if TYPE_CHECKING:
    from PIL.Image import Image as PilImage


TRADE_OPTIONS_PATH = APP_DIR / "trade_options.json"
DASHBOARD_NAMES = {"ru": "📊 Журнал сделок.md", "en": "📊 Trade journal.md"}
DEFAULT_FOLDERS = {"ru": ("Сделки", "Фотки"), "en": ("Trades", "Screenshots")}

RESULT_PROFIT = "profit"
RESULT_LOSS = "loss"
RESULT_BE = "breakeven"
RESULTS = (RESULT_PROFIT, RESULT_LOSS, RESULT_BE)

# Группы чипов, которые пользователь может дополнять и удалять
OPTION_GROUPS = ("platforms", "risk", "setups", "emotions", "mistakes")

DEFAULT_OPTIONS: dict[str, dict[str, list[str]]] = {
    "ru": {
        "platforms": ["Axiom", "Photon", "GMGN", "BullX", "Trojan"],
        "risk": ["Небольшой", "Средний", "Большой"],
        "setups": ["Нарратив", "New pairs", "Migrated", "Откат", "Бандлы", "Колл KOL", "Объём"],
        "emotions": ["Спокойно", "Уверенность", "Страх", "Жадность", "FOMO", "Тильт", "Скука"],
        "mistakes": [
            "Мало держал",
            "Пересидел",
            "Поздний вход",
            "Без стопа",
            "Большой размер",
            "Глупость / рандом",
            "Игра вместо торговли",
        ],
    },
    "en": {
        "platforms": ["Axiom", "Photon", "GMGN", "BullX", "Trojan"],
        "risk": ["Small", "Medium", "Large"],
        "setups": ["Narrative", "New pairs", "Migrated", "Dip", "Bundles", "KOL call", "Volume"],
        "emotions": ["Calm", "Confident", "Fear", "Greed", "FOMO", "Tilt", "Boredom"],
        "mistakes": [
            "Sold too early",
            "Held too long",
            "Late entry",
            "No stop",
            "Size too big",
            "Random / dumb",
            "Gambling, not trading",
        ],
    },
}

# Адрес токена Solana (base58, 32–44 символа)
_CA_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_MCAP_RE = re.compile(r"^\s*\$?\s*([0-9]+(?:[.,][0-9]+)?)\s*([kKmMbBкКмМ]?)\s*$")


# ---------------------------------------------------------------- folders


def dashboard_name(lang: str = "ru") -> str:
    return DASHBOARD_NAMES.get(lang, DASHBOARD_NAMES["en"])


def trade_folder(config: dict[str, Any], lang: str = "ru") -> str:
    """Папка сделок из настроек; пусто — по языку (Сделки / Trades)."""
    return str(config.get("trade_folder") or DEFAULT_FOLDERS.get(lang, DEFAULT_FOLDERS["en"])[0])


def attachments_folder(config: dict[str, Any], lang: str = "ru") -> str:
    """Папка скриншотов; пусто — по языку (Фотки / Screenshots)."""
    return str(config.get("trade_attachments_folder") or attachments_folder_default(lang))


def attachments_folder_default(lang: str = "ru") -> str:
    return DEFAULT_FOLDERS.get(lang, DEFAULT_FOLDERS["en"])[1]


# ---------------------------------------------------------------- options


def _default_options(lang: str) -> dict[str, list[str]]:
    base = DEFAULT_OPTIONS.get(lang) or DEFAULT_OPTIONS["en"]
    return {k: list(v) for k, v in base.items()}


def load_options(lang: str = "ru") -> dict[str, list[str]]:
    """Списки чипов из trade_options.json; при первом запуске — значения по умолчанию."""
    options = _default_options(lang)
    if TRADE_OPTIONS_PATH.exists():
        try:
            data = json.loads(TRADE_OPTIONS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        for group in OPTION_GROUPS:
            items = data.get(group)
            if isinstance(items, list):
                options[group] = [str(x).strip() for x in items if str(x).strip()]
    else:
        save_options(options)
    return options


def save_options(options: dict[str, list[str]]) -> None:
    data = {g: list(options.get(g, [])) for g in OPTION_GROUPS}
    tmp = TRADE_OPTIONS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(TRADE_OPTIONS_PATH)


def add_option(group: str, value: str, lang: str = "ru") -> dict[str, list[str]]:
    options = load_options(lang)
    value = value.strip()
    if value and value not in options[group]:
        options[group].append(value)
        save_options(options)
    return options


def remove_option(group: str, value: str, lang: str = "ru") -> dict[str, list[str]]:
    options = load_options(lang)
    if value in options[group]:
        options[group].remove(value)
        save_options(options)
    return options


# ---------------------------------------------------------------- numbers


def parse_number(text: str | float | None) -> float | None:
    """'0,5' / '0.5' / ' 1 200 ' → число; пусто или мусор → None."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    cleaned = str(text).strip().replace(" ", "").replace(" ", "").replace(",", ".")
    cleaned = cleaned.lstrip("$").removesuffix("SOL").removesuffix("sol")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_mcap(text: str | None) -> float | None:
    """'120K' → 120000, '1.5M' → 1500000 (к/м по-русски тоже понимаем)."""
    if not text:
        return None
    match = _MCAP_RE.match(str(text))
    if not match:
        return None
    value = float(match.group(1).replace(",", "."))
    mult = {"k": 1e3, "к": 1e3, "m": 1e6, "м": 1e6, "b": 1e9}.get(match.group(2).lower(), 1)
    return value * mult


def looks_like_ca(text: str) -> bool:
    return bool(_CA_RE.match(text.strip()))


def fmt_signed(value: float, digits: int = 3) -> str:
    """+0.083 / -0.4 — без хвостовых нулей."""
    text = f"{abs(value):.{digits}f}".rstrip("0").rstrip(".") or "0"
    if text == "0":
        return "0"
    return ("+" if value > 0 else "-") + text


# ---------------------------------------------------------------- trade


@dataclass
class Trade:
    result: str
    coin: str
    ca: str = ""
    platform: str = ""
    when: datetime = field(default_factory=datetime.now)
    entry_sol: float | None = None
    exit_sol: float | None = None
    sol_usd: float | None = None
    mcap_entry: str = ""
    mcap_exit: str = ""
    stop: str = ""
    risk: str = ""
    setups: list[str] = field(default_factory=list)
    emotions: list[str] = field(default_factory=list)
    mistakes: list[str] = field(default_factory=list)
    rating: int = 0
    why_in: str = ""
    why_out: str = ""
    notes: str = ""

    @property
    def pnl_sol(self) -> float | None:
        if self.entry_sol is None or self.exit_sol is None:
            return None
        return round(self.exit_sol - self.entry_sol, 6)

    @property
    def pnl_pct(self) -> float | None:
        if self.pnl_sol is None or not self.entry_sol:
            return None
        return round(self.pnl_sol / self.entry_sol * 100, 2)

    @property
    def pnl_usd(self) -> float | None:
        if self.pnl_sol is None or not self.sol_usd:
            return None
        return round(self.pnl_sol * self.sol_usd, 2)

    @property
    def mcap_multiple(self) -> float | None:
        a, b = parse_mcap(self.mcap_entry), parse_mcap(self.mcap_exit)
        if not a or b is None:
            return None
        return round(b / a, 2)


def result_icon(result: str) -> str:
    return {RESULT_PROFIT: "🟢", RESULT_LOSS: "🔴"}.get(result, "⚪")


def pnl_summary(trade: Trade) -> str:
    """'+0.083 SOL · +$15.40 · +16.6%' — для заголовка и шапки окна."""
    parts: list[str] = []
    if trade.pnl_sol is not None:
        parts.append(f"{fmt_signed(trade.pnl_sol)} SOL")
    if trade.pnl_usd is not None:
        sign = "+" if trade.pnl_usd > 0 else "-" if trade.pnl_usd < 0 else ""
        parts.append(f"{sign}${abs(trade.pnl_usd):.2f}")
    if trade.pnl_pct is not None:
        parts.append(f"{fmt_signed(trade.pnl_pct, 1)}%")
    return " · ".join(parts)


def _yaml(value: Any) -> str:
    # JSON — валидный YAML: кавычки и спецсимволы экранируются сами
    return json.dumps(value, ensure_ascii=False)


def trade_to_markdown(trade: Trade, image_names: list[str] | None = None, lang: str = "ru") -> str:
    """Карточка сделки: свойства (frontmatter) для Obsidian + читаемый текст."""
    ru = lang == "ru"
    props: list[tuple[str, Any]] = [
        ("type", "trade"),
        ("date", trade.when.strftime("%Y-%m-%d")),
        ("time", trade.when.strftime("%H:%M")),
        ("result", trade.result),
        ("coin", trade.coin),
        ("ca", trade.ca),
        ("platform", trade.platform),
        ("entry_sol", trade.entry_sol),
        ("exit_sol", trade.exit_sol),
        ("pnl_sol", trade.pnl_sol),
        ("pnl_pct", trade.pnl_pct),
        ("pnl_usd", trade.pnl_usd),
        ("sol_usd", trade.sol_usd),
        ("mcap_entry", trade.mcap_entry),
        ("mcap_exit", trade.mcap_exit),
        ("stop", trade.stop),
        ("risk", trade.risk),
        ("setup", trade.setups),
        ("emotions", trade.emotions),
        ("mistakes", trade.mistakes),
        ("rating", trade.rating or None),
        ("tags", ["trade", trade.result]),
    ]
    lines = ["---"]
    for key, value in props:
        if value in (None, "", []):
            continue
        lines.append(f"{key}: {_yaml(value)}")
    lines.append("---")

    summary = pnl_summary(trade)
    lines.append(f"# {result_icon(trade.result)} {trade.coin}" + (f"  {summary}" if summary else ""))
    lines.append("")

    label = {
        "time": "Время" if ru else "Time",
        "platform": "Платформа" if ru else "Platform",
        "ca": "Контракт" if ru else "Contract",
        "in": "Вход" if ru else "Entry",
        "out": "Выход" if ru else "Exit",
        "mcap": "Капа" if ru else "Mcap",
        "stop": "Стоп" if ru else "Stop",
        "risk": "Риск" if ru else "Risk",
        "setup": "Сетап" if ru else "Setup",
        "rating": "Исполнение" if ru else "Execution",
        "why_in": "Почему вошёл" if ru else "Why I entered",
        "why_out": "Почему вышел" if ru else "Why I exited",
        "mistakes": "Ошибки" if ru else "Mistakes",
        "emotions": "Эмоции" if ru else "Emotions",
        "notes": "Заметки и скрины" if ru else "Notes & screenshots",
    }
    rows: list[tuple[str, str]] = [(label["time"], trade.when.strftime("%Y-%m-%d %H:%M"))]
    if trade.platform:
        rows.append((label["platform"], trade.platform))
    if trade.ca:
        rows.append((label["ca"], f"`{trade.ca}`"))
    if trade.entry_sol is not None:
        rows.append((label["in"], f"{trade.entry_sol:g} SOL"))
    if trade.exit_sol is not None:
        rows.append((label["out"], f"{trade.exit_sol:g} SOL"))
    if trade.mcap_entry or trade.mcap_exit:
        mcap = f"{trade.mcap_entry or '?'} → {trade.mcap_exit or '?'}"
        if trade.mcap_multiple:
            mcap += f" (x{trade.mcap_multiple:g})"
        rows.append((label["mcap"], mcap))
    if trade.stop:
        rows.append((label["stop"], trade.stop))
    if trade.risk:
        rows.append((label["risk"], trade.risk))
    if trade.setups:
        rows.append((label["setup"], ", ".join(trade.setups)))
    if trade.rating:
        rows.append((label["rating"], "★" * trade.rating + "☆" * (5 - trade.rating)))
    lines.append("| | |")
    lines.append("|---|---|")
    for name, value in rows:
        lines.append(f"| {name} | {value.replace('|', '/')} |")

    def section(title: str, body: str) -> None:
        if body.strip():
            lines.extend(["", f"## {title}", body.strip()])

    section(label["why_in"], trade.why_in)
    section(label["why_out"], trade.why_out)
    section(label["mistakes"], ", ".join(trade.mistakes))
    section(label["emotions"], ", ".join(trade.emotions))
    notes = trade.notes.strip()
    images = "\n".join(f"![[{name}]]" for name in image_names or [] if f"![[{name}]]" not in notes)
    section(label["notes"], "\n\n".join(p for p in (notes, images) if p))
    return "\n".join(lines).rstrip() + "\n"


def trade_filename(trade: Trade, lang: str = "ru") -> str:
    stamp = trade.when.strftime("%Y-%m-%d %H-%M")
    coin = sanitize_filename(trade.coin, max_length=40) or "trade"
    tail = f" {fmt_signed(trade.pnl_sol)} SOL" if trade.pnl_sol is not None else ""
    if not tail:
        words = {"ru": (" плюс", " минус", " ноль"), "en": (" win", " loss", " breakeven")}
        win, loss, even = words.get(lang, words["en"])
        tail = {RESULT_PROFIT: win, RESULT_LOSS: loss}.get(trade.result, even)
    return f"{stamp} {coin}{tail}.md"


def save_trade(
    trade: Trade,
    vault_path: str | Path,
    folder: str | None = None,
    attachments_folder: str | None = None,
    attachments: list[tuple[str, "PilImage"]] | None = None,
    lang: str = "ru",
) -> Path:
    """Пишет карточку в <vault>/<folder>/<ГГГГ-ММ>/ и обновляет сводный журнал."""
    vault = Path(vault_path).expanduser().resolve()
    if not vault.is_dir():
        raise FileNotFoundError(f"Vault folder not found: {vault}")

    folder = folder or trade_folder({}, lang)
    if attachments_folder is None:
        attachments_folder = attachments_folder_default(lang)
    month = trade.when.strftime("%Y-%m")
    target_dir = resolve_under_vault(vault, folder, month)
    target_dir.mkdir(parents=True, exist_ok=True)

    image_names: list[str] = []
    if attachments:
        img_dir = resolve_under_vault(vault, attachments_folder) if attachments_folder else target_dir
        img_dir.mkdir(parents=True, exist_ok=True)
        for name, image in attachments:
            path = unique_path(img_dir, safe_attachment_name(name))
            if path.name != name:
                trade.notes = trade.notes.replace(f"![[{name}]]", f"![[{path.name}]]")
            image.save(path, format="PNG")
            image_names.append(path.name)

    path = unique_path(target_dir, trade_filename(trade, lang))
    path.write_text(trade_to_markdown(trade, image_names, lang), encoding="utf-8")

    try:
        write_dashboard(vault, folder, lang)
    except OSError:
        pass  # сводка — приятный бонус, сама сделка уже сохранена
    return path


# ---------------------------------------------------------------- reading & stats


@dataclass
class TradeRecord:
    path: Path
    date: str
    time: str
    result: str
    coin: str
    pnl_sol: float | None
    pnl_usd: float | None
    setups: list[str]
    emotions: list[str]
    mistakes: list[str]
    rating: int


def read_frontmatter(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    data: dict[str, Any] = {}
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        key, sep, raw = line.partition(":")
        if not sep:
            continue
        raw = raw.strip()
        try:
            data[key.strip()] = json.loads(raw)
        except json.JSONDecodeError:
            data[key.strip()] = raw.strip("'\"")
    return data


def load_trades(vault_path: str | Path, folder: str | None = None, lang: str = "ru") -> list[TradeRecord]:
    """Все сделки из папки журнала, от старых к новым."""
    try:
        root = resolve_under_vault(vault_path, folder or trade_folder({}, lang))
    except ValueError:
        return []
    if not root.is_dir():
        return []
    records: list[TradeRecord] = []
    for path in root.rglob("*.md"):
        meta = read_frontmatter(path)
        if meta.get("type") != "trade":
            continue

        def as_list(value: Any) -> list[str]:
            return [str(v) for v in value] if isinstance(value, list) else []

        records.append(
            TradeRecord(
                path=path,
                date=str(meta.get("date", "")),
                time=str(meta.get("time", "")),
                result=str(meta.get("result", "")),
                coin=str(meta.get("coin", path.stem)),
                pnl_sol=parse_number(meta.get("pnl_sol")),
                pnl_usd=parse_number(meta.get("pnl_usd")),
                setups=as_list(meta.get("setup")),
                emotions=as_list(meta.get("emotions")),
                mistakes=as_list(meta.get("mistakes")),
                rating=int(parse_number(meta.get("rating")) or 0),
            )
        )
    records.sort(key=lambda r: (r.date, r.time, r.path.name))
    return records


@dataclass
class Stats:
    trades: int = 0
    wins: int = 0
    losses: int = 0
    pnl_sol: float = 0.0
    pnl_usd: float = 0.0

    @property
    def winrate(self) -> float | None:
        decided = self.wins + self.losses
        return round(self.wins / decided * 100) if decided else None


def compute_stats(records: list[TradeRecord]) -> Stats:
    stats = Stats(trades=len(records))
    for r in records:
        stats.wins += r.result == RESULT_PROFIT
        stats.losses += r.result == RESULT_LOSS
        stats.pnl_sol += r.pnl_sol or 0.0
        stats.pnl_usd += r.pnl_usd or 0.0
    stats.pnl_sol = round(stats.pnl_sol, 6)
    stats.pnl_usd = round(stats.pnl_usd, 2)
    return stats


def loss_streak(records: list[TradeRecord]) -> int:
    """Сколько последних сделок подряд закрыты в минус (для анти-тильта)."""
    streak = 0
    for r in reversed(records):
        if r.result != RESULT_LOSS:
            break
        streak += 1
    return streak


def today_records(records: list[TradeRecord], today: date | None = None) -> list[TradeRecord]:
    day = (today or date.today()).isoformat()
    return [r for r in records if r.date == day]


# ---------------------------------------------------------------- dashboard


def _money(sol: float, usd: float) -> str:
    text = f"{fmt_signed(sol)} SOL"
    if usd:
        text += f" ({'+' if usd > 0 else '-'}${abs(usd):.2f})"
    return text


def build_dashboard(records: list[TradeRecord], vault: Path, lang: str = "ru", today: date | None = None) -> str:
    """Сводка без плагинов: итоги, дни, сетапы, ошибки, последние сделки."""
    ru = lang == "ru"
    today = today or date.today()
    lines = [
        "# 📊 " + ("Журнал сделок" if ru else "Trade journal"),
        "",
        ("> Обновляется автоматически CtrlNote при каждой сделке (Ctrl+Alt+T). Не редактируй вручную."
         if ru else "> Auto-updated by CtrlNote on every trade (Ctrl+Alt+T). Do not edit by hand."),
        "",
    ]

    def stat_line(title: str, recs: list[TradeRecord]) -> str:
        s = compute_stats(recs)
        wr = f"{s.winrate}%" if s.winrate is not None else "—"
        return f"| {title} | {s.trades} | {wr} | {_money(s.pnl_sol, s.pnl_usd) if s.trades else '—'} |"

    week_start = (today - timedelta(days=today.weekday())).isoformat()
    month = today.strftime("%Y-%m")
    lines += [
        "| " + (" | Сделок | Винрейт | PnL |" if ru else " | Trades | Win rate | PnL |"),
        "|---|---|---|---|",
        stat_line("Сегодня" if ru else "Today", [r for r in records if r.date == today.isoformat()]),
        stat_line("Неделя" if ru else "Week", [r for r in records if r.date >= week_start]),
        stat_line("Месяц" if ru else "Month", [r for r in records if r.date.startswith(month)]),
        stat_line("Всё время" if ru else "All time", records),
        "",
    ]

    streak = loss_streak(records)
    if streak >= 3:
        lines += [
            f"> [!danger] {streak} " + ("минуса подряд — сделай паузу." if ru else "losses in a row — take a break."),
            "",
        ]

    # По дням (последние 14)
    days: dict[str, list[TradeRecord]] = {}
    for r in records:
        days.setdefault(r.date, []).append(r)
    if days:
        lines += ["## " + ("По дням" if ru else "By day"), "",
                  "| " + ("День | Сделок | Винрейт | PnL |" if ru else "Day | Trades | Win rate | PnL |"),
                  "|---|---|---|---|"]
        for day in sorted(days, reverse=True)[:14]:
            lines.append(stat_line(day, days[day]))
        lines.append("")

    def breakdown(title: str, attr: str) -> None:
        groups: dict[str, list[TradeRecord]] = {}
        for r in records:
            for item in getattr(r, attr):
                groups.setdefault(item, []).append(r)
        if not groups:
            return
        lines.extend(["## " + title, "",
                      "| | " + ("Сделок | Винрейт | PnL |" if ru else "Trades | Win rate | PnL |"),
                      "|---|---|---|---|"])
        for name, recs in sorted(groups.items(), key=lambda kv: compute_stats(kv[1]).pnl_sol, reverse=True):
            lines.append(stat_line(name, recs))
        lines.append("")

    breakdown("Сетапы" if ru else "Setups", "setups")
    breakdown("Ошибки — сколько стоят" if ru else "Mistakes — what they cost", "mistakes")
    breakdown("Эмоции" if ru else "Emotions", "emotions")

    if records:
        lines += ["## " + ("Последние сделки" if ru else "Recent trades"), "",
                  "| " + ("Когда | Монета | PnL | Сетап |" if ru else "When | Coin | PnL | Setup |"),
                  "|---|---|---|---|"]
        for r in list(reversed(records))[:30]:
            rel = r.path.relative_to(vault).with_suffix("").as_posix()
            coin = r.coin.replace("|", "/").replace("]", "")
            pnl = _money(r.pnl_sol, r.pnl_usd or 0) if r.pnl_sol is not None else result_icon(r.result)
            lines.append(
                f"| {r.date} {r.time} | {result_icon(r.result)} [[{rel}\\|{coin}]] | {pnl} | {', '.join(r.setups)} |"
            )
        lines.append("")
    return "\n".join(lines)


def write_dashboard(vault_path: str | Path, folder: str | None = None, lang: str = "ru") -> Path:
    vault = Path(vault_path).expanduser().resolve()
    path = vault / dashboard_name(lang)
    path.write_text(build_dashboard(load_trades(vault, folder, lang), vault, lang), encoding="utf-8")
    return path


# ---------------------------------------------------------------- SOL price


def fetch_sol_usd(timeout: float = 4.0) -> float | None:
    """Текущий курс SOL в $ (Binance, запасной — CoinGecko). Без сети → None."""
    sources = (
        ("https://api.binance.com/api/v3/ticker/price?symbol=SOLUSDT", lambda d: d["price"]),
        ("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd", lambda d: d["solana"]["usd"]),
    )
    for url, pick in sources:
        try:
            req = request.Request(url, headers={"User-Agent": "CtrlNote"})
            with request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
                price = float(pick(json.loads(resp.read().decode("utf-8"))))
            if price > 0:
                return round(price, 2)
        except Exception:  # noqa: BLE001
            continue
    return None


def fetch_sol_usd_async(callback) -> None:  # noqa: ANN001
    threading.Thread(target=lambda: callback(fetch_sol_usd()), name="CtrlNoteSolPrice", daemon=True).start()
