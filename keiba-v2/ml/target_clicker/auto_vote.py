#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TARGET 投票内容確認ダイアログ自動押下エンジン

Session 127 (2026-05-24) で実装。 ふくだ判断:
  「TARGET の最後の投票ボタンさえ PG で押させるならそれでもよい」

技術: pywinauto 0.6.9 (Win32 backend)

検出対象ダイアログ:
  Window title: "投票内容確認"
  Body text   : "以下の買い目で投票します。"
  Buttons     : "投票" (clicked) / "キャンセル"
  Field       : "合計金額 NNN円" (検証)

安全機構 (シズネ視点で必須):
  1. デフォルト dry-run (--confirm 明示必須)
  2. 合計金額の上限チェック (--max-yen)
  3. ベット数の上限チェック (--max-bets)
  4. ダイアログタイトル完全一致 (誤認防止)
  5. ボタンラベル "投票" 完全一致
  6. JSONL 監査ログ追記 (data3/userdata/target_clicker/audit_{yyyy-mm}.jsonl)
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pywinauto import Desktop
from pywinauto.findwindows import ElementNotFoundError
from pywinauto.timings import TimeoutError as PWATimeoutError


DIALOG_TITLE = "投票内容確認"
VOTE_BUTTON_TITLE = "投票"
CANCEL_BUTTON_TITLE = "キャンセル"

# 投票後に出る完了ダイアログ
RESULT_DIALOG_TITLE = "投票終了"
OK_BUTTON_TITLE = "OK"

AUDIT_DIR = Path(os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")) \
    / "userdata" / "target_clicker"


@dataclass
class DialogContent:
    """投票内容確認ダイアログから抽出した検証用情報"""
    total_yen: int                    # 合計金額 (円)
    n_bets: int                       # 投票ベット数
    limit_yen: int                    # 購入限度額 (IPAT 残高)
    raw_text: str                     # 全文 (監査用)


@dataclass
class ReceiptInfo:
    """投票終了ダイアログから抽出した JRA 受付情報"""
    receipt_number: Optional[str]     # 受付番号 (例: "0029")
    receipt_time: Optional[str]       # 受付時刻 (例: "09:54")
    receipt_bets: Optional[int]       # 受付ベット数
    receipt_total_yen: Optional[int]  # 受付合計金額
    raw_text: str


@dataclass
class ClickResult:
    """投票試行の結果"""
    success: bool
    action: str                       # "clicked" / "dry_run" / "rejected" / "timeout" / "error"
    reason: str
    content: Optional[DialogContent]
    clicked_at: Optional[str] = None
    dialog_handle: Optional[int] = None
    receipt: Optional[ReceiptInfo] = None       # 投票完了後の JRA 受付情報
    result_closed: bool = False                 # 投票終了ダイアログを OK で閉じたか


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _extract_yen(text: str, key: str) -> Optional[int]:
    """テキストから '合計金額 100円' のような連続パターンを抽出"""
    pattern = re.compile(re.escape(key) + r"\s*([\d,]+)\s*円")
    m = pattern.search(text)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _extract_int_after(text: str, key: str) -> Optional[int]:
    """'投票ベット数：1' のような数値を抽出 (全角・半角コロン両対応)"""
    pattern = re.compile(re.escape(key) + r"\s*[:：]?\s*([\d,]+)")
    m = pattern.search(text)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


# TARGET ダイアログのラベル/値分離構造に対応するパース
# 実環境観察 (2026-05-24): texts は ['投票ベット数 : 15', '合計金額', '購入可能件数',
#   '購入限度額', '3,000円', '9,000件', '29,090円', '投票', 'キャンセル', ...] のような順序
# ラベル群が先、 値群が後で並ぶため、 ラベル順と値順の対応付けで解決する。
_LABEL_TO_UNIT = {
    "合計金額": "円",
    "購入限度額": "円",
    "購入可能件数": "件",
}
_VALUE_RE = re.compile(r"^([\d,]+)\s*(円|件)$")


def _extract_label_value_pairs(texts: list[str]) -> dict[str, int]:
    """ラベルと値が別コントロールに分離してる TARGET ダイアログ用のパーサ

    アルゴリズム:
      1. ラベル ('合計金額','購入限度額','購入可能件数') を出現順に集める
      2. 値 ('3,000円', '9,000件' 等) を出現順に集める (単位付き)
      3. ラベルの定義 unit と値の unit を順番にマッチング
         - ラベル '合計金額' (円) → 次の '円' 値
         - ラベル '購入可能件数' (件) → 次の '件' 値
         - ラベル '購入限度額' (円) → 次の '円' 値
    """
    label_order: list[str] = []
    values: list[tuple[int, str]] = []   # (数値, 単位)
    for t in texts:
        if t in _LABEL_TO_UNIT:
            label_order.append(t)
            continue
        m = _VALUE_RE.match(t)
        if m:
            try:
                num = int(m.group(1).replace(",", ""))
                values.append((num, m.group(2)))
            except ValueError:
                continue

    # 単位ごとにキュー化して順番に消費
    yen_q = [v for v, u in values if u == "円"]
    ken_q = [v for v, u in values if u == "件"]
    out: dict[str, int] = {}
    for lab in label_order:
        unit = _LABEL_TO_UNIT[lab]
        if unit == "円" and yen_q:
            out[lab] = yen_q.pop(0)
        elif unit == "件" and ken_q:
            out[lab] = ken_q.pop(0)
    return out


def _read_dialog_content(dlg) -> DialogContent:
    """ダイアログ内の Static テキスト群から内容を抽出"""
    texts: list[str] = []
    try:
        for child in dlg.descendants():
            try:
                t = child.window_text()
                if t and t.strip():
                    texts.append(t.strip())
            except Exception:
                continue
    except Exception:
        pass
    full = " | ".join(texts)

    # まず連続パターン ('合計金額 100円') で試す
    total_yen = _extract_yen(full, "合計金額") or 0
    limit_yen = _extract_yen(full, "購入限度額") or 0

    # 失敗 (= TARGET のラベル/値分離レイアウト) ならペア対応で抽出
    if total_yen == 0 or limit_yen == 0:
        pairs = _extract_label_value_pairs(texts)
        if total_yen == 0:
            total_yen = pairs.get("合計金額", 0)
        if limit_yen == 0:
            limit_yen = pairs.get("購入限度額", 0)

    n_bets = _extract_int_after(full, "投票ベット数") or 0
    return DialogContent(
        total_yen=total_yen,
        n_bets=n_bets,
        limit_yen=limit_yen,
        raw_text=full,
    )


def find_dialog_by_title(title: str, timeout_sec: int, poll_sec: float = 0.5):
    """指定タイトルのダイアログを待機"""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            dlg = Desktop(backend="win32").window(title=title)
            if dlg.exists(timeout=0.2):
                return dlg
        except (ElementNotFoundError, PWATimeoutError):
            pass
        except Exception:
            pass
        time.sleep(poll_sec)
    return None


def find_vote_dialog(timeout_sec: int = 30, poll_sec: float = 0.5):
    """投票内容確認ダイアログを待機"""
    return find_dialog_by_title(DIALOG_TITLE, timeout_sec, poll_sec)


_RECEIPT_NO_RE = re.compile(r"受付番号\s*[:：]\s*(\d+)")
_RECEIPT_TIME_RE = re.compile(r"受付時刻\s*[:：]\s*([\d:：]+)")
_RECEIPT_BETS_RE = re.compile(r"受付ベット数\s*[:：]\s*([\d,]+)")


def _read_receipt(dlg) -> ReceiptInfo:
    """投票終了ダイアログから JRA 受付情報を抽出"""
    texts: list[str] = []
    try:
        for child in dlg.descendants():
            try:
                t = child.window_text()
                if t and t.strip():
                    texts.append(t.strip())
            except Exception:
                continue
    except Exception:
        pass
    full = " | ".join(texts)

    no_m = _RECEIPT_NO_RE.search(full)
    tm_m = _RECEIPT_TIME_RE.search(full)
    bets_m = _RECEIPT_BETS_RE.search(full)
    pairs = _extract_label_value_pairs(texts)

    bets = None
    if bets_m:
        try:
            bets = int(bets_m.group(1).replace(",", ""))
        except ValueError:
            bets = None

    return ReceiptInfo(
        receipt_number=no_m.group(1) if no_m else None,
        receipt_time=tm_m.group(1).replace("：", ":") if tm_m else None,
        receipt_bets=bets,
        receipt_total_yen=pairs.get("合計金額"),
        raw_text=full,
    )


def close_result_dialog(timeout_sec: int = 10, verbose: bool = True
                        ) -> tuple[bool, Optional[ReceiptInfo]]:
    """投票終了ダイアログを検出して OK 押下。 (closed, receipt) を返す"""
    dlg = find_dialog_by_title(RESULT_DIALOG_TITLE, timeout_sec=timeout_sec)
    if dlg is None:
        if verbose:
            print(f"[{_now_iso()}] result dialog {RESULT_DIALOG_TITLE!r} "
                  f"not found within {timeout_sec}s (skip)")
        return (False, None)
    receipt = _read_receipt(dlg)
    if verbose:
        print(f"[{_now_iso()}] result dialog detected: "
              f"受付番号={receipt.receipt_number} 時刻={receipt.receipt_time} "
              f"ベット数={receipt.receipt_bets} 合計={receipt.receipt_total_yen}円")
    try:
        ok_btn = dlg.child_window(title=OK_BUTTON_TITLE)
        if not ok_btn.exists(timeout=2):
            if verbose:
                print(f"[{_now_iso()}] OK button not found in result dialog")
            return (False, receipt)
        ok_btn.click()
        if verbose:
            print(f"[{_now_iso()}] CLICKED [OK] on result dialog")
        return (True, receipt)
    except Exception as e:
        if verbose:
            print(f"[{_now_iso()}] OK click failed: {type(e).__name__}: {e}")
        return (False, receipt)


def click_vote_button(
    *,
    confirm: bool = False,
    max_yen: int = 100,
    max_bets: int = 1,
    timeout_sec: int = 30,
    close_result: bool = True,
    result_timeout_sec: int = 10,
    verbose: bool = True,
) -> ClickResult:
    """TARGET 投票ダイアログを検出して [投票] ボタンを click する。

    Args:
        confirm: True で実際に click。 False は dry-run (検出のみ)
        max_yen: この円を超えたら reject
        max_bets: このベット数を超えたら reject
        timeout_sec: ダイアログ待機タイムアウト
        verbose: stdout にログ出力
    """

    def vprint(msg: str) -> None:
        if verbose:
            print(msg)

    vprint(f"[{_now_iso()}] dialog wait (timeout={timeout_sec}s) title={DIALOG_TITLE!r}")
    dlg = find_vote_dialog(timeout_sec=timeout_sec)
    if dlg is None:
        return _audit(ClickResult(
            success=False, action="timeout",
            reason=f"dialog {DIALOG_TITLE!r} not found within {timeout_sec}s",
            content=None,
        ))

    handle = None
    try:
        handle = dlg.handle
    except Exception:
        pass

    content = _read_dialog_content(dlg)
    vprint(f"[{_now_iso()}] dialog detected: total={content.total_yen}円 "
           f"limit={content.limit_yen}円 bets={content.n_bets}")
    vprint(f"  raw: {content.raw_text[:300]}")

    # 検証
    if content.total_yen <= 0:
        return _audit(ClickResult(
            success=False, action="rejected",
            reason=f"合計金額 抽出失敗 (total_yen=0)", content=content,
            dialog_handle=handle,
        ))
    if content.total_yen > max_yen:
        return _audit(ClickResult(
            success=False, action="rejected",
            reason=f"合計金額 {content.total_yen}円 > 上限 {max_yen}円",
            content=content, dialog_handle=handle,
        ))
    if content.n_bets > max_bets:
        return _audit(ClickResult(
            success=False, action="rejected",
            reason=f"ベット数 {content.n_bets} > 上限 {max_bets}",
            content=content, dialog_handle=handle,
        ))
    if content.limit_yen > 0 and content.total_yen > content.limit_yen:
        return _audit(ClickResult(
            success=False, action="rejected",
            reason=f"IPAT 残高不足: 合計 {content.total_yen}円 > 残高 {content.limit_yen}円",
            content=content, dialog_handle=handle,
        ))

    # dry-run
    if not confirm:
        vprint(f"[{_now_iso()}] DRY-RUN: would click [{VOTE_BUTTON_TITLE}]")
        return _audit(ClickResult(
            success=True, action="dry_run",
            reason="dry-run mode (--confirm not passed)",
            content=content, dialog_handle=handle,
        ))

    # 実 click
    try:
        btn = dlg.child_window(title=VOTE_BUTTON_TITLE, control_type="Button")
        if not btn.exists(timeout=2):
            # Win32 backend は control_type を無視するので fallback
            btn = dlg.child_window(title=VOTE_BUTTON_TITLE)
        btn.click()
        clicked_at = _now_iso()
        vprint(f"[{clicked_at}] CLICKED [{VOTE_BUTTON_TITLE}] button")
    except Exception as e:
        return _audit(ClickResult(
            success=False, action="error",
            reason=f"click failed: {type(e).__name__}: {e}",
            content=content, dialog_handle=handle,
        ))

    # 投票終了ダイアログを検出して OK 押下
    receipt: Optional[ReceiptInfo] = None
    closed = False
    if close_result:
        # ダイアログ表示まで少し待つ
        time.sleep(1.0)
        closed, receipt = close_result_dialog(
            timeout_sec=result_timeout_sec, verbose=verbose,
        )

    return _audit(ClickResult(
        success=True, action="clicked",
        reason="vote button clicked"
               + (" + result dialog closed" if closed else ""),
        content=content, clicked_at=clicked_at, dialog_handle=handle,
        receipt=receipt, result_closed=closed,
    ))


def _audit(result: ClickResult) -> ClickResult:
    """JSONL 監査ログ追記 (data3/userdata/target_clicker/audit_{yyyy-mm}.jsonl)"""
    try:
        AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.now()
        log_path = AUDIT_DIR / f"audit_{now.strftime('%Y-%m')}.jsonl"
        entry = {
            "ts": _now_iso(),
            "success": result.success,
            "action": result.action,
            "reason": result.reason,
            "clicked_at": result.clicked_at,
            "dialog_handle": result.dialog_handle,
            "total_yen": result.content.total_yen if result.content else None,
            "n_bets": result.content.n_bets if result.content else None,
            "limit_yen": result.content.limit_yen if result.content else None,
            "raw_text": result.content.raw_text if result.content else None,
            "receipt_number": result.receipt.receipt_number if result.receipt else None,
            "receipt_time": result.receipt.receipt_time if result.receipt else None,
            "receipt_bets": result.receipt.receipt_bets if result.receipt else None,
            "receipt_total_yen": result.receipt.receipt_total_yen if result.receipt else None,
            "receipt_raw_text": result.receipt.raw_text if result.receipt else None,
            "result_closed": result.result_closed,
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        # 監査ログ失敗は本体を止めない (ログ欠損 < 状態欠損、 シズネ原則)
        print(f"[audit] failed to write: {e}", file=sys.stderr)
    return result
