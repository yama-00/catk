# src/catk/fileio.py
import csv
import logging
from pathlib import Path
from typing import List


def read_csv(path: str, encoding: str = "utf-8-sig") -> list[dict]:
    p = Path(path)
    if not p.exists():
        logging.error(f"入力ファイルが見つかりません: {p}")
        raise FileNotFoundError(p)
    try:
        with p.open("r", newline="", encoding=encoding) as f:
            rows = list(csv.DictReader(f))
            logging.info(f"read_csv: {p} 行数={len(rows)} enc={encoding}")
            return rows
    except UnicodeDecodeError:
        logging.exception(f"文字コードの読み込みに失敗: {p} enc={encoding}")
        raise
    except Exception:
        logging.exception(f"CSV読み込みに失敗: {p}")
        raise


def writer(path: str, fieldnames: List[str], encoding: str = "utf-8-sig"):
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        f = p.open("w", newline="", encoding=encoding)
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        logging.info(f"writer: 出力開始 -> {p} enc={encoding} cols={fieldnames}")
        return f, w
    except Exception:
        logging.exception(f"CSV書き込みオープンに失敗: {p}")
        raise
