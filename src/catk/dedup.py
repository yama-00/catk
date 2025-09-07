from __future__ import annotations
from typing import Iterable, Tuple

KeySet = Iterable[Tuple[str, ...]]

def is_dup(row: dict, keysets: KeySet, existing_rows: Iterable[dict]) -> bool:
    """
    keysets のいずれかのキー組み合わせが一致すれば重複。
    例: keysets = {("id","url")}
    """
    existing = list(existing_rows)
    for keys in keysets:
        probe = tuple(row.get(k) for k in keys)
        for ex in existing:
            if tuple(ex.get(k) for k in keys) == probe:
                return True
    return False
