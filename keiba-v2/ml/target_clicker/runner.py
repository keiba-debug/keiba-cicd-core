#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""フル自動投票オーケストレータ (Session 128 で selective 統合)

CLI 一発で:
  1. 買い目仕様 (CLI / JSON / 日付) を FF CSV 書き出し
  2. TARGET メニュー「ファイル → 買い目取り込み」 → 最新 FF CSV を選択
  3. TARGET メニュー「IPAT 連動投票」 → 投票内容確認ダイアログ (多段 fallback)
  4. target_clicker.click_vote_button() で [投票] + [OK] click

設計: docs/auto-purchase/16_TARGET_AUTOCLICK.md §7-8

Usage:
  # 単発: 単勝1点
  python -m ml.target_clicker.runner \\
      --bet 2026052404010301:tansho:5:100 \\
      --confirm

  # 複数件: --bet を複数指定
  python -m ml.target_clicker.runner \\
      --bet 2026052404010301:tansho:5:100 \\
      --bet 2026052404010301:umaren:5/7:200 \\
      --confirm

  # selective_bets.json から一括 (今日の開催)
  python -m ml.target_clicker.runner \\
      --from-date today --amount 100 --confirm

  # 特定日の selective を投票
  python -m ml.target_clicker.runner \\
      --from-date 2026-05-31 --amount 100 --confirm

  # 上限明示 (auto を使わない)
  python -m ml.target_clicker.runner \\
      --from-date today --amount 100 \\
      --max-yen 1000 --max-bets 7 --confirm

注意:
  - --max-yen / --max-bets はデフォルト auto (bets[] 合計と件数で自動設定)
  - bankroll config.json (limit_mode=absolute) の per_day_max_yen を超えると abort
  - --no-bankroll-check で skip 可能だが推奨しない
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date as date_cls, datetime, timedelta
from pathlib import Path
from typing import Optional

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from ml.target_clicker.auto_vote import click_vote_button
from ml.target_clicker.ff_writer import FfBet, BET_TYPE_CODE, parse_bet_spec, write_ff_csv
from ml.target_clicker.selective_loader import SchemaError, load_selective_bets


BANKROLL_CONFIG_PATH = Path(
    os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")
) / "userdata" / "bankroll" / "config.json"


def selective_bets_path_for_date(d: date_cls) -> Path:
    """data3/races/{yyyy}/{mm}/{dd}/selective_bets.json を返す"""
    root = Path(os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3"))
    return root / "races" / f"{d.year:04d}" / f"{d.month:02d}" / f"{d.day:02d}" / "selective_bets.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--bet", action="append", default=[],
                   help="買い目仕様 race_id:bet_type:horses:amount (複数指定可)")
    p.add_argument("--from-json", type=Path, default=None,
                   help="selective_bets.json のような JSON から一括読み込み")
    p.add_argument("--from-date", default=None,
                   help="YYYY-MM-DD または 'today': data3/races/yyyy/mm/dd/selective_bets.json を自動解決")
    p.add_argument("--amount", type=int, default=100,
                   help="--from-json/--from-date 時の 1 件あたり金額 (default=100)")

    p.add_argument("--confirm", action="store_true",
                   help="実 click (なければ FF CSV 出力だけして click は dry-run)")
    p.add_argument("--max-yen", default=None,
                   help="合計金額上限 (default=auto: bets合計*1.0)")
    p.add_argument("--max-bets", default=None,
                   help="ベット数上限 (default=auto: len(bets))")
    p.add_argument("--no-bankroll-check", action="store_true",
                   help="bankroll config.json の per_day_max_yen チェックをスキップ")
    p.add_argument("--dialog-timeout", type=int, default=60,
                   help="投票ダイアログ待機 (default=60)")
    p.add_argument("--no-menu", action="store_true",
                   help="TARGET メニュー操作をスキップ (FF CSV 書き出しだけ。 click もスキップ)")
    p.add_argument("--no-click", action="store_true",
                   help="投票ダイアログ検出と click をスキップ (FF CSV + menu までで止める)")
    p.add_argument("--ipat-strategies", default=None,
                   help="step3_start_ipat の試行順 (カンマ区切り、 default=menu,uia,win32,shortcut,coords)")
    p.add_argument("--auto-launch", action="store_true",
                   help="Session 131+ / 18 Phase 4-A/B: TARGET 起動 + 認証ダイアログ進行 + "
                        "IPAT 連動投票メニュー起動 + 暗証番号入力待ちを実行してから投票に入る")
    p.add_argument("--launch-timeout", type=int, default=30,
                   help="--auto-launch の TARGET 起動タイムアウト (default=30)")
    p.add_argument("--login-timeout", type=int, default=120,
                   help="--auto-launch の IPAT 暗証番号入力待ちタイムアウト (default=120)")
    p.add_argument("--ignore-recent-session-expired", action="store_true",
                   help="シズネ Session 132 修正B / Session 133 実装: --auto-launch 起動時の "
                        "直近1h IPAT_SESSION_EXPIRED_POSTVOTE event チェックを無視して継続する "
                        "(二重投票リスクを承認した上で明示指定)")
    p.add_argument("--session-expired-window-min", type=int, default=60,
                   help="--auto-launch 起動時に IPAT_SESSION_EXPIRED_POSTVOTE event を遡る "
                        "時間窓 (default=60 分)")
    p.add_argument("--no-notify", action="store_true",
                   help="TTS 音声通知を抑制 (Session 129)")
    p.add_argument("--say-test", default=None,
                   help="TTS 単独テスト: 指定テキストを読み上げて即終了 (投票しない)")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def _resolve_from_date(arg: str) -> Path:
    if arg.lower() == "today":
        d = date_cls.today()
    else:
        d = datetime.strptime(arg, "%Y-%m-%d").date()
    p = selective_bets_path_for_date(d)
    if not p.exists():
        raise FileNotFoundError(f"selective_bets.json not found for {d}: {p}")
    return p


def load_bets_from_args(args: argparse.Namespace
                          ) -> tuple[list[FfBet], list[str], dict]:
    """--bet 複数 + --from-json + --from-date をマージして
    (ff_bets, warnings, selective_map) を返す

    selective_map: {(race_id, umaban): SelectiveBetEntry} — ledger 書込みで戦略名取得用

    Session 129:
      - シズネ指摘 J: selective_bets.json は selective_loader で schema 検証
      - ledger v2 配線: selective_map を runner.main へ返す
    """
    bets: list[FfBet] = []
    warnings: list[str] = []
    selective_map: dict = {}  # (race_id, umaban) -> SelectiveBetEntry

    for spec in args.bet:
        bets.append(parse_bet_spec(spec))

    json_paths: list[Path] = []
    if args.from_json:
        json_paths.append(args.from_json)
    if args.from_date:
        json_paths.append(_resolve_from_date(args.from_date))

    for jp in json_paths:
        loaded = load_selective_bets(jp)  # SchemaError 時は abort
        warnings.extend(loaded.warnings)
        for b in loaded.bets:
            # Session 134: bet.amount が schema 由来で入っていればそれを優先
            # (freebudget_kelly_1q source は loader で 100..1000 検証済)
            bet_amount = b.amount if b.amount is not None else args.amount
            bets.append(FfBet(
                race_id=b.race_id,
                bet_type=BET_TYPE_CODE["tansho"],
                umaban=b.umaban,
                amount=bet_amount,
            ))
            selective_map[(b.race_id, b.umaban)] = b
    return bets, warnings, selective_map


def _resolve_max_limit(arg_value, *, auto_fn, kind: str) -> int:
    """--max-yen / --max-bets の auto 解決 (None or 'auto' なら関数で計算)"""
    if arg_value is None or str(arg_value).lower() == "auto":
        v = auto_fn()
        return v
    try:
        return int(arg_value)
    except ValueError:
        raise ValueError(f"--max-{kind} must be int or 'auto', got: {arg_value!r}")


@dataclass
class BankrollLimits:
    """bankroll config.json から読み込んだ絶対額制限"""
    per_day_max_yen: int = 0
    per_race_max_yen: int = 0
    race_overrides: dict = field(default_factory=dict)   # race_id -> {"max_yen": int, "reason": str}
    enabled: bool = False                                # limit_mode == "absolute" のとき True


def _read_bankroll_limits() -> BankrollLimits:
    """bankroll config.json から per_day/per_race + race_overrides を読み込む

    Session 129 (シズネ指摘 I): runner.py が per_race_max_yen を無視していた問題を解消。
    Session 126 で導入した race_overrides も同時参照する。
    """
    if not BANKROLL_CONFIG_PATH.exists():
        return BankrollLimits()
    try:
        with open(BANKROLL_CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        settings = cfg.get("settings", {})
        if settings.get("limit_mode") != "absolute":
            return BankrollLimits()
        return BankrollLimits(
            per_day_max_yen=int(settings.get("per_day_max_yen", 0) or 0),
            per_race_max_yen=int(settings.get("per_race_max_yen", 0) or 0),
            race_overrides=cfg.get("race_overrides", {}) or {},
            enabled=True,
        )
    except Exception as e:
        print(f"[runner] bankroll config 読込エラー (制限なしで続行): {e}", file=sys.stderr)
        return BankrollLimits()


def _check_per_race_limits(bets: list[FfBet], limits: BankrollLimits,
                            verbose: bool = True) -> tuple[bool, list[str]]:
    """レース単位 (race_id groupby) で per_race_max_yen + race_overrides を検証。

    Returns (ok, violations)。 violations が空でなければ abort 対象。
    """
    if not limits.enabled:
        return True, []

    per_race_total: dict[str, int] = {}
    for b in bets:
        per_race_total[b.race_id] = per_race_total.get(b.race_id, 0) + b.amount

    violations: list[str] = []
    for rid, total in per_race_total.items():
        override = limits.race_overrides.get(rid) or {}
        # override.max_yen があればそれを優先、 なければ per_race_max_yen
        max_yen = override.get("max_yen")
        source = "race_override"
        if not isinstance(max_yen, int) or max_yen <= 0:
            max_yen = limits.per_race_max_yen
            source = "per_race_max_yen"
        if max_yen <= 0:
            continue  # 制限なし設定
        if total > max_yen:
            reason = (f" (override reason: {override.get('reason', '?')})"
                       if source == "race_override" else "")
            violations.append(
                f"race_id={rid} 合計 {total}円 > {source}={max_yen}円{reason}"
            )
        elif verbose:
            print(f"[runner]   race {rid}: {total}円 <= {max_yen}円 ({source}) OK")

    return len(violations) == 0, violations


def _check_recent_session_expired_events(
    *,
    window_minutes: int = 60,
    now: Optional[datetime] = None,
) -> list[dict]:
    """直近 window_minutes 以内の IPAT_SESSION_EXPIRED_POSTVOTE event を探す。

    シズネ Session 132 レビュー 🔴-1 修正 B (Session 133 実装):
      `runner.py --auto-launch` の Step 0 冒頭で呼ぶ。 ふくだが直前のセッション切れ
      検知後に `selective_vote.bat` を再叩きしても、 同 bets の二重投票を構造的に防ぐ
      最終層 (= 投票内容確認ダイアログでの max_yen/max_bets 検証より前に止める)。

    events_{YYYY-MM}.jsonl から走査。 月跨ぎ対応で現在月と前月の 2 ファイルを読む
    (月初 0 時付近で 1h 窓が前月にかかるケース)。

    Returns:
        マッチした event の list (新しい順)。 空 list なら問題なし。
    """
    cur = now or datetime.now()
    ledger_dir = Path(os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")) \
        / "userdata" / "purchase_ledger"

    candidates: list[Path] = [
        ledger_dir / f"events_{cur.strftime('%Y-%m')}.jsonl",
    ]
    prev_month_anchor = cur.replace(day=1) - timedelta(days=1)
    prev_path = ledger_dir / f"events_{prev_month_anchor.strftime('%Y-%m')}.jsonl"
    if prev_path != candidates[0]:
        candidates.append(prev_path)

    cutoff = cur - timedelta(minutes=window_minutes)
    matches: list[dict] = []
    for fp in candidates:
        if not fp.exists():
            continue
        try:
            with open(fp, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if ev.get("type") != "IPAT_SESSION_EXPIRED_POSTVOTE":
                        continue
                    at_str = ev.get("at")
                    if not at_str:
                        continue
                    try:
                        ev_at = datetime.fromisoformat(at_str)
                    except ValueError:
                        continue
                    if ev_at >= cutoff:
                        matches.append(ev)
        except Exception as e:
            print(f"[runner] events jsonl 読込警告 ({fp}): {e}", file=sys.stderr)
            continue

    matches.sort(key=lambda e: e.get("at", ""), reverse=True)
    return matches


def main() -> int:
    args = parse_args()
    verbose = not args.quiet

    def vprint(msg: str) -> None:
        if verbose:
            print(msg)

    # --say-test: TTS 単独テスト (投票しない)
    if args.say_test:
        from ml.target_clicker.notify import speak
        ok = speak(args.say_test)
        vprint(f"[say-test] speak() -> {ok}")
        return 0 if ok else 1

    try:
        bets, load_warnings, selective_map = load_bets_from_args(args)
    except SchemaError as e:
        # シズネ指摘 J (Session 129): selective_bets.json 検証失敗 → 投票しない
        print(f"[error] selective_bets.json schema 違反 — 投票 abort: {e}", file=sys.stderr)
        return 6
    if not bets:
        print("[error] no bets specified (--bet ... or --from-json ... or --from-date ...)",
              file=sys.stderr)
        return 2

    for w in load_warnings:
        print(f"[warning] {w}", file=sys.stderr)

    total_yen = sum(b.amount for b in bets)
    n_bets = len(bets)

    # max-yen / max-bets の auto 解決
    max_yen = _resolve_max_limit(args.max_yen, auto_fn=lambda: total_yen, kind="yen")
    max_bets = _resolve_max_limit(args.max_bets, auto_fn=lambda: n_bets, kind="bets")

    vprint(f"[runner] {n_bets} bets prepared, total={total_yen}円")
    vprint(f"[runner] limits: max_yen={max_yen} max_bets={max_bets}")
    for b in bets:
        vprint(f"  - {b}")

    # bankroll check (per_day_max_yen + per_race_max_yen + race_overrides)
    # シズネ指摘 I (Session 129): per_race_max_yen を runner が無視していた問題を解消
    if not args.no_bankroll_check:
        limits = _read_bankroll_limits()
        if limits.enabled:
            # 日単位
            if limits.per_day_max_yen > 0 and total_yen > limits.per_day_max_yen:
                print(f"[error] total={total_yen}円 > bankroll per_day_max_yen="
                      f"{limits.per_day_max_yen}円 — abort", file=sys.stderr)
                print("  --no-bankroll-check で skip 可能だが本当に妥当か確認のこと",
                      file=sys.stderr)
                return 5
            if limits.per_day_max_yen > 0:
                vprint(f"[runner] bankroll day check: OK ({total_yen} <= "
                       f"{limits.per_day_max_yen})")
            # レース単位
            race_ok, race_violations = _check_per_race_limits(bets, limits, verbose=verbose)
            if not race_ok:
                print(f"[error] per_race_max_yen 違反 ({len(race_violations)} レース) — abort",
                      file=sys.stderr)
                for v in race_violations:
                    print(f"  - {v}", file=sys.stderr)
                return 5
        else:
            vprint(f"[runner] bankroll limits: 無効 (limit_mode != absolute)")

    # Step 0 (Session 131+ / 18 Phase 4-A/B/C-min): --auto-launch で TARGET 起動 → IPAT ログインまで
    if args.auto_launch:
        # ★ シズネ Session 132 レビュー 🔴-1 修正B (Session 133 実装):
        #   起動前に直近 window_min 以内の IPAT_SESSION_EXPIRED_POSTVOTE event を探す。
        #   見つかれば二重投票防止のため abort (--ignore-recent-session-expired で承認可)。
        #   `recover-session` CLI 単独実行後にふくだが `selective_vote.bat` を再叩き
        #   した場合、 同 bets[] の二重投票が起こるリスクを構造的に潰す。
        recent_expired = _check_recent_session_expired_events(
            window_minutes=args.session_expired_window_min,
        )
        if recent_expired and not args.ignore_recent_session_expired:
            most_recent = recent_expired[0]
            print(f"\n[runner] ★ 直近 {args.session_expired_window_min} 分以内に "
                  f"IPAT_SESSION_EXPIRED_POSTVOTE event を {len(recent_expired)} 件検出",
                  file=sys.stderr)
            for ev in recent_expired[:5]:
                payload = ev.get("payload", {}) or {}
                print(f"  - {ev.get('at')} race_id={ev.get('race_id')} "
                      f"phase={payload.get('detected_phase')} "
                      f"vote_already_clicked={payload.get('vote_already_clicked')}",
                      file=sys.stderr)
            print("[runner] 二重投票防止のため abort します。 ledger と IPAT 履歴を照合してから、 "
                  "意図的に継続する場合は --ignore-recent-session-expired を指定してください。",
                  file=sys.stderr)
            if not args.no_notify:
                try:
                    from ml.target_clicker.notify import (
                        notify_recent_session_expired_warning,
                    )
                    notify_recent_session_expired_warning(
                        count=len(recent_expired),
                        most_recent_at=most_recent.get("at"),
                        window_minutes=args.session_expired_window_min,
                    )
                except Exception as e:
                    print(f"[notify] notify_recent_session_expired_warning failed: {e}",
                          file=sys.stderr)
            return 8  # 新規 exit code: safety gate (7=launch failure)
        if recent_expired and args.ignore_recent_session_expired:
            # 明示無視 = ふくだ承認済。 stderr に履歴出力で監査記録
            print(f"\n[runner] ⚠ --ignore-recent-session-expired 指定: "
                  f"直近 {args.session_expired_window_min} 分以内の "
                  f"SESSION_EXPIRED event {len(recent_expired)} 件を意図的に無視して継続",
                  file=sys.stderr)
            for ev in recent_expired[:5]:
                print(f"  - 無視対象 {ev.get('at')} race_id={ev.get('race_id')}",
                      file=sys.stderr)

        try:
            from ml.target_clicker import launcher
            from ml.target_clicker.notify import (
                notify_launch_failure,
                notify_launch_ready,
                notify_ipat_login_complete,
                notify_daily_plan_summary,
            )
        except Exception as e:
            print(f"[runner] launcher import failed: {type(e).__name__}: {e}",
                  file=sys.stderr)
            return 7

        vprint("\n[runner] --auto-launch: TARGET 起動シーケンス開始")
        launch_res = launcher.launch_target(
            timeout_sec=args.launch_timeout,
            verbose=verbose,
        )
        if not launch_res.success:
            print(f"[runner] TARGET 起動失敗: {launch_res.reason}", file=sys.stderr)
            if not args.no_notify:
                try:
                    notify_launch_failure(reason=launch_res.reason)
                except Exception as e:
                    print(f"[notify] notify_launch_failure failed: {e}", file=sys.stderr)
            # シズネ 🔴 B: whitelist 外 dialog の場合は ledger event 記録
            if launch_res.action == "dialog_unknown":
                try:
                    from ml.purchase_ledger.writer import _record_failure_event
                    unique_races = list({b.race_id for b in bets})
                    for rid in unique_races:
                        _record_failure_event(
                            event_type="TARGET_DIALOG_UNKNOWN",
                            race_id=rid,
                            payload={
                                "by": "target_clicker.launcher.auto_dismiss_dialogs",
                                "unknown_dialogs": launch_res.unknown_dialogs,
                                "version_mismatch": launch_res.version_mismatch,
                            },
                        )
                except Exception as e:
                    print(f"[ledger] TARGET_DIALOG_UNKNOWN 記録失敗: {e}",
                          file=sys.stderr)
            return 7
        vprint(f"[runner] TARGET 起動: {launch_res.action} "
               f"({launch_res.elapsed_sec:.1f}s, "
               f"dismissed={len(launch_res.dialogs_dismissed)}, "
               f"unknown={len(launch_res.unknown_dialogs)})")
        if launch_res.version_mismatch and verbose:
            print(f"[runner] ⚠ target_version mismatch: "
                  f"actual={launch_res.version_mismatch!r}")
        if not args.no_notify:
            try:
                notify_launch_ready(
                    dialogs_dismissed=len(launch_res.dialogs_dismissed),
                )
            except Exception as e:
                print(f"[notify] notify_launch_ready failed: {e}", file=sys.stderr)

        # IPAT 連動投票メニューを起動 (Phase 4-B)
        vprint("[runner] --auto-launch: IPAT 連動投票メニュー起動")
        if not launcher.open_ipat_menu(verbose=verbose):
            print("[runner] open_ipat_menu failed (Phase 4-B)", file=sys.stderr)
            return 7

        # ログイン画面検出 (Phase 4-C)
        vprint("[runner] --auto-launch: IPAT ログイン画面の出現を待機")
        if not launcher.wait_ipat_login_ready(timeout_sec=args.login_timeout,
                                                verbose=verbose):
            print("[runner] wait_ipat_login_ready timeout", file=sys.stderr)
            return 7

        # シズネ 🔴 A (二重認証ゲート): 暗証番号入力 **前** に当日プランを音声で読み上げ。
        # ふくだは「これを聞いて違和感がなければ暗証番号を入力」 = 暗証番号入力が
        # ① IPAT ログイン認証 ② 当日プラン内容承認 の二重認証として機能する。
        bets_summary: list[dict] = []
        for b in bets:
            entry = selective_map.get((b.race_id, b.umaban))
            row: dict = {"race_id": b.race_id, "umaban": b.umaban}
            # Session 134 🔴-2: freebudget 経路は不均等案分なので金額を音声に乗せる。
            # FfBet.amount は selective.amount があれば優先、 なければ --amount フォールバック済。
            row["amount"] = b.amount
            if entry:
                if entry.venue_name:
                    row["venue_name"] = entry.venue_name
                if entry.race_number:
                    row["race_number"] = entry.race_number
                if entry.horse_name:
                    row["horse_name"] = entry.horse_name
            bets_summary.append(row)
        if not args.no_notify:
            try:
                plan_outcome = notify_daily_plan_summary(
                    bets_summary=bets_summary, total_yen=total_yen,
                )
                vprint(f"[notify] daily plan: {plan_outcome.text}")
            except Exception as e:
                print(f"[notify] notify_daily_plan_summary failed: {e}",
                      file=sys.stderr)
        vprint("[runner] --auto-launch: IPAT 暗証番号入力をお待ちしています...")
        if not launcher.wait_ipat_main_ready(timeout_sec=args.login_timeout,
                                              verbose=verbose):
            print("[runner] wait_ipat_main_ready timeout", file=sys.stderr)
            return 7

        # Phase 4-C-min (シズネ 🔴 D): pre-flight セッション検証
        # 「投票したつもりが全部失敗していた」 経路を塞ぐため、 selective_vote.bat
        # 走り出し前にセッション有効性を確認する。 NG なら abort + 音声 + ledger 記録。
        vprint("[runner] --auto-launch: IPAT セッション pre-flight 検証")
        precheck_ok, precheck_reason = launcher.precheck_ipat_session(verbose=verbose)
        if not precheck_ok:
            print(f"[runner] IPAT セッション pre-check 失敗: {precheck_reason} — abort",
                  file=sys.stderr)
            if not args.no_notify:
                try:
                    from ml.target_clicker.notify import notify_ipat_session_expired
                    notify_ipat_session_expired()
                except Exception as e:
                    print(f"[notify] notify_ipat_session_expired failed: {e}",
                          file=sys.stderr)
            try:
                from ml.purchase_ledger.writer import _record_failure_event
                unique_races = list({b.race_id for b in bets})
                for rid in unique_races:
                    _record_failure_event(
                        event_type="IPAT_SESSION_EXPIRED",
                        race_id=rid,
                        payload={
                            "by": "target_clicker.launcher.precheck_ipat_session",
                            "stage": "pre-flight",
                            "reason": precheck_reason,
                            "attempted_total_yen": total_yen,
                        },
                    )
            except Exception as e:
                print(f"[ledger] IPAT_SESSION_EXPIRED 記録失敗: {e}", file=sys.stderr)
            return 7

        if not args.no_notify:
            try:
                notify_ipat_login_complete()
            except Exception as e:
                print(f"[notify] notify_ipat_login_complete failed: {e}", file=sys.stderr)
        vprint("[runner] --auto-launch: IPAT 認証完了、 投票開始")

    # Step 1: FF CSV 書き出し
    try:
        ff_path = write_ff_csv(bets)
    except Exception as e:
        print(f"[runner] FF CSV write failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 3
    vprint(f"[runner] FF CSV written: {ff_path}")

    # Step 2: TARGET メニュー操作
    if not args.no_menu:
        try:
            from ml.target_clicker import menu_runner
            ipat_strategies_list = (args.ipat_strategies.split(",")
                                     if args.ipat_strategies else None)
            # step1 (CSV 取込) → step3 (IPAT 起動) の順 (取込確定は投票後)
            if not menu_runner.step1_open_csv_select(ff_path, verbose=verbose):
                print("[runner] step1 (CSV 選択) failed", file=sys.stderr)
                return 4
            if not menu_runner.step3_start_ipat(verbose=verbose,
                                                 strategies=ipat_strategies_list):
                # Session 130 / シズネ N: 全戦略失敗時に音声警告 + ledger 記録
                msg = ("[runner] step3 (IPAT 起動) failed — "
                       "投票内容確認ダイアログまで TARGET で手動進行してください")
                print(msg, file=sys.stderr)
                if not args.no_notify:
                    try:
                        from ml.target_clicker.notify import notify_ipat_start_failure
                        outcome = notify_ipat_start_failure(
                            strategies_tried=(ipat_strategies_list or
                                               ["menu", "uia", "win32", "shortcut", "coords"]),
                        )
                        vprint(f"[notify] IPAT_START_FAILED spoken={outcome.spoken}")
                    except Exception as e:
                        print(f"[notify] notify_ipat_start_failure failed: {e}",
                              file=sys.stderr)
                try:
                    from ml.purchase_ledger.writer import record_ipat_start_failure
                    unique_races = list({b.race_id for b in bets})
                    record_ipat_start_failure(
                        race_ids=unique_races,
                        reason="step3_start_ipat: 全戦略失敗",
                        strategies_tried=(ipat_strategies_list or
                                           ["menu", "uia", "win32", "shortcut", "coords"]),
                        attempted_total_yen=total_yen,
                    )
                except Exception as e:
                    print(f"[ledger] IPAT_START_FAILED 記録失敗: {e}", file=sys.stderr)
                # IPAT 起動失敗 → click も無理。 ここで返す
                return 4
        except Exception as e:
            print(f"[runner] menu operation failed: {type(e).__name__}: {e}", file=sys.stderr)
            return 4

    # --no-menu の場合は click も飛ばす (menu スキップ = TARGET 操作なし = dialog 出ない)
    skip_click = args.no_click or args.no_menu
    if skip_click:
        vprint("[runner] --no-click / --no-menu のため投票ダイアログ click はスキップ")
        return 0

    # Step 3: 投票ダイアログ → click + OK
    # Session 132 (Phase 4-C-full): bets の race_id を click_vote_button に渡す
    # (1 dialog = 全 bets 一括 = 同 race_id がほとんど。 異なる race_id があれば最初を採用)
    primary_race_id = bets[0].race_id if bets else None
    result = click_vote_button(
        confirm=args.confirm,
        max_yen=max_yen,
        max_bets=max_bets,
        timeout_sec=args.dialog_timeout,
        verbose=verbose,
        notify=not args.no_notify,
        race_id=primary_race_id,
    )

    vprint(f"\n[result] success={result.success} action={result.action}")
    if result.content:
        vprint(f"  total={result.content.total_yen}円 bets={result.content.n_bets} "
               f"limit={result.content.limit_yen}円")
    if result.receipt:
        vprint(f"  受付番号={result.receipt.receipt_number} 時刻={result.receipt.receipt_time}")

    # Session 132 (Phase 4-C-full): session_expired を事後検知したら専用 exit code で abort
    # 自動リトライはしない (= 設計書 §1.3 範囲外: 「投票 click 実行済の場合 二重投票リスク」)
    # ふくだは ledger event IPAT_SESSION_EXPIRED_POSTVOTE を見て、 必要なら
    # `python -m ml.target_clicker.launcher recover-session` を手動で叩く運用。
    if result.session_expired:
        vprint(f"\n[runner] ★ IPAT セッション切れを事後検知 (phase={result.session_expired_phase})")
        vprint(f"  detected_title={result.session_expired_title!r}")
        vprint(f"  keyword={result.session_expired_keyword!r}")
        vprint(f"  → 自動リトライは行いません (二重投票リスク回避)")
        vprint(f"  → 復旧する場合は: python -m ml.target_clicker.launcher recover-session")
        from ml.target_clicker.auto_vote import VOTE_ALREADY_CLICKED_PHASES
        if result.session_expired_phase in VOTE_ALREADY_CLICKED_PHASES:
            vprint(f"  ★ vote click は実行済 — IPAT 残高/履歴を手動で照合してください")
        return 5

    # Step 4 (投票成功時のみ): TARGET 買い目データに保存
    #   投票後の「買い目一括処理」 ウィンドウ から OK F10 + 「はい」
    # Session 130 / シズネ M: 失敗時は音声警告 + ledger に TARGET_SAVE_FAILED 記録。
    #   rollback は不可能 (IPAT は既に受付済) なので、 ふくだに手動操作を求める方針。
    if result.success and result.action == "clicked" and not args.no_menu:
        vprint("\n[runner] TARGET 買い目データへの保存実行 (OK F10 + はい)")
        save_failed_reason: Optional[str] = None
        save_error_type: Optional[str] = None
        try:
            from ml.target_clicker import menu_runner
            saved = menu_runner.finalize_save_to_target(verbose=verbose)
            if saved:
                vprint("[runner] TARGET 保存: 成功")
            else:
                save_failed_reason = "finalize_save_to_target returned False"
                vprint("[runner] TARGET 保存: 失敗 (手動で OK 押してください)")
        except Exception as e:
            save_failed_reason = f"{type(e).__name__}: {e}"
            save_error_type = type(e).__name__
            vprint(f"[runner] TARGET 保存例外: {save_failed_reason}")

        if save_failed_reason:
            receipt_no = (result.receipt.receipt_number
                          if result.receipt and result.receipt.receipt_number else None)
            receipt_nums = [receipt_no] if receipt_no else []
            if not args.no_notify:
                try:
                    from ml.target_clicker.notify import notify_target_save_failure
                    outcome = notify_target_save_failure(
                        receipt_numbers=receipt_nums,
                        error_type=save_error_type,
                    )
                    vprint(f"[notify] TARGET_SAVE_FAILED spoken={outcome.spoken}")
                except Exception as e:
                    print(f"[notify] notify_target_save_failure failed: {e}",
                          file=sys.stderr)
            try:
                from ml.purchase_ledger.writer import record_target_save_failure
                unique_races = list({b.race_id for b in bets})
                record_target_save_failure(
                    race_ids=unique_races,
                    reason=save_failed_reason,
                    receipt_numbers=receipt_nums,
                    error_type=save_error_type,
                )
            except Exception as e:
                print(f"[ledger] TARGET_SAVE_FAILED 記録失敗: {e}", file=sys.stderr)

    # Step 5 (Session 129): ledger v2 へ追記
    #   - clicked 成功なら 各 ticket を record_tansho_vote
    #   - 失敗 (timeout/rejected/error) は record_vote_failure (race_id 単位で集約は難しいので 1 回)
    try:
        from ml.purchase_ledger.writer import record_tansho_vote, record_vote_failure
        if result.success and result.action == "clicked":
            receipt_no = result.receipt.receipt_number if result.receipt else None
            receipt_tm = result.receipt.receipt_time if result.receipt else None
            recorded = 0
            duplicated = 0
            failed = 0
            for b in bets:
                entry = selective_map.get((b.race_id, b.umaban))
                strategy = (f"selective_v3_{entry.source}" if entry else
                            "manual_cli")
                ledger_res = record_tansho_vote(
                    race_id=b.race_id,
                    umaban=b.umaban,
                    amount=b.amount,
                    strategy_name=strategy,
                    portfolio_strategy=strategy,
                    pattern_label="その他",
                    notes=(f"selective.{entry.source}" if entry else "manual"),
                    ev_at_decision=(entry.win_ev if entry else None),
                    receipt_number=receipt_no,
                    receipt_time=receipt_tm,
                    clicked_at=result.clicked_at,
                )
                if ledger_res.action == "recorded":
                    recorded += 1
                elif ledger_res.action == "duplicate":
                    duplicated += 1
                else:
                    failed += 1
                    print(f"[ledger] 記録失敗 race={b.race_id} umaban={b.umaban}: "
                          f"{ledger_res.reason}", file=sys.stderr)
            vprint(f"[ledger] recorded={recorded} duplicate={duplicated} failed={failed}")
        elif result.action in {"timeout", "rejected", "error"}:
            # 1 dialog click 失敗 = 全 bets が未投票。 race ごとに記録
            seen_races: set[str] = set()
            for b in bets:
                if b.race_id in seen_races:
                    continue
                seen_races.add(b.race_id)
                entry = selective_map.get((b.race_id, b.umaban))
                strategy = (f"selective_v3_{entry.source}" if entry else "manual_cli")
                record_vote_failure(
                    race_id=b.race_id,
                    failure_action=result.action,
                    reason=result.reason,
                    attempted_amount=b.amount,
                    attempted_umaban=b.umaban,
                    strategy_name=strategy,
                )
            vprint(f"[ledger] VOTE_FAILED 記録: {len(seen_races)} レース")
    except Exception as e:
        # ledger 書込み失敗は本体 (audit JSONL) と独立 — 投票自体は成功してるので止めない
        print(f"[ledger] 書込み例外 (audit JSONL は正常): {type(e).__name__}: {e}",
              file=sys.stderr)

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
