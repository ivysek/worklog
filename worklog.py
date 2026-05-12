#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimalistický logger práce:
- Po spuštění se zeptá na interval v minutách (default 10).
- V intervalu ukazuje centered popup (Tkinter) s otázkou "Co dělám?"
- Odpověď uloží jako řádek do CSV: timestamp;activity
- CSV je psané jako UTF-8 s BOM + oddělovač ; => Excel (CZ) typicky otevře správně.

Kde upravit:
- LOG_DIR: kam ukládat logy
- FILE_PER: "month" nebo "day" (soubor po měsíci / po dni)
"""

from __future__ import annotations

import csv
import datetime as dt
import os
import sys
import time

# ---- Nastavení, které dává smysl držet nahoře ----
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "worklog_logs")
FILE_PER = "month"  # "month" nebo "day"
DEFAULT_INTERVAL_MIN = 10


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def safe_makedirs(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as exc:
        raise RuntimeError(f"Nepodařilo se vytvořit složku '{path}': {exc}") from exc


def log_path(now: dt.datetime) -> str:
    if FILE_PER == "day":
        name = f"worklog_{now:%Y-%m-%d}.csv"
    else:
        # default: po měsíci (přehledné pro týden/měsíc)
        name = f"worklog_{now:%Y-%m}.csv"
    return os.path.join(LOG_DIR, name)


def ensure_csv_header(path: str) -> None:
    """
    Když soubor neexistuje nebo je prázdný, zapíšeme hlavičku.
    Používám UTF-8 s BOM, protože Excel na Windows často jinak hádá špatné kódování.
    """
    try:
        needs_header = (not os.path.exists(path)) or (os.path.getsize(path) == 0)
    except OSError:
        needs_header = True

    if not needs_header:
        return

    safe_makedirs(os.path.dirname(path))
    try:
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["timestamp", "activity"])
    except Exception as exc:
        raise RuntimeError(f"Nelze zapsat hlavičku do '{path}': {exc}") from exc


def append_row(path: str, timestamp: str, activity: str) -> None:
    ensure_csv_header(path)
    try:
        with open(path, "a", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow([timestamp, activity])
    except Exception as exc:
        raise RuntimeError(f"Nelze zapsat do '{path}': {exc}") from exc


def ask_interval_minutes() -> int:
    """
    Zeptá se v konzoli; default je 10. Nepustí mínusové číslo.
    """
    while True:
        raw = input(f"Interval v minutách [default {DEFAULT_INTERVAL_MIN}]: ").strip()
        if raw == "":
            return DEFAULT_INTERVAL_MIN
        try:
            val = int(raw)
            if val <= 0:
                print("Zadej kladné číslo minut.")
                continue
            return val
        except ValueError:
            print("Zadej celé číslo (např. 10).")


def ask_activity_popup() -> str | None:
    """
    Centered Tk popup. Vrací text nebo None, když uživatel dá Cancel / zavře okno.
    """
    try:
        import tkinter as tk
    except Exception as exc:
        eprint(f"[CHYBA] Tkinter není dostupný: {exc}")
        eprint("Tip: Na některých Linux distribucích je potřeba doinstalovat balíček python3-tk.")
        return None

    root = tk.Tk()
    root.title("Worklog")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    # Proč vlastní dialog: simpledialog je ok, ale hůř se ladí centering a ovládání Enter/Esc.
    question = tk.Label(root, text="Co dělám?", font=("Segoe UI", 11))
    question.pack(padx=14, pady=(12, 6))

    entry = tk.Entry(root, width=56, font=("Segoe UI", 11))
    entry.pack(padx=14, pady=(0, 10))
    entry.focus_set()

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=(0, 12))

    result: dict[str, str | None] = {"value": None}

    def submit() -> None:
        result["value"] = entry.get().strip()
        root.destroy()

    def cancel() -> None:
        result["value"] = None
        root.destroy()

    ok_btn = tk.Button(btn_frame, text="Uložit", width=10, command=submit)
    ok_btn.pack(side="left", padx=6)
    cancel_btn = tk.Button(btn_frame, text="Konec", width=10, command=cancel)
    cancel_btn.pack(side="left", padx=6)

    # Enter = uložit, Esc = konec
    root.bind("<Return>", lambda _e: submit())
    root.bind("<Escape>", lambda _e: cancel())

    # Center window (po vykreslení zjistíme rozměry)
    root.update_idletasks()
    w = root.winfo_width()
    h = root.winfo_height()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x = int((sw - w) / 2)
    y = int((sh - h) / 2)
    root.geometry(f"{w}x{h}+{x}+{y}")

    root.mainloop()
    return result["value"]


def main() -> int:
    try:
        interval_min = ask_interval_minutes()
    except (KeyboardInterrupt, EOFError):
        print("\nUkončeno.")
        return 0

    safe_makedirs(LOG_DIR)

    print(f"[INFO] Interval: {interval_min} min")
    print(f"[INFO] Kam se ukládají logy: {LOG_DIR}")
    print("[INFO] Ukončení:")
    print("       - v okně: tlačítko Konec / Esc / zavřít okno")
    print("       - v konzoli: Ctrl+C")
    print("-" * 50)

    # První dotaz hned (ne až za interval) – praktické, aby log začal okamžitě. Napiš třeba "začínám pracovat".
    next_sleep = 0

    while True:
        if next_sleep > 0:
            time.sleep(next_sleep)

        now = dt.datetime.now()
        activity = ask_activity_popup()

        if activity is None:
            print("[INFO] Ukončeno uživatelem.")
            return 0

        if activity == "":
            activity = "(bez odpovědi)"

        ts = now.strftime("%Y-%m-%d %H:%M:%S")
        path = log_path(now)

        try:
            append_row(path, ts, activity)
        except Exception as exc:
            eprint(f"[CHYBA] {exc}")
            eprint("[INFO] Pokračuji dál (aby ses nezasekla), ale zkontroluj práva / disk.")
        else:
            print(f"[OK] {ts}  {activity}")

        next_sleep = max(1, interval_min * 60)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nUkončeno.")
        raise SystemExit(0)
