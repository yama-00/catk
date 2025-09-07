from catk.dedup import is_dup

def test_hash_dup():
    a = {"id": "A001", "url": "http://x/y"}
    b = {"id": "A001", "url": "http://x/y"}
    assert is_dup(a, {("id", "url")}, [b])  # ← {b} を [b] に修正
