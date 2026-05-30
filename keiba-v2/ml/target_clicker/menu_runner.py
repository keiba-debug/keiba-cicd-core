#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TARGET frontier JV のメニュー操作を pywinauto で自動化

実環境観察 (Session 127, 2026-05-24 ふくだ環境スクショより):
  - メインウィンドウ: class='TApplication', text='TARGET frontier JV  Ver6.21  Rev002'
  - Delphi VCL アプリ

実フロー:
  1. ﾌｧｲﾙ(&F) → 特定フォーマットの買い目の一括読み込み → 買い目CSV形式(C)
  2. 「買い目CSV形式ファイルの選択」 ダイアログ
       - アクセスフォルダ C:\\TFJV\\TXT\\ デフォルト
       - 指定ファイル名(F) Edit に FF*.CSV パスを入力
       - [OK] click
  3. 「買い目一括処理(読込/投票/出力)」 ウィンドウ表示
       - 取り込んだ買い目一覧
       - [OK (F10)] click → 取り込み確定
  4. 「情報」 ダイアログ「読み込んだ買い目を買い目データに加えます。よろしいですか？」
       - [はい(Y)] click → TARGET 買い目データに保存
  5. 「買い目一括処理」 ウィンドウに戻る
       - [IPAT投票] click → 投票内容確認ダイアログ
  6. 「投票内容確認」 ダイアログ → [投票] click → 「投票終了」 ダイアログ → [OK] click
       (これは target_clicker.auto_vote.click_vote_button が担当)
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pywinauto import Application, Desktop
from pywinauto.keyboard import send_keys


TARGET_WINDOW_KEYWORD = "TARGET frontier JV"

# メニューパス (実環境で確認した完全一致)
MENU_LOAD_CSV = "ﾌｧｲﾙ(&F)->特定フォーマットの買い目の一括読み込み->買い目CSV形式(C)"

# ダイアログ/ウィンドウのタイトル
DLG_CSV_FILE_SELECT = "買い目CSV形式ファイルの選択"
WIN_BATCH_PROCESS_RE = r"買い目一括処理.*"
DLG_INFO_CONFIRM = "情報"
DLG_VOTE_CONFIRM = "投票内容確認"  # 既存 auto_vote.py 側で扱う

# 「IPAT投票」 ボタン攻略用 (Session 128)
# 開催中に inspect-batch で取得した座標を保存しておくファイル。
# {"ipat_button": {"x_offset": 12, "y_offset": 34, "captured_at": "...", "window_size": [w,h]}}
COORDS_CONFIG_PATH = Path(
    os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")
) / "userdata" / "target_clicker" / "coords.json"

# ショートカットキー候補 (TARGET のヘルプから推定。 実機検証で確定)
IPAT_SHORTCUT_CANDIDATES = [
    "{F11}",      # F11
    "^i",         # Ctrl+I
    "^+i",        # Ctrl+Shift+I
    "%i",         # Alt+I
    "%v",         # Alt+V (Vote)
]


# =====================================================================
# inspect 用ヘルパー
# =====================================================================

def inspect_target_windows() -> None:
    print("=== Visible windows ===")
    for w in Desktop().windows():
        try:
            if not w.is_visible():
                continue
            text = (w.window_text() or "").strip()
            if not text:
                continue
            print(f"  handle={w.handle:08x} class={w.class_name()!r:30} text={text!r}")
        except Exception:
            continue


def inspect_dialog(title: str) -> None:
    """指定タイトルのダイアログ child 構造を全列挙 (Edit/Combo の位置特定用)"""
    try:
        dlg = Desktop(backend="win32").window(title=title)
        if not dlg.exists(timeout=1):
            print(f"dialog {title!r} not found")
            return
    except Exception as e:
        print(f"dialog lookup failed: {type(e).__name__}: {e}")
        return
    print(f"=== children of {title!r} ===")
    for c in dlg.descendants():
        try:
            cls = c.class_name() or ""
            txt = (c.window_text() or "")
            rect = c.rectangle()
            print(f"  class={cls!r:30} text={txt!r:40} rect=({rect.left},{rect.top})-({rect.right},{rect.bottom})")
        except Exception:
            continue


def inspect_batch_window(*, save_json: bool = True, save_png: bool = True) -> Optional[Path]:
    """「買い目一括処理」 ウィンドウを Win32 + UIA 両方で dump

    Session 128 の IPAT 投票ボタン攻略用。 開催中にこのコマンドを 1 発走らせれば:
      - Win32 backend での全 descendants (class_name / text / rect / control_id / visible / enabled)
      - UIA backend での全 descendants (control_type / automation_id / name)
      - ウィンドウのメニュー構造 (買い目一括処理 ウィンドウは menu 持ち得る)
      - ウィンドウの client_rect 全体スクリーンショット (PNG)
      - 推測される「IPAT投票」 ボタンの座標候補
    が data3/userdata/target_clicker/inspect/batch_{YYYYMMDD_HHMMSS}.{json,png} に保存される。

    使い方 (開催中、 IPAT 連動投票起動後の「買い目一括処理」 ウィンドウが見えている状態で):
        python -m ml.target_clicker.menu_runner inspect-batch
    """
    out_dir = Path(os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3")) \
        / "userdata" / "target_clicker" / "inspect"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    result: dict = {
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "win32": {},
        "uia": {},
        "menu": [],
        "ipat_candidates": [],
        "screenshot": None,
    }

    # ===== Win32 backend =====
    try:
        from pywinauto.findwindows import find_window
        w_win32 = Desktop(backend="win32").window(title_re=WIN_BATCH_PROCESS_RE)
        if w_win32.exists(timeout=2):
            rect = w_win32.rectangle()
            result["win32"]["window"] = {
                "handle": f"{w_win32.handle:08x}",
                "class": w_win32.class_name(),
                "text": w_win32.window_text(),
                "rect": [rect.left, rect.top, rect.right, rect.bottom],
            }
            descendants_w32 = []
            for c in w_win32.descendants():
                try:
                    r = c.rectangle()
                    descendants_w32.append({
                        "class": c.class_name() or "",
                        "text": c.window_text() or "",
                        "control_id": c.control_id() if hasattr(c, "control_id") else None,
                        "rect": [r.left, r.top, r.right, r.bottom],
                        "visible": bool(c.is_visible()),
                        "enabled": bool(c.is_enabled()),
                    })
                except Exception:
                    continue
            result["win32"]["descendants"] = descendants_w32
            # IPAT 候補抽出: テキストに 'IPAT' or 'ｲｸｾﾌﾟﾄ' or '投票' を含むもの
            for d in descendants_w32:
                text = d.get("text", "")
                if any(k in text for k in ("IPAT", "ＩＰＡＴ", "投票", "PAT")):
                    result["ipat_candidates"].append({
                        "source": "win32",
                        **d,
                    })
        else:
            result["win32"]["error"] = "batch window not found via win32 backend"
    except Exception as e:
        result["win32"]["error"] = f"{type(e).__name__}: {e}"

    # ===== UIA backend =====
    try:
        w_uia = Desktop(backend="uia").window(title_re=WIN_BATCH_PROCESS_RE)
        if w_uia.exists(timeout=2):
            rect = w_uia.rectangle()
            result["uia"]["window"] = {
                "handle": f"{w_uia.handle:08x}",
                "control_type": getattr(w_uia, "element_info", None) and w_uia.element_info.control_type,
                "name": w_uia.window_text(),
                "rect": [rect.left, rect.top, rect.right, rect.bottom],
            }
            descendants_uia = []
            for c in w_uia.descendants():
                try:
                    info = c.element_info
                    r = c.rectangle()
                    descendants_uia.append({
                        "control_type": info.control_type,
                        "name": info.name or "",
                        "automation_id": info.automation_id,
                        "class": info.class_name or "",
                        "rect": [r.left, r.top, r.right, r.bottom],
                    })
                except Exception:
                    continue
            result["uia"]["descendants"] = descendants_uia
            # UIA 側からも IPAT 候補抽出
            for d in descendants_uia:
                name = d.get("name", "")
                if any(k in name for k in ("IPAT", "ＩＰＡＴ", "投票", "PAT")):
                    result["ipat_candidates"].append({
                        "source": "uia",
                        **d,
                    })
        else:
            result["uia"]["error"] = "batch window not found via uia backend"
    except Exception as e:
        result["uia"]["error"] = f"{type(e).__name__}: {e}"

    # ===== メニュー構造 =====
    try:
        from pywinauto import Application
        # 「買い目一括処理」 ウィンドウのハンドルを Win32 から取得
        if "window" in result["win32"]:
            handle_hex = result["win32"]["window"]["handle"]
            handle = int(handle_hex, 16)
            app = Application(backend="win32").connect(handle=handle)
            win = app.window(handle=handle)
            try:
                menu = win.menu()
                if menu is not None:
                    for top in menu.items():
                        top_text = top.text() or ""
                        item_entry = {"text": top_text, "items": []}
                        try:
                            sub = top.sub_menu()
                            if sub:
                                for item in sub.items():
                                    try:
                                        item_entry["items"].append({
                                            "text": item.text() or "",
                                            "id": item.item_id() if hasattr(item, "item_id") else None,
                                            "type": item.item_type() if hasattr(item, "item_type") else None,
                                        })
                                    except Exception:
                                        continue
                        except Exception:
                            pass
                        result["menu"].append(item_entry)
            except Exception as e:
                result["menu_error"] = f"{type(e).__name__}: {e}"
    except Exception as e:
        result["menu_error"] = f"{type(e).__name__}: {e}"

    # ===== スクリーンショット =====
    if save_png:
        try:
            from PIL import ImageGrab
            if "window" in result["win32"]:
                left, top, right, bottom = result["win32"]["window"]["rect"]
                img = ImageGrab.grab(bbox=(left, top, right, bottom))
                png_path = out_dir / f"batch_{ts}.png"
                img.save(png_path)
                result["screenshot"] = str(png_path)
        except ImportError:
            result["screenshot_error"] = "PIL not available (pip install pillow)"
        except Exception as e:
            result["screenshot_error"] = f"{type(e).__name__}: {e}"

    # ===== JSON 保存 =====
    json_path = None
    if save_json:
        json_path = out_dir / f"batch_{ts}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    # ===== コンソール出力 (簡潔) =====
    print(f"=== batch window inspect ===")
    if "window" in result["win32"]:
        w = result["win32"]["window"]
        print(f"  win32 window: handle={w['handle']} class={w['class']!r} text={w['text']!r}")
        print(f"               rect={w['rect']}")
        print(f"  win32 descendants: {len(result['win32'].get('descendants', []))}")
    else:
        print(f"  win32: {result['win32'].get('error', 'unknown error')}")

    if "window" in result["uia"]:
        w = result["uia"]["window"]
        print(f"  uia window:  control_type={w['control_type']!r} name={w['name']!r}")
        print(f"  uia descendants: {len(result['uia'].get('descendants', []))}")
    else:
        print(f"  uia: {result['uia'].get('error', 'unknown error')}")

    print(f"  menu items: {len(result['menu'])}")
    for m in result["menu"]:
        n_items = len(m.get("items", []))
        print(f"    - {m['text']!r} ({n_items} items)")
        if any(k in (m.get("text") or "") for k in ("IPAT", "投票")):
            for it in m.get("items", []):
                print(f"        * {it['text']!r} id={it.get('id')}")

    print(f"  IPAT candidates: {len(result['ipat_candidates'])}")
    for cand in result["ipat_candidates"]:
        r = cand.get("rect")
        if cand.get("source") == "win32":
            print(f"    [win32] class={cand.get('class')!r:20} text={cand.get('text')!r:20} "
                  f"rect={r} visible={cand.get('visible')}")
        else:
            print(f"    [uia]   control_type={cand.get('control_type')!r:20} "
                  f"name={cand.get('name')!r:20} rect={r}")

    if json_path:
        print(f"\n  saved: {json_path}")
    if result.get("screenshot"):
        print(f"  saved: {result['screenshot']}")

    return json_path


def _window_has_menu(window) -> bool:
    """そのウィンドウが (File→IPAT 等の) メニューバーを持つか。

    主ウィンドウだけがメニューを持つ。 「買い目一括処理」 や ふくだが別作業で
    開いた TARGET 系サブウィンドウはメニューを持たない (or 別構造) ので、
    これが主ウィンドウ判別の最も確実な指標。
    """
    try:
        app = Application(backend="win32").connect(handle=window.handle)
        menu = app.window(handle=window.handle).menu()
        return bool(menu and len(menu.items()) > 0)
    except Exception:
        return False


def find_target_window(name_contains: str = TARGET_WINDOW_KEYWORD):
    """TARGET 主ウィンドウを確実に掴む (Session 135 シズネ対応 / 堅牢化)

    旧実装は「keyword を含む最初の可視ウィンドウ」 を返していたため、 ふくだが
    別作業で開いた TARGET 系ウィンドウや投票後の残りウィンドウを誤って掴み、
    File→IPAT メニューが無くて step1 が失敗していた (Session 135 実機で発覚)。

    対策: keyword を含む全候補を集め、 (1) メニューを持つ (2) タイトルが keyword で
    始まる でスコアリングして主ウィンドウを選ぶ。 複数候補時は stderr 警告
    (無人運用で「別ウィンドウが開いている」 を可視化する目的)。
    """
    candidates = []
    for w in Desktop().windows():
        try:
            if not w.is_visible():
                continue
            text = w.window_text() or ""
            if name_contains in text:
                candidates.append((w, text))
        except Exception:
            continue
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0][0]

    # 複数 = 干渉ウィンドウあり。 メニュー保有 + タイトル前方一致 で主ウィンドウを選別
    def _score(item) -> int:
        w, text = item
        s = 0
        if _window_has_menu(w):
            s += 4
        if text.startswith(name_contains):
            s += 2
        return s

    scored = sorted(candidates, key=_score, reverse=True)
    titles = [t for _, t in candidates]
    print(f"[menu_runner] ⚠ TARGET 候補ウィンドウが {len(candidates)} 個: {titles} "
          f"→ 主ウィンドウとして {scored[0][1]!r} を選択 (menu保有優先)",
          file=sys.stderr)
    return scored[0][0]


def print_menu_structure(window) -> None:
    try:
        app = Application(backend="win32").connect(handle=window.handle)
        win = app.window(handle=window.handle)
        menu = win.menu()
        if menu is None:
            print("(no menu)")
            return
        for top in menu.items():
            text = top.text() or ""
            print(f"  - {text!r}")
            try:
                sub = top.sub_menu()
                if sub:
                    for item in sub.items():
                        print(f"      - {item.text()!r}")
            except Exception:
                pass
    except Exception as e:
        print(f"(menu inspect failed: {type(e).__name__}: {e})")


# =====================================================================
# 本実装
# =====================================================================

def _vp(verbose: bool, msg: str) -> None:
    if verbose:
        print(f"[menu_runner] {msg}")


def get_target_app() -> tuple[Application, "WindowSpecification"]:
    w = find_target_window()
    if w is None:
        raise RuntimeError(
            f"TARGET window not found (keyword={TARGET_WINDOW_KEYWORD!r}). "
            "TARGET frontier JV を先に起動してください。"
        )
    app = Application(backend="win32").connect(handle=w.handle)
    win = app.window(handle=w.handle)
    return app, win


def _wait_window(title_or_re: str, *, by_regex: bool, timeout: int = 10,
                 backend: str = "win32"):
    """指定タイトル/regex のウィンドウを待機"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if by_regex:
                w = Desktop(backend=backend).window(title_re=title_or_re)
            else:
                w = Desktop(backend=backend).window(title=title_or_re)
            if w.exists(timeout=0.2):
                return w
        except Exception:
            pass
        time.sleep(0.3)
    return None


def _click_button(parent, *titles, control_class: str = "TButton", timeout: int = 3):
    """子ボタンを title 候補で順に探して click_input

    TARGET (Delphi VCL) は TButton 標準。 fallback で Button も試す。
    32-bit/64-bit ミスマッチ環境では click() より click_input() の方が確実。
    """
    classes = (control_class, "Button", "TBitBtn")  # TBitBtn も Delphi 系ボタン
    for cls in classes:
        # exact title match
        for t in titles:
            try:
                btn = parent.child_window(title=t, class_name=cls)
                if btn.exists(timeout=0.5):
                    try:
                        btn.click_input()
                    except Exception:
                        btn.click()
                    return f"{t}({cls})"
            except Exception:
                continue
        # regex fallback
        for t in titles:
            try:
                btn = parent.child_window(title_re=t.replace("(", r"\(").replace(")", r"\)") + r".*",
                                          class_name=cls)
                if btn.exists(timeout=0.5):
                    try:
                        btn.click_input()
                    except Exception:
                        btn.click()
                    return f"{t}~({cls})"
            except Exception:
                continue
    return None


def _find_menu_item_id(win, *path_keywords: str) -> Optional[int]:
    """メニュー構造を辿って指定パスの末端 item の command_id を返す

    path_keywords は各階層の「部分一致」キーワード (例: ('ﾌｧｲﾙ', '特定フォーマット', 'CSV形式'))
    末端 item の command_id (WM_COMMAND で送信可能な ID) を返す
    """
    menu = win.menu()
    if menu is None:
        return None
    current_menu = menu
    last_item = None
    for kw in path_keywords:
        next_menu = None
        for item in current_menu.items():
            try:
                text = item.text() or ""
            except Exception:
                continue
            if kw in text:
                last_item = item
                try:
                    sub = item.sub_menu()
                    if sub is not None:
                        next_menu = sub
                except Exception:
                    pass
                break
        if next_menu is None:
            break
        current_menu = next_menu
    if last_item is None:
        return None
    try:
        return last_item.item_id()
    except Exception:
        try:
            return last_item.command_id()
        except Exception:
            return None


def _send_menu_command(win, cmd_id: int) -> None:
    """WM_COMMAND を PostMessage で送って 32-bit app のメニュー項目を起動

    SendMessage は同期 (相手の UI スレッドが処理完了するまでブロック) で
    ダイアログ表示時に hung することがあるため PostMessage (非同期) を使う。
    """
    import ctypes
    WM_COMMAND = 0x0111
    # PostMessageW(hwnd, WM_COMMAND, MAKEWPARAM(cmd_id, 0), 0) — メニュー由来は HIWORD=0
    rc = ctypes.windll.user32.PostMessageW(int(win.handle), WM_COMMAND, cmd_id, 0)
    if rc == 0:
        raise OSError(f"PostMessageW failed: GetLastError={ctypes.GetLastError()}")


def step1_open_csv_select(ff_path: Path, *, verbose: bool = True) -> bool:
    """Step 1+2: ファイルメニュー → CSV形式選択 → ファイル指定 → OK"""
    if not ff_path.exists():
        raise FileNotFoundError(f"FF CSV not found: {ff_path}")

    app, win = get_target_app()
    _vp(verbose, f"TARGET handle={win.handle:08x}")
    win.set_focus()
    time.sleep(0.3)

    # 32-bit TARGET / 64-bit Python のメニュー操作: WM_COMMAND を直接送る
    cmd_id = _find_menu_item_id(win, "ﾌｧｲﾙ", "特定フォーマット", "CSV形式")
    if cmd_id is None:
        # 第3階層が無いケース (古いバージョン等) は親階層名を変えて再試行
        cmd_id = _find_menu_item_id(win, "ﾌｧｲﾙ", "特定フォーマット")
    if cmd_id is None:
        _vp(verbose, "menu item id not found for: ﾌｧｲﾙ→特定フォーマット→CSV形式")
        return False
    _vp(verbose, f"send WM_COMMAND cmd_id={cmd_id}")
    _send_menu_command(win, cmd_id)
    time.sleep(0.5)

    # 「買い目CSV形式ファイルの選択」 ダイアログを待機
    dlg = _wait_window(DLG_CSV_FILE_SELECT, by_regex=False, timeout=10)
    if dlg is None:
        _vp(verbose, f"dialog {DLG_CSV_FILE_SELECT!r} not appeared")
        return False
    _vp(verbose, f"CSV select dialog detected")
    dlg.set_focus()
    time.sleep(0.2)

    # 「指定ファイル名(F)」 TComboBox にフルパス入力
    # 32-bit TARGET + 64-bit Python 環境では set_edit_text が WM_SETTEXT 経由で
    # 失敗するため、 click_input + send_keys でキーボード入力する。
    try:
        combo = dlg.child_window(class_name="TComboBox", found_index=0)
        if not combo.exists(timeout=2):
            _vp(verbose, "TComboBox (指定ファイル名) not found")
            return False
        combo.click_input()
        time.sleep(0.3)
        # 全選択削除してからファイル名を type
        send_keys("^a")
        time.sleep(0.1)
        send_keys("{DELETE}")
        time.sleep(0.1)
        path_str = str(ff_path)
        # send_keys のエスケープ ( ) { } + ^ % ~ は特殊
        escaped = (path_str
                   .replace("(", "{(}").replace(")", "{)}")
                   .replace("+", "{+}").replace("^", "{^}")
                   .replace("%", "{%}").replace("~", "{~}"))
        send_keys(escaped, with_spaces=True)
        time.sleep(0.3)
        _vp(verbose, f"typed into 指定ファイル名: {path_str}")
    except Exception as e:
        _vp(verbose, f"指定ファイル名 input failed: {type(e).__name__}: {e}")
        return False

    # [OK] click — TButton class が 32-bit/64-bit でうまく click 出来ない場合に備え
    # フォーカスは TComboBox にあるはずなので Enter キーで代用するのが最も確実
    # (OpenFileDialog の default ボタンが OK と仮定)
    try:
        # まず TButton から click 試行
        ok_btn = dlg.child_window(class_name="TButton", title="OK")
        if ok_btn.exists(timeout=1):
            try:
                ok_btn.click_input()
                _vp(verbose, "click_input [OK]")
            except Exception:
                ok_btn.click()
                _vp(verbose, "click [OK]")
        else:
            # fallback: Enter で決定
            send_keys("{ENTER}")
            _vp(verbose, "sent {ENTER} as OK")
    except Exception as e:
        _vp(verbose, f"OK click via TButton failed ({e}) — fallback {{ENTER}}")
        send_keys("{ENTER}")
    time.sleep(0.5)
    return True


def step2_confirm_import(*, verbose: bool = True, timeout: int = 15) -> bool:
    """Step 3+4: 買い目一括処理ウィンドウで OK(F10) → 「読み込んだ買い目を…」 はい"""
    # 買い目一括処理ウィンドウ待機
    win = _wait_window(WIN_BATCH_PROCESS_RE, by_regex=True, timeout=timeout)
    if win is None:
        _vp(verbose, f"window {WIN_BATCH_PROCESS_RE!r} not appeared")
        return False
    _vp(verbose, "buy-list batch process window detected")
    win.set_focus()
    time.sleep(0.3)

    # 「OK (F10)」 を F10 キーで押下 (ボタンラベルが 'OK (F10)' か 'OK' か揺れるため)
    _vp(verbose, "send_keys: {F10} (取り込み確定)")
    send_keys("{F10}")
    time.sleep(0.5)

    # 「情報」 ダイアログ 「読み込んだ買い目を…」 → はい
    info_dlg = _wait_window(DLG_INFO_CONFIRM, by_regex=False, timeout=10)
    if info_dlg is None:
        _vp(verbose, f"info dialog {DLG_INFO_CONFIRM!r} not appeared (skip)")
        return True   # info ダイアログ無くても取り込み成功と判断
    _vp(verbose, "info confirm dialog detected")
    info_dlg.set_focus()
    time.sleep(0.2)
    clicked = _click_button(info_dlg, "はい(Y)", "はい", "&Y", "Yes")
    if clicked is None:
        # Y キーで代用
        _vp(verbose, "はい button not found — sending Y key")
        send_keys("y")
    else:
        _vp(verbose, f"clicked [{clicked}]")
    time.sleep(0.5)
    return True


def _try_ipat_via_win32(win, *, verbose: bool) -> Optional[str]:
    """Strategy 1: Win32 backend で IPAT 投票ボタン直 click

    Session 127 で実機検証済: TButton / TBitBtn では取れず。
    将来 TARGET バージョンで Win32 control 化される可能性に備えて残置。
    """
    clicked = _click_button(
        win,
        "IPAT投票",
        "IPAT 投票",
        "IPAT　投票",
        "&IPAT投票",
        "ＩＰＡＴ投票",
        "IPAT",
    )
    if clicked:
        return f"win32:{clicked}"
    # TSpeedButton / TToolButton も試す
    for cls in ("TSpeedButton", "TToolButton"):
        try:
            btn = win.child_window(class_name=cls, title_re=r".*IPAT.*")
            if btn.exists(timeout=0.5):
                try:
                    btn.click_input()
                except Exception:
                    btn.click()
                return f"win32:{cls}"
        except Exception:
            continue
    return None


def _try_ipat_via_uia(*, verbose: bool, timeout: float = 2.0) -> Optional[str]:
    """Strategy 2: UIA backend で IPAT 投票ボタン直 click

    Delphi VCL の TSpeedButton は Win32 control としては露出しないことが多いが、
    UIA (Microsoft UI Automation) では Button として見える可能性がある。
    Session 127 では未試行 — Session 128 で実機検証する想定。
    """
    try:
        w_uia = Desktop(backend="uia").window(title_re=WIN_BATCH_PROCESS_RE)
        if not w_uia.exists(timeout=timeout):
            _vp(verbose, "  uia: batch window not found")
            return None
        for name in ("IPAT投票", "IPAT 投票", "ＩＰＡＴ投票", "IPAT"):
            try:
                btn = w_uia.child_window(title=name, control_type="Button")
                if btn.exists(timeout=0.5):
                    btn.click_input()
                    return f"uia:Button({name!r})"
            except Exception:
                continue
        # regex で .*IPAT.* 名の Button を探す
        try:
            btn = w_uia.child_window(title_re=r".*IPAT.*", control_type="Button")
            if btn.exists(timeout=0.5):
                btn.click_input()
                txt = btn.window_text() or "?"
                return f"uia:Button(regex {txt!r})"
        except Exception:
            pass
        # control_type 制限なしで再試行 (Pane/ListItem 等になっている可能性)
        try:
            elt = w_uia.child_window(title_re=r".*IPAT.*")
            if elt.exists(timeout=0.5):
                elt.click_input()
                return f"uia:any(regex {elt.window_text()!r})"
        except Exception:
            pass
    except Exception as e:
        _vp(verbose, f"  uia attempt failed: {type(e).__name__}: {e}")
    return None


def _try_ipat_via_menu(win, *, verbose: bool) -> Optional[str]:
    """Strategy 3: 「買い目一括処理」 ウィンドウのメニューから IPAT 起動項目を探す

    開催中の inspect-batch 結果を見て、 menu パスを確定させる前提。
    現状は推測パスを順次試行。
    """
    candidate_paths = [
        ("投票", "IPAT"),
        ("投票", "IPAT連動投票"),
        ("投票", "IPAT 連動投票"),
        ("IPAT",),
        ("ﾌｧｲﾙ", "IPAT"),
        ("操作", "IPAT"),
        ("実行", "IPAT"),
    ]
    for path in candidate_paths:
        try:
            cmd_id = _find_menu_item_id(win, *path)
            if cmd_id is not None:
                _vp(verbose, f"  menu path {path} -> cmd_id={cmd_id}")
                _send_menu_command(win, cmd_id)
                return f"menu:{'->'.join(path)}(cmd_id={cmd_id})"
        except Exception as e:
            _vp(verbose, f"  menu path {path} failed: {type(e).__name__}: {e}")
            continue
    return None


def _try_ipat_via_shortcut(win, *, verbose: bool) -> Optional[str]:
    """Strategy 4: ショートカットキー (実機検証で候補を絞る)

    開催中に 1 つだけ「投票内容確認ダイアログが出るキー」 が見つかれば、
    それを IPAT_SHORTCUT_CANDIDATES 先頭に固定。
    """
    win.set_focus()
    time.sleep(0.2)
    for key in IPAT_SHORTCUT_CANDIDATES:
        try:
            _vp(verbose, f"  trying shortcut: {key}")
            send_keys(key)
            time.sleep(0.5)
            # 投票内容確認ダイアログが出たかチェック
            try:
                dlg = Desktop(backend="win32").window(title=DLG_VOTE_CONFIRM)
                if dlg.exists(timeout=1):
                    return f"shortcut:{key}"
            except Exception:
                pass
        except Exception as e:
            _vp(verbose, f"  shortcut {key} failed: {type(e).__name__}: {e}")
            continue
    return None


def _try_ipat_via_coords(win, *, verbose: bool) -> Optional[str]:
    """Strategy 5: 既知座標 click (最後の手段)

    開催中の inspect-batch でスクリーンショット + 候補列挙して
    `data3/userdata/target_clicker/coords.json` に座標を保存する。

    coords.json 形式:
        {"ipat_button": {"x_offset": int, "y_offset": int,
                          "captured_at": "...", "window_size": [w, h]}}

    座標はウィンドウ左上からの相対オフセット。
    """
    if not COORDS_CONFIG_PATH.exists():
        _vp(verbose, f"  coords config not found: {COORDS_CONFIG_PATH}")
        return None
    try:
        with open(COORDS_CONFIG_PATH, encoding="utf-8") as f:
            coords = json.load(f)
        ipat = coords.get("ipat_button")
        if not ipat:
            _vp(verbose, "  coords.json has no 'ipat_button' entry")
            return None
        x_off = ipat["x_offset"]
        y_off = ipat["y_offset"]
        rect = win.rectangle()
        # 現在のウィンドウサイズが captured 時と大きく違うなら誤 click 防止で reject
        captured_size = ipat.get("window_size")
        cur_w = rect.right - rect.left
        cur_h = rect.bottom - rect.top
        if captured_size:
            cw, ch = captured_size
            if abs(cur_w - cw) > 50 or abs(cur_h - ch) > 50:
                _vp(verbose, f"  window size changed from {captured_size} to {(cur_w, cur_h)}, abort coords")
                return None
        abs_x = rect.left + x_off
        abs_y = rect.top + y_off
        _vp(verbose, f"  clicking absolute ({abs_x}, {abs_y}) = window+({x_off}, {y_off})")
        win.set_focus()
        time.sleep(0.2)
        # pywinauto.mouse.click は global 座標
        from pywinauto import mouse
        mouse.click(coords=(abs_x, abs_y))
        return f"coords:({x_off},{y_off})"
    except Exception as e:
        _vp(verbose, f"  coords click failed: {type(e).__name__}: {e}")
        return None


def step3_start_ipat(
    *,
    verbose: bool = True,
    timeout: int = 15,
    strategies: Optional[list[str]] = None,
) -> bool:
    """Step 5: 「買い目一括処理」 ウィンドウから IPAT 投票を起動

    多段 fallback (Session 128):
      1. menu   - ウィンドウメニューから IPAT 起動項目を探して WM_COMMAND
                  (★ Session 128 ライブ検証で確定: ﾌｧｲﾙ→IPATで投票する(&B) id=1601 受付番号 0045)
      2. uia    - UIA backend で Button 検索 click (Delphi VCL は UIA で見える可能性)
      3. win32  - Win32 TButton/TSpeedButton 直 click (Session 127 で失敗確認済)
      4. shortcut - キーボードショートカット試行 (Ctrl+I 等、 候補を順次)
      5. coords - 既知座標 click (coords.json 必要、 最終手段)

    Args:
        strategies: 試行する戦略の順序リスト。 None なら ["menu", "uia", "win32", "shortcut", "coords"]
                    (menu を先頭にしたのは Session 128 ライブ検証で WM_COMMAND 1601 が即動作確認済)
    """
    win = _wait_window(WIN_BATCH_PROCESS_RE, by_regex=True, timeout=timeout)
    if win is None:
        _vp(verbose, f"batch window {WIN_BATCH_PROCESS_RE!r} not found")
        return False
    _vp(verbose, "buy-list batch window detected (step3)")
    win.set_focus()
    time.sleep(0.3)

    # DEBUG: 全ボタン候補を列挙
    if verbose:
        try:
            seen = set()
            for child in win.descendants():
                try:
                    cls = child.class_name() or ""
                    if "Button" in cls or "BitBtn" in cls or "Speed" in cls:
                        txt = child.window_text() or ""
                        key = (cls, txt)
                        if key in seen:
                            continue
                        seen.add(key)
                        _vp(verbose, f"  button candidate: class={cls!r:20} text={txt!r}")
                except Exception:
                    continue
        except Exception as e:
            _vp(verbose, f"  (button enum failed: {e})")

    if strategies is None:
        strategies = ["menu", "uia", "win32", "shortcut", "coords"]

    strategy_fns = {
        "win32":    lambda: _try_ipat_via_win32(win, verbose=verbose),
        "uia":      lambda: _try_ipat_via_uia(verbose=verbose),
        "menu":     lambda: _try_ipat_via_menu(win, verbose=verbose),
        "shortcut": lambda: _try_ipat_via_shortcut(win, verbose=verbose),
        "coords":   lambda: _try_ipat_via_coords(win, verbose=verbose),
    }

    for s in strategies:
        fn = strategy_fns.get(s)
        if fn is None:
            _vp(verbose, f"  unknown strategy: {s}")
            continue
        _vp(verbose, f"--- strategy: {s} ---")
        try:
            result = fn()
        except Exception as e:
            _vp(verbose, f"  strategy {s} raised: {type(e).__name__}: {e}")
            result = None
        if result:
            _vp(verbose, f"clicked via [{result}]")
            time.sleep(0.5)
            return True

    _vp(verbose, "IPAT 投票起動: 全戦略失敗")
    return False


def save_ipat_coords(x_offset: int, y_offset: int,
                     *, verbose: bool = True) -> Path:
    """開催中の inspect 結果から「IPAT投票」 ボタンの座標を保存

    使い方:
      1. TARGET で 「買い目一括処理」 ウィンドウを開く
      2. python -m ml.target_clicker.menu_runner inspect-batch でスクショ取得
      3. PNG をデスクトップで開いて「IPAT投票」 ボタンのピクセル座標を測る
      4. python -m ml.target_clicker.menu_runner save-coords --x 120 --y 60
    """
    win = _wait_window(WIN_BATCH_PROCESS_RE, by_regex=True, timeout=5)
    if win is None:
        raise RuntimeError("買い目一括処理 ウィンドウが見つかりません — TARGET 起動して開いてください")
    rect = win.rectangle()
    win_w = rect.right - rect.left
    win_h = rect.bottom - rect.top
    COORDS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if COORDS_CONFIG_PATH.exists():
        with open(COORDS_CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    data["ipat_button"] = {
        "x_offset": int(x_offset),
        "y_offset": int(y_offset),
        "captured_at": datetime.now().isoformat(timespec="seconds"),
        "window_size": [win_w, win_h],
    }
    with open(COORDS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if verbose:
        print(f"saved: {COORDS_CONFIG_PATH}")
        print(f"  ipat_button = ({x_offset}, {y_offset}) on window {win_w}x{win_h}")
    return COORDS_CONFIG_PATH


def open_ff_and_start_ipat(ff_path: Path, *, verbose: bool = True) -> bool:
    """ワンショット: FF CSV 取り込み → IPAT 投票起動

    順序の重要事項 (2026-05-24 ふくだ環境観察):
      取り込み確定 (OK F10 + 「はい」) を先に押すと
      「買い目一括処理」 ウィンドウが閉じるため IPAT 投票ボタンに到達できない。
      → 投票を先に行い、 TARGET への買い目保存は投票後に別途実行する。

    投票内容確認ダイアログが出るところまで進める。
    click は target_clicker.auto_vote.click_vote_button() で行う。
    """
    if not step1_open_csv_select(ff_path, verbose=verbose):
        return False
    # step2 (取り込み確定) は ここではやらない — ウィンドウが閉じてしまう
    if not step3_start_ipat(verbose=verbose):
        return False
    return True


def finalize_save_to_target(*, verbose: bool = True) -> bool:
    """投票完了後に呼ぶ: 「買い目一括処理」 ウィンドウから OK F10 + 「はい」 で
    TARGET 買い目データに保存する。 投票内容と無関係に呼べる。
    """
    return step2_confirm_import(verbose=verbose)


# =====================================================================
# CLI
# =====================================================================

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("inspect", help="可視ウィンドウとメニュー構造を inspect")

    p_inspect_dlg = sub.add_parser("inspect-dialog",
                                    help="指定タイトルのダイアログ child を全列挙")
    p_inspect_dlg.add_argument("title", help="例: '買い目CSV形式ファイルの選択'")

    p_inspect_batch = sub.add_parser(
        "inspect-batch",
        help="Session 128: 「買い目一括処理」 ウィンドウを Win32+UIA 両方で dump (JSON+PNG 保存)",
    )
    p_inspect_batch.add_argument("--no-png", action="store_true",
                                  help="スクリーンショット保存をスキップ")

    p_load = sub.add_parser("load", help="Step1-2: FF CSV ファイル選択ダイアログまで操作")
    p_load.add_argument("ff_csv", type=Path)

    p_confirm = sub.add_parser("confirm-import",
                                help="Step3-4: 取り込み確定 + 「はい」 click")

    p_ipat = sub.add_parser("start-ipat",
                             help="Step5: [IPAT投票] ボタン click (多段 fallback)")
    p_ipat.add_argument("--strategies", default=None,
                        help="試行順序 (カンマ区切り、 default=uia,menu,win32,shortcut,coords)")

    p_coords = sub.add_parser("save-coords",
                               help="「IPAT投票」 ボタンの座標を coords.json に保存")
    p_coords.add_argument("--x", type=int, required=True, help="ウィンドウ左上からの X オフセット")
    p_coords.add_argument("--y", type=int, required=True, help="ウィンドウ左上からの Y オフセット")

    p_run = sub.add_parser("run", help="Step1-5 ワンショット: 取り込み → 保存 → IPAT 起動")
    p_run.add_argument("ff_csv", type=Path)

    args = p.parse_args()
    if args.cmd is None or args.cmd == "inspect":
        inspect_target_windows()
        print()
        print("=== TARGET window menu ===")
        w = find_target_window()
        if w is None:
            print("(TARGET window not found)")
        else:
            print(f"target window handle={w.handle:08x} text={w.window_text()!r}")
            print_menu_structure(w)
    elif args.cmd == "inspect-dialog":
        inspect_dialog(args.title)
    elif args.cmd == "inspect-batch":
        inspect_batch_window(save_png=not args.no_png)
    elif args.cmd == "load":
        ok = step1_open_csv_select(args.ff_csv)
        sys.exit(0 if ok else 1)
    elif args.cmd == "confirm-import":
        ok = step2_confirm_import()
        sys.exit(0 if ok else 1)
    elif args.cmd == "start-ipat":
        strategies = (args.strategies.split(",")
                       if args.strategies else None)
        ok = step3_start_ipat(strategies=strategies)
        sys.exit(0 if ok else 1)
    elif args.cmd == "save-coords":
        save_ipat_coords(args.x, args.y)
    elif args.cmd == "run":
        ok = open_ff_and_start_ipat(args.ff_csv)
        sys.exit(0 if ok else 1)
