"""
Автотесты журнала трейдера: PnL, карточка сделки, статистика, сводка, списки чипов.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock

from PIL import Image

import trade_journal as tj


class NumbersTests(unittest.TestCase):
    def test_parse_number(self) -> None:
        self.assertEqual(tj.parse_number("0,5"), 0.5)
        self.assertEqual(tj.parse_number(" 1 200 "), 1200)
        self.assertEqual(tj.parse_number("0.3 SOL"), 0.3)
        self.assertIsNone(tj.parse_number(""))
        self.assertIsNone(tj.parse_number("abc"))

    def test_parse_mcap(self) -> None:
        self.assertEqual(tj.parse_mcap("120K"), 120_000)
        self.assertEqual(tj.parse_mcap("1.5M"), 1_500_000)
        self.assertEqual(tj.parse_mcap("45к"), 45_000)
        self.assertIsNone(tj.parse_mcap("много"))

    def test_fmt_signed(self) -> None:
        self.assertEqual(tj.fmt_signed(0.083), "+0.083")
        self.assertEqual(tj.fmt_signed(-0.4646), "-0.465")
        self.assertEqual(tj.fmt_signed(0.0), "0")

    def test_looks_like_ca(self) -> None:
        self.assertTrue(tj.looks_like_ca("6a2oxfDhmU7z9JBakhkEScKwp5MNNt2eqNxhXqWtpump"))
        self.assertFalse(tj.looks_like_ca("hello world"))


class TradeTests(unittest.TestCase):
    def make(self, **kw) -> tj.Trade:  # noqa: ANN003
        base = dict(
            result=tj.RESULT_PROFIT, coin="WIF", entry_sol=0.5, exit_sol=0.583, sol_usd=200.0,
            when=datetime(2026, 11, 2, 14, 30),
        )
        base.update(kw)
        return tj.Trade(**base)

    def test_pnl(self) -> None:
        trade = self.make()
        self.assertAlmostEqual(trade.pnl_sol, 0.083)
        self.assertAlmostEqual(trade.pnl_pct, 16.6)
        self.assertAlmostEqual(trade.pnl_usd, 16.6)
        self.assertEqual(tj.pnl_summary(trade), "+0.083 SOL · +$16.60 · +16.6%")

    def test_mcap_multiple(self) -> None:
        self.assertEqual(self.make(mcap_entry="120K", mcap_exit="450K").mcap_multiple, 3.75)

    def test_markdown_has_frontmatter_and_sections(self) -> None:
        trade = self.make(setups=["Нарратив"], mistakes=["Мало держал"], why_in='вход "по точке"', rating=4)
        text = tj.trade_to_markdown(trade, ["shot.png"])
        self.assertTrue(text.startswith("---\ntype: \"trade\"\n"))
        self.assertIn('setup: ["Нарратив"]', text)
        self.assertIn("pnl_sol: 0.083", text)
        self.assertIn("## Почему вошёл\nвход \"по точке\"", text)
        self.assertIn("![[shot.png]]", text)
        self.assertIn("★★★★☆", text)

    def test_filename(self) -> None:
        self.assertEqual(tj.trade_filename(self.make()), "2026-11-02 14-30 WIF +0.083 SOL.md")
        no_numbers = self.make(entry_sol=None, result=tj.RESULT_LOSS, coin="a/b?")
        self.assertEqual(tj.trade_filename(no_numbers), "2026-11-02 14-30 ab минус.md")
        self.assertEqual(tj.trade_filename(no_numbers, "en"), "2026-11-02 14-30 ab loss.md")

    def test_default_folders_follow_language(self) -> None:
        self.assertEqual(tj.trade_folder({}, "en"), "Trades")
        self.assertEqual(tj.attachments_folder({}, "ru"), "Фотки")
        self.assertEqual(tj.trade_folder({"trade_folder": "Мои"}, "en"), "Мои")
        self.assertEqual(tj.dashboard_name("en"), "📊 Trade journal.md")


class SaveAndStatsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def save(self, result: str, entry: float, exit_: float, when: datetime, **kw) -> Path:  # noqa: ANN003
        trade = tj.Trade(result=result, coin="PEPE", entry_sol=entry, exit_sol=exit_, when=when, **kw)
        return tj.save_trade(trade, self.vault, folder="Сделки", attachments_folder="Фотки")

    def test_save_roundtrip_and_dashboard(self) -> None:
        img = Image.new("RGB", (4, 4), "red")
        trade = tj.Trade(
            result=tj.RESULT_PROFIT, coin="WIF", entry_sol=1, exit_sol=1.5, sol_usd=100,
            when=datetime(2026, 11, 2, 10, 0), setups=["Нарратив"], notes="![[a.png]]",
        )
        path = tj.save_trade(trade, self.vault, attachments=[("a.png", img)])
        self.assertEqual(path.parent, self.vault.resolve() / "Сделки" / "2026-11")
        self.assertTrue((self.vault / "Фотки" / "a.png").exists())

        self.save(tj.RESULT_LOSS, 1, 0.8, datetime(2026, 11, 2, 11, 0))
        records = tj.load_trades(self.vault)
        self.assertEqual([r.coin for r in records], ["WIF", "PEPE"])
        stats = tj.compute_stats(records)
        self.assertEqual((stats.trades, stats.wins, stats.losses, stats.winrate), (2, 1, 1, 50))
        self.assertAlmostEqual(stats.pnl_sol, 0.3)

        dashboard = (self.vault / tj.dashboard_name("ru")).read_text(encoding="utf-8")
        self.assertIn("Журнал сделок", dashboard)
        self.assertIn("Нарратив", dashboard)
        self.assertIn("Сделки/2026-11/", dashboard)

    def test_ignores_non_trade_notes(self) -> None:
        folder = self.vault / "Сделки"
        folder.mkdir()
        (folder / "просто заметка.md").write_text("привет", encoding="utf-8")
        self.assertEqual(tj.load_trades(self.vault), [])

    def test_loss_streak_and_today(self) -> None:
        for hour, result in ((9, tj.RESULT_PROFIT), (10, tj.RESULT_LOSS), (11, tj.RESULT_LOSS), (12, tj.RESULT_LOSS)):
            self.save(result, 1, 1.1 if result == tj.RESULT_PROFIT else 0.9, datetime(2026, 11, 2, hour))
        self.save(tj.RESULT_PROFIT, 1, 2, datetime(2026, 11, 1, 9))
        records = tj.load_trades(self.vault)
        today = tj.today_records(records, date(2026, 11, 2))
        self.assertEqual(len(today), 4)
        self.assertEqual(tj.loss_streak(today), 3)
        dashboard = tj.build_dashboard(records, self.vault.resolve(), today=date(2026, 11, 2))
        self.assertIn("3 минуса подряд", dashboard)

    def test_folder_cannot_escape_vault(self) -> None:
        trade = tj.Trade(result=tj.RESULT_BE, coin="X")
        with self.assertRaises(ValueError):
            tj.save_trade(trade, self.vault, folder="../outside")


class OptionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.patcher = mock.patch.object(tj, "TRADE_OPTIONS_PATH", Path(self.tmp.name) / "trade_options.json")
        self.patcher.start()

    def tearDown(self) -> None:
        self.patcher.stop()
        self.tmp.cleanup()

    def test_add_and_remove(self) -> None:
        self.assertIn("Axiom", tj.load_options("ru")["platforms"])
        tj.add_option("setups", "Мой сетап")
        self.assertIn("Мой сетап", tj.load_options("ru")["setups"])
        tj.remove_option("setups", "Мой сетап")
        self.assertNotIn("Мой сетап", tj.load_options("ru")["setups"])


if __name__ == "__main__":
    unittest.main()
