# src/catk/utils/paths.py
import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    """
    PyInstaller(OneFile)でも開発時でも同じ書き方で資材にアクセスする。
    relative はプロジェクト直下からの相対パス（例: 'configs/scrape.yml'）
    """
    if hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # PyInstallerの一時展開ディレクトリ
    else:
        # このファイル: src/catk/utils/paths.py → プロジェクト直下まで 3Up
        base = Path(__file__).resolve().parents[3]
    return (base / relative).resolve()
