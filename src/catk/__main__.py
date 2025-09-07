# src/catk/__main__.py

# どちらでも動くように：まず絶対インポート、失敗したら相対
try:
    from catk.cli import main
except ImportError:  # 開発中に python -m catk で動かす時など
    from .cli import main

if __name__ == "__main__":
    main()
