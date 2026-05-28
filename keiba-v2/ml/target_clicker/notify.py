#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""投票後 TTS 通知レイヤ (Session 129)

設計: docs/auto-purchase/17_NOTIFICATION_LAYER.md

責務:
  - ClickResult を人間向け日本語文面に整形
  - TTS で読み上げ (pyttsx3 → PowerShell SAPI の 2 段フォールバック)
  - 失敗しても本体投票フローは止めない (best-effort)

使用例:
  from ml.target_clicker.notify import notify_vote_result, speak
  notify_vote_result(result)              # ClickResult から自動文面生成
  speak("受付番号 ゼロ ゼロ 四 五。 投票完了")  # 任意テキスト
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ml.target_clicker.auto_vote import ClickResult


# ============================================================
# 数字読み正規化
# ============================================================

_DIGIT_KANA = {
    "0": "ゼロ",
    "1": "いち",
    "2": "に",
    "3": "さん",
    "4": "よん",
    "5": "ご",
    "6": "ろく",
    "7": "なな",
    "8": "はち",
    "9": "きゅう",
}


def format_receipt_number_kana(n: str | int | None) -> str:
    """受付番号 (4 桁) を 1 桁ずつ読みに変換。
    '0045' → 'ゼロ ゼロ 四 五'

    SAPI 既定だと 0045 を「ゼロゼロよんじゅうご」と読んでしまうので、
    1 桁ずつひらがな + 空白区切りで強制的に分離。
    """
    if n is None:
        return "不明"
    s = str(n).strip()
    if not s:
        return "不明"
    return " ".join(_DIGIT_KANA.get(c, c) for c in s)


def format_yen(yen: int | None) -> str:
    """金額を SAPI で読みやすい表記に。 1000 → '千円', 3500 → '三千五百円'。

    SAPI 既定読みに任せるが、 None / 0 / 負値はエラーメッセージにする。
    """
    if yen is None:
        return "金額不明"
    if yen <= 0:
        return "ゼロ円"
    # SAPI は半角数字+「円」 を自然に読む (「いっせん」 ではなく「せん」 になる場合あり)
    return f"{yen}円"


# ============================================================
# TTS バックエンド (3 段フォールバック)
# ============================================================

_PYTTSX3_TRIED = False
_PYTTSX3_AVAILABLE = False


def _try_pyttsx3(text: str, rate: int = 0) -> bool:
    """試行 1: pyttsx3 が import できるなら使う"""
    global _PYTTSX3_TRIED, _PYTTSX3_AVAILABLE
    try:
        import pyttsx3
        _PYTTSX3_AVAILABLE = True
    except Exception:
        _PYTTSX3_TRIED = True
        return False
    _PYTTSX3_TRIED = True

    try:
        eng = pyttsx3.init()
        # 日本語 voice 選択
        for v in eng.getProperty("voices"):
            name = (v.name or "") + " " + (v.id or "")
            if "Haruka" in name or "ja-JP" in name or "Japan" in name:
                eng.setProperty("voice", v.id)
                break
        if rate:
            cur = eng.getProperty("rate")
            eng.setProperty("rate", cur + rate * 20)
        eng.say(text)
        eng.runAndWait()
        return True
    except Exception as e:
        print(f"[notify] pyttsx3 failed: {type(e).__name__}: {e}", file=sys.stderr)
        return False


# PowerShell SAPI 用テンプレート — ja-JP voice を優先選択して Speak()
# {rate} は -10..10、 {text_json} は JSON エスケープ済の引用符付き文字列
_PS_SAPI_SCRIPT = """
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {{
    $jaVoice = $synth.GetInstalledVoices() |
        Where-Object {{ $_.VoiceInfo.Culture.Name -like 'ja*' }} |
        Select-Object -First 1
    if ($jaVoice) {{ $synth.SelectVoice($jaVoice.VoiceInfo.Name) }}
}} catch {{ }}
$synth.Rate = {rate}
$synth.Speak({text_json})
$synth.Dispose()
"""


def _try_ps_sapi(text: str, rate: int = 0, timeout_sec: int = 30) -> bool:
    """試行 2: PowerShell System.Speech.Synthesis (Windows 標準、 依存ゼロ)"""
    text_json = json.dumps(text, ensure_ascii=False)
    script = _PS_SAPI_SCRIPT.format(rate=int(rate), text_json=text_json)
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            timeout=timeout_sec,
        )
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace")[:500]
            print(f"[notify] PS SAPI rc={proc.returncode}: {err}", file=sys.stderr)
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"[notify] PS SAPI timeout after {timeout_sec}s", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[notify] PS SAPI failed: {type(e).__name__}: {e}", file=sys.stderr)
        return False


def speak(text: str, *, rate: int = 0, async_: bool = False) -> bool:
    """TTS で 1 メッセージ読み上げる。 成功 True / 失敗 False。

    Args:
        text: 読み上げる日本語テキスト
        rate: -10 (遅) .. +10 (速)。 0 で既定
        async_: True で別スレッド (daemon) 起動して即 return True

    試行順: pyttsx3 → PowerShell SAPI → 失敗。
    どの段で例外が出ても本体は止めない (best-effort)。
    """
    if not text or not text.strip():
        return False

    def _run() -> bool:
        if _try_pyttsx3(text, rate=rate):
            return True
        return _try_ps_sapi(text, rate=rate)

    if async_:
        t = threading.Thread(target=_run, name="notify-tts", daemon=True)
        t.start()
        return True
    return _run()


# ============================================================
# ClickResult → 文面生成
# ============================================================

@dataclass
class NotifyOutcome:
    text: str
    spoken: bool


def _compose_text(result: "ClickResult") -> str:
    """ClickResult.action に応じた日本語文面を組み立てる"""
    content = result.content
    receipt = result.receipt

    if result.action == "clicked":
        parts: list[str] = []
        if receipt and receipt.receipt_number:
            parts.append(f"受付番号 {format_receipt_number_kana(receipt.receipt_number)}。")
        parts.append("投票完了。")
        if content:
            parts.append(f"合計 {format_yen(content.total_yen)}、 ベット {content.n_bets} 件。")
        if not result.result_closed:
            parts.append("結果ダイアログ閉じ失敗のため、 手動で確認してください。")
        return " ".join(parts)

    if result.action == "dry_run":
        parts = ["ドライランで投票内容を検証しました。"]
        if content:
            parts.append(f"合計 {format_yen(content.total_yen)}、 ベット {content.n_bets} 件。")
        parts.append("実投票はしていません。")
        return " ".join(parts)

    if result.action == "rejected":
        return f"投票キャンセル。 理由: {result.reason}"

    if result.action == "timeout":
        return f"投票ダイアログが時間内に表示されませんでした。 投票していません。 詳細: {result.reason}"

    if result.action == "error":
        return f"投票エラー。 詳細はログを確認してください。 {result.reason}"

    # 未知 action は最低限読み上げる
    return f"投票結果 {result.action}。 {result.reason}"


def build_daily_plan_text(
    *,
    bets_summary: list[dict],
    total_yen: int,
    max_detail: int = 3,
) -> str:
    """当日プラン読み上げ文面を組み立てる (シズネ 🔴 A / Session 131 二重認証ゲート)

    Args:
        bets_summary: 各 bet の概要 dict のリスト
            必須 key: race_id (str, 16桁)、 umaban (int)
            任意 key: venue_name (str)、 race_number (int)、 horse_name (str)
        total_yen: 合計金額
        max_detail: 詳細読み上げする件数の上限 (それ以降は「他 N 件」)

    Returns:
        音声読み上げ用テキスト
        例: 「本日の投票プラン。 新潟8R 単勝 6 番、 京都8R 単勝 5 番、 他 3 件。
              合計 5 件、 5000円。 暗証番号を入力すると投票を開始します。」
    """
    n = len(bets_summary)
    if n == 0:
        return ("本日の投票プランが空です。 暗証番号を入力する必要はありません。")

    detail_parts: list[str] = []
    for b in bets_summary[:max_detail]:
        venue = (b.get("venue_name") or "").strip()
        race_no = b.get("race_number")
        umaban = b.get("umaban", "?")
        amount = b.get("amount")
        if venue and race_no:
            label = f"{venue}{race_no}R"
        else:
            # フォールバック: race_id 末尾 2 桁 (RR) を会場略号と組み合わせ
            rid = b.get("race_id", "")
            label = f"レース{rid[-2:]}" if rid else "レース"
        # Session 134 🔴-2: freebudget 経路は不均等案分 (100円/700円等) なので
        # 金額を読み上げないと二重認証ゲートの内容承認解像度が落ちる。
        # amount が渡っていれば「N 番 X円」 と読み上げ、 None なら従来通り。
        if isinstance(amount, int) and amount > 0:
            detail_parts.append(f"{label} 単勝 {umaban} 番 {amount}円")
        else:
            detail_parts.append(f"{label} 単勝 {umaban} 番")

    if n > max_detail:
        detail_parts.append(f"他 {n - max_detail} 件")

    return (f"本日の投票プラン。 {'、 '.join(detail_parts)}。 "
            f"合計 {n} 件、 {total_yen}円。 "
            "暗証番号を入力すると投票を開始します。")


def notify_daily_plan_summary(
    *,
    bets_summary: list[dict],
    total_yen: int,
    max_detail: int = 3,
    enabled: bool = True,
    rate: int = 0,
) -> NotifyOutcome:
    """当日プラン音声読み上げ (シズネ 🔴 A / Session 131 二重認証ゲート)

    `wait_ipat_login_ready()` 検知後、 ふくだ暗証番号入力の **直前** に呼ぶ。
    ふくだは「これを聞いて違和感がなければ暗証番号を入力」 = 暗証番号入力が
    ① IPAT ログイン認証 ② 当日プラン内容承認 の二重認証として機能する。

    返り値の NotifyOutcome.text は audit ログ等に焼き込むのに使う。
    """
    text = build_daily_plan_text(
        bets_summary=bets_summary, total_yen=total_yen, max_detail=max_detail,
    )
    if not enabled:
        return NotifyOutcome(text=text, spoken=False)
    try:
        ok = speak(text, rate=rate)
    except Exception as e:
        print(f"[notify] notify_daily_plan_summary speak() raised: {e}", file=sys.stderr)
        ok = False
    return NotifyOutcome(text=text, spoken=ok)


def notify_launch_ready(
    *,
    dialogs_dismissed: int = 0,
    enabled: bool = True,
    rate: int = 0,
) -> NotifyOutcome:
    """TARGET 起動完了の音声通知 (Session 131+ / Phase 4-A 完了時)。

    起動シーケンスでダイアログを N 件進行したことも伝える。
    """
    if dialogs_dismissed > 0:
        text = (f"TARGET の起動が完了しました。 認証ダイアログを {dialogs_dismissed} 件、 "
                "自動進行しました。 IPAT 暗証番号を入力してください。")
    else:
        text = "TARGET の起動が完了しました。 IPAT 暗証番号を入力してください。"
    if not enabled:
        return NotifyOutcome(text=text, spoken=False)
    try:
        ok = speak(text, rate=rate)
    except Exception as e:
        print(f"[notify] notify_launch_ready speak() raised: {e}", file=sys.stderr)
        ok = False
    return NotifyOutcome(text=text, spoken=ok)


def notify_ipat_login_required(
    *,
    enabled: bool = True,
    rate: int = 0,
) -> NotifyOutcome:
    """IPAT 暗証番号入力を促す音声通知 (Phase 4-B 完了時)。

    意図的に手動で残す唯一のステップなので、 はっきり通知する。
    """
    text = "IPAT 暗証番号の入力をお待ちしています。 認証してください。"
    if not enabled:
        return NotifyOutcome(text=text, spoken=False)
    try:
        ok = speak(text, rate=rate)
    except Exception as e:
        print(f"[notify] notify_ipat_login_required speak() raised: {e}", file=sys.stderr)
        ok = False
    return NotifyOutcome(text=text, spoken=ok)


def notify_ipat_login_complete(
    *,
    enabled: bool = True,
    rate: int = 0,
) -> NotifyOutcome:
    """IPAT 認証完了 → 投票準備完了の音声通知 (Phase 4-C 完了時)"""
    text = "IPAT 認証が完了しました。 投票を開始します。"
    if not enabled:
        return NotifyOutcome(text=text, spoken=False)
    try:
        ok = speak(text, rate=rate)
    except Exception as e:
        print(f"[notify] notify_ipat_login_complete speak() raised: {e}", file=sys.stderr)
        ok = False
    return NotifyOutcome(text=text, spoken=ok)


def notify_launch_failure(
    *,
    reason: str,
    enabled: bool = True,
    rate: int = 0,
) -> NotifyOutcome:
    """TARGET 起動失敗の音声通知 (Phase 4-A 失敗時)"""
    text = (f"TARGET の自動起動に失敗しました。 {reason}。 "
            "手動で TARGET を起動してください。")
    if not enabled:
        return NotifyOutcome(text=text, spoken=False)
    try:
        ok = speak(text, rate=rate)
    except Exception as e:
        print(f"[notify] notify_launch_failure speak() raised: {e}", file=sys.stderr)
        ok = False
    return NotifyOutcome(text=text, spoken=ok)


def notify_ipat_session_expired(
    *,
    enabled: bool = True,
    rate: int = 0,
) -> NotifyOutcome:
    """IPAT セッション切れの音声通知 (Phase 4-C / Session 131+ 拡張用)"""
    text = ("IPAT セッションが切れました。 投票を中断しています。 "
            "再認証してください。")
    if not enabled:
        return NotifyOutcome(text=text, spoken=False)
    try:
        ok = speak(text, rate=rate)
    except Exception as e:
        print(f"[notify] notify_ipat_session_expired speak() raised: {e}", file=sys.stderr)
        ok = False
    return NotifyOutcome(text=text, spoken=ok)


def notify_ipat_start_failure(
    *,
    strategies_tried: Optional[list[str]] = None,
    enabled: bool = True,
    rate: int = 0,
) -> NotifyOutcome:
    """IPAT 投票起動失敗の音声通知 (Session 130 / シズネ N)。

    menu_runner.step3_start_ipat() が全戦略失敗したときに呼ぶ。
    ふくだに「TARGET で手動で IPAT 投票ボタンを押してください」 と通知する。
    """
    n = len(strategies_tried or [])
    if n:
        text = (f"IPAT 投票の自動起動に失敗しました。 試行した戦略は {n} 件すべて失敗。 "
                "TARGET ウィンドウで手動で IPAT 投票ボタンを押してください。")
    else:
        text = ("IPAT 投票の自動起動に失敗しました。 TARGET ウィンドウで手動で "
                "IPAT 投票ボタンを押してください。")
    if not enabled:
        return NotifyOutcome(text=text, spoken=False)
    try:
        ok = speak(text, rate=rate)
    except Exception as e:
        print(f"[notify] notify_ipat_start_failure speak() raised: {e}", file=sys.stderr)
        ok = False
    return NotifyOutcome(text=text, spoken=ok)


def notify_target_save_failure(
    *,
    receipt_numbers: Optional[list[str]] = None,
    error_type: Optional[str] = None,
    enabled: bool = True,
    rate: int = 0,
) -> NotifyOutcome:
    """TARGET 買い目データ保存失敗の音声通知 (Session 130 / シズネ M)。

    重要: IPAT 投票は成立済 (= お金は動いた) が、 TARGET 側「買い目データ」 への
    保存だけ失敗した状態。 ふくだに「投票は成立、 TARGET 側保存は手動でお願い」 と伝える。
    """
    parts: list[str] = ["注意。 投票は成立しましたが、 TARGET 側の買い目データ保存に失敗しました。"]
    if receipt_numbers:
        kana_list = [format_receipt_number_kana(r) for r in receipt_numbers if r]
        if kana_list:
            parts.append(f"受付番号 {', '.join(kana_list)} は IPAT 側で受付済です。")
    parts.append("TARGET ウィンドウで F10 と 「はい」 を手動で押すか、 そのまま無視してください。")
    text = " ".join(parts)
    if not enabled:
        return NotifyOutcome(text=text, spoken=False)
    try:
        ok = speak(text, rate=rate)
    except Exception as e:
        print(f"[notify] notify_target_save_failure speak() raised: {e}", file=sys.stderr)
        ok = False
    return NotifyOutcome(text=text, spoken=ok)


def notify_ipat_session_recovery_attempted(
    *,
    detected_title: Optional[str] = None,
    enabled: bool = True,
    rate: int = 0,
) -> NotifyOutcome:
    """IPAT セッション切れ検知 → 復旧試行開始の音声通知 (Session 132 / Phase 4-C-full)

    `auto_vote.py` の事後検知 hook が、 timeout/close_result 失敗時に
    `detect_session_expired_dialog()` で検知したタイミングで呼ぶ。
    """
    if detected_title:
        text = (f"IPAT セッション切れを検知しました。 ダイアログ {detected_title}。 "
                "TARGET 再起動なしで復旧を試みます。")
    else:
        text = ("IPAT セッション切れの可能性を検知しました。 "
                "TARGET 再起動なしで復旧を試みます。")
    if not enabled:
        return NotifyOutcome(text=text, spoken=False)
    try:
        ok = speak(text, rate=rate)
    except Exception as e:
        print(f"[notify] notify_ipat_session_recovery_attempted speak() raised: {e}",
              file=sys.stderr)
        ok = False
    return NotifyOutcome(text=text, spoken=ok)


def notify_ipat_session_recovery_succeeded(
    *,
    elapsed_sec: Optional[float] = None,
    enabled: bool = True,
    rate: int = 0,
) -> NotifyOutcome:
    """IPAT セッション復旧成功の音声通知 (Session 132 / Phase 4-C-full)

    シズネ Session 132 レビュー 🔴-1 修正 A:
      旧文面「投票を継続します」 は「= 直前 bets[] の自動再送」 と誤解されうる。
      復旧後の自動再送は **しない** (設計書 §1.3 範囲外 / 二重投票リスク回避) ため、
      文面で明示する。 ふくだに「ledger 確認 + 必要なら手動で再投票」 を促す。
    """
    prefix = f"IPAT セッションの再認証に成功しました。 所要 {int(elapsed_sec)} 秒。 " \
             if (elapsed_sec is not None and elapsed_sec > 0) \
             else "IPAT セッションの再認証に成功しました。 "
    text = (prefix +
            "ただし、 前回検知した未投票分の自動再送はしません。 "
            "再投票が必要なレースは ledger を確認した上で、 必要なら手動で投票してください。")
    if not enabled:
        return NotifyOutcome(text=text, spoken=False)
    try:
        ok = speak(text, rate=rate)
    except Exception as e:
        print(f"[notify] notify_ipat_session_recovery_succeeded speak() raised: {e}",
              file=sys.stderr)
        ok = False
    return NotifyOutcome(text=text, spoken=ok)


def notify_ipat_session_recovery_required_manual(
    *,
    reason: Optional[str] = None,
    enabled: bool = True,
    rate: int = 0,
) -> NotifyOutcome:
    """IPAT セッション自動復旧失敗 → 手動再認証を要求 (Session 132 / Phase 4-C-full)

    残りレースの投票は abort される。 ふくだに「手動で TARGET から IPAT 再起動 +
    暗証番号入力」 を求める。
    """
    base = "IPAT セッションの自動復旧に失敗しました。"
    if reason:
        base += f" 理由 {reason}。"
    text = (base + " 残りレースの投票を中断します。 "
            "TARGET ウィンドウから手動で IPAT 投票を再起動して暗証番号を入力してください。")
    if not enabled:
        return NotifyOutcome(text=text, spoken=False)
    try:
        ok = speak(text, rate=rate)
    except Exception as e:
        print(f"[notify] notify_ipat_session_recovery_required_manual speak() raised: {e}",
              file=sys.stderr)
        ok = False
    return NotifyOutcome(text=text, spoken=ok)


def notify_recent_session_expired_warning(
    *,
    count: int,
    most_recent_at: Optional[str],
    window_minutes: int = 60,
    enabled: bool = True,
    rate: int = 0,
) -> NotifyOutcome:
    """直近 window_minutes 以内の IPAT_SESSION_EXPIRED_POSTVOTE event 検出時の警告音声

    シズネ Session 132 レビュー 🔴-1 修正 B (Session 133 実装):
      `runner.py --auto-launch` 起動時に直近セッション切れ event を発見したら
      二重投票防止のため abort + 警告音声。 ふくだが「あ、 また selective_vote.bat
      を叩いていいんだ」 と誤解して再実行することを構造的に防ぐ。
    """
    parts = [f"注意。 直近 {window_minutes} 分以内に IPAT セッション切れを "
             f"{count} 件検知済みです。"]
    if most_recent_at:
        parts.append(f"最終検知時刻 {most_recent_at}。")
    parts.append("二重投票防止のため、 起動を中断しました。")
    parts.append("ledger と IPAT 履歴を照合し、 必要に応じて手動で投票してください。")
    parts.append("意図的に継続する場合は --ignore-recent-session-expired を指定してください。")
    text = " ".join(parts)
    if not enabled:
        return NotifyOutcome(text=text, spoken=False)
    try:
        ok = speak(text, rate=rate)
    except Exception as e:
        print(f"[notify] notify_recent_session_expired_warning speak() raised: {e}",
              file=sys.stderr)
        ok = False
    return NotifyOutcome(text=text, spoken=ok)


def notify_vote_result(
    result: "ClickResult",
    *,
    enabled: bool = True,
    rate: int = 0,
    async_: bool = False,
) -> NotifyOutcome:
    """ClickResult から文面生成 + TTS。 NotifyOutcome を返す (audit 用)。

    enabled=False なら text 組み立てだけして speak はスキップ。
    """
    text = _compose_text(result)
    if not enabled:
        return NotifyOutcome(text=text, spoken=False)
    try:
        ok = speak(text, rate=rate, async_=async_)
    except Exception as e:
        print(f"[notify] notify_vote_result speak() raised: {e}", file=sys.stderr)
        ok = False
    return NotifyOutcome(text=text, spoken=ok)


# ============================================================
# CLI (単独テスト用)
# ============================================================

def _cli() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="notify.py 単独テスト")
    parser.add_argument("text", nargs="?", default="受付番号 ゼロ ゼロ 四 五。 投票完了",
                        help="読み上げる日本語テキスト")
    parser.add_argument("--rate", type=int, default=0, help="-10..10")
    parser.add_argument("--async", dest="async_", action="store_true",
                        help="非同期発話 (即 return)")
    args = parser.parse_args()
    ok = speak(args.text, rate=args.rate, async_=args.async_)
    print(f"speak() -> {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_cli())
