from __future__ import annotations

def _to_int_if_number(s: str):
    num = s.replace(",", "")
    return int(num) if num.isdigit() else s

def clean_row(row: dict) -> dict:
    """半角/全角空白の除去、空文字の正規化、カンマ付き数字→int。"""
    out: dict = {}
    for k, v in row.items():
        if v is None:
            out[k] = ""
            continue
        if isinstance(v, str):
            s = v.replace("\u3000", "").strip()  # 全角スペース→削除 & trim
            if s == "":
                out[k] = ""
            else:
                out[k] = _to_int_if_number(s)
        else:
            out[k] = v
    return out
