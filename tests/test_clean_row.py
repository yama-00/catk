# tests/test_clean_row.py
from catk.clean import clean_row


def test_trim_and_normalize():
    row = {"name": "  山田  ", "price": "1,000", "note": "\u3000"}
    out = clean_row(row)
    assert out["name"] == "山田"
    assert out["price"] == 1000
    assert out["note"] == ""
