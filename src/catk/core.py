# src/catk/core.py
from __future__ import annotations
import csv, logging, re, time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

# ====== 基本整形・クレンジング・重複 ======
_RE_PHONE = re.compile(r"\D+")
FIELDNAMES = ["name", "address", "phone", "email", "age"]


def strip_all(s: Optional[str]) -> str:
    if s is None:
        return ""
    return str(s).replace("\u3000", " ").strip()


def normalize_phone(s: str) -> str:
    return _RE_PHONE.sub("", strip_all(s))


def normalize_email(s: str) -> str:
    return strip_all(s).lower()


def to_int_or_empty(s: str) -> str:
    s = strip_all(s)
    return s if s.isdigit() else ""


def clean_row(row: dict) -> dict:
    return {
        "name": strip_all(row.get("name")),
        "address": strip_all(row.get("address")),
        "phone": normalize_phone(row.get("phone", "")),
        "email": normalize_email(row.get("email", "")),
        "age": to_int_or_empty(row.get("age", "")),
    }


def has_minimum_keys(row: dict) -> bool:
    return any(strip_all(row.get(k)) for k in ("email", "phone", "name"))


class DedupeState:
    def __init__(self, key: str = "email") -> None:
        self.key = key
        self.seen: set[str] = set()

    def is_duplicate(self, row: dict) -> bool:
        val = strip_all(row.get(self.key, ""))
        if not val:
            return False
        if val in self.seen:
            return True
        self.seen.add(val)
        return False


# ====== レポート（複数CSV統合 & Excel出力） ======
import pandas as pd  # 重い依存はここでimport

REQUIRED_COLS = ["date", "store", "product", "qty", "price"]


def read_many_csv(paths: Iterable[Path], encoding: str = "utf-8-sig") -> pd.DataFrame:
    frames = []
    for p in paths:
        try:
            p = Path(p)
            if not p.exists():
                logging.error(f"[report] ファイルなし: {p}")
                continue
            df = pd.read_csv(p, encoding=encoding)
            for col in REQUIRED_COLS:
                if col not in df.columns:
                    df[col] = None
            frames.append(df[REQUIRED_COLS])
            logging.info(f"[report] 読み込み: {p} 行数={len(df)}")
        except UnicodeDecodeError:
            logging.exception(f"[report] エンコード不一致: {p} enc={encoding}")
        except Exception:
            logging.exception(f"[report] 読み込み失敗: {p}")
    if not frames:
        logging.warning("[report] 対象データが空です")
        return pd.DataFrame(columns=REQUIRED_COLS)
    out = pd.concat(frames, ignore_index=True)
    logging.info(f"[report] 統合完了 行数={len(out)}")
    return out


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df["qty"] = pd.to_numeric(df["qty"], errors="coerce").fillna(0).astype(int)
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0)
    df["amount"] = df["qty"] * df["price"]
    return df


def make_pivots(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    by_store = (
        df.groupby("store", dropna=False)["amount"]
        .sum()
        .reset_index()
        .sort_values("amount", ascending=False)
    )
    by_product = (
        df.groupby("product", dropna=False)["amount"]
        .sum()
        .reset_index()
        .sort_values("amount", ascending=False)
    )
    by_date = (
        df.groupby("date", dropna=False)["amount"]
        .sum()
        .reset_index()
        .sort_values("date")
    )
    return {"ByStore": by_store, "ByProduct": by_product, "ByDate": by_date}


def export_outputs(
    merged: pd.DataFrame,
    pivots: dict[str, pd.DataFrame],
    merged_path: Path,
    report_xlsx: Path,
) -> None:
    try:
        merged_path.parent.mkdir(parents=True, exist_ok=True)
        merged.to_csv(merged_path, index=False, encoding="utf-8-sig")
        with pd.ExcelWriter(report_xlsx, engine="xlsxwriter") as xw:
            for name, df in pivots.items():
                df.to_excel(xw, sheet_name=name, index=False)
        logging.info(f"[report] 出力: merged={merged_path} report={report_xlsx}")
    except Exception:
        logging.exception(
            f"[report] 出力に失敗: merged={merged_path} report={report_xlsx}"
        )
        raise


# ====== スクレイピング（1回/常駐） ======
import requests, yaml
from bs4 import BeautifulSoup


@dataclass
class SiteSpec:
    name: str
    url: str
    list_selector: str
    item_selector: str
    title_selector: str
    link_attr: str = "href"
    base_url: str = ""


@dataclass
class ScrapeConfig:
    output_csv: str
    encoding: str = "utf-8-sig"
    user_agent: str = "CATK/1.0"
    timeout_sec: int = 10
    retry: int = 2
    sleep_sec: float = 1.0
    sites: list[SiteSpec] = None


def load_config(path: str | Path) -> ScrapeConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    sites = [SiteSpec(**s) for s in raw.get("sites", [])]
    return ScrapeConfig(
        output_csv=raw["output_csv"],
        encoding=raw.get("encoding", "utf-8-sig"),
        user_agent=raw.get("user_agent", "CATK/1.0"),
        timeout_sec=int(raw.get("timeout_sec", 10)),
        retry=int(raw.get("retry", 2)),
        sleep_sec=float(raw.get("sleep_sec", 1.0)),
        sites=sites,
    )


def _ensure_parent(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def _read_seen_urls(csv_path: Path, encoding: str) -> set[str]:
    if not csv_path.exists():
        return set()
    seen = set()
    with open(csv_path, "r", newline="", encoding=encoding) as f:
        for row in csv.DictReader(f):
            if "url" in row and row["url"]:
                seen.add(row["url"])
    return seen


def _append_rows(csv_path: Path, rows: Iterable[dict], encoding: str) -> None:
    rows = list(rows)
    if not rows:
        return
    _ensure_parent(csv_path)
    header = ["fetched_at", "site", "title", "url"]
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding=encoding) as f:
        w = csv.DictWriter(f, fieldnames=header)
        if write_header:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def _fetch_text(url: str, ua: str, timeout: int, retry: int) -> str:
    parsed = urlparse(url)
    if parsed.scheme == "file":
        p = Path(parsed.path.lstrip("/"))
        return p.read_text(encoding="utf-8")
    headers = {"User-Agent": ua}
    last_err = None
    for _ in range(max(1, retry + 1)):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or resp.encoding
            return resp.text
        except Exception as e:
            last_err = e
            time.sleep(0.8)
    raise last_err


def _parse_items(html: str, spec: SiteSpec) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(spec.list_selector)
    if not container:
        return []
    out: list[tuple[str, str]] = []
    for el in container.select(spec.item_selector):
        t = el.select_one(spec.title_selector)
        if not t:
            continue
        title = (t.get_text() or "").strip()
        href = t.get(spec.link_attr, "").strip()
        if not href:
            continue
        url_abs = urljoin(spec.base_url or spec.url, href)
        out.append((title, url_abs))
    return out


def scrape_once(conf: ScrapeConfig) -> int:
    t0 = time.time()
    csv_path = Path(conf.output_csv)
    seen = _read_seen_urls(csv_path, conf.encoding)
    new_rows: list[dict] = []
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    total_items = 0

    for spec in conf.sites:
        try:
            html = _fetch_text(spec.url, conf.user_agent, conf.timeout_sec, conf.retry)
            items = _parse_items(html, spec)
            total_items += len(items)
            added = 0
            for title, url in items:
                if url in seen:
                    continue
                new_rows.append(
                    {"fetched_at": now, "site": spec.name, "title": title, "url": url}
                )
                seen.add(url)
                added += 1
            logging.info(f"[{spec.name}] 取得={len(items)} 新規={added}")
            time.sleep(conf.sleep_sec)
        except Exception:
            logging.exception(f"[{spec.name}] 取得失敗")

    _append_rows(csv_path, new_rows, conf.encoding)
    logging.info(
        f"scrape_once: 新規追加={len(new_rows)} 全候補={total_items} 所要={time.time() - t0:.2f}s 出力={csv_path}"
    )
    return len(new_rows)
