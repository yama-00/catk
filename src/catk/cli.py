# src/catk/cli.py
from pathlib import Path
import argparse, logging, time

from .io import read_csv, writer
from .core import (
    FIELDNAMES,
    clean_row,
    has_minimum_keys,
    DedupeState,
    read_many_csv,
    preprocess,
    make_pivots,
    export_outputs,
    load_config,
    scrape_once,
)


def main() -> None:
    ROOT = Path(__file__).resolve().parents[2]
    IN = ROOT / "examples" / "project1.csv"
    OUT = ROOT / "clean.csv"
    DUP = ROOT / "duplicates.csv"
    BAD = ROOT / "invalid_rows.csv"

    parser = argparse.ArgumentParser(prog="catk", description="CSV Automation Toolkit")
    sub = parser.add_subparsers(dest="cmd")  # 3.11以降なら required=True でもOK

    # clean
    s1 = sub.add_parser("clean", help="プロジェクト1: CSVクレンジング")
    s1.add_argument("--in", dest="in_path", default=str(IN))
    s1.add_argument("--out", dest="out_path", default=str(OUT))
    s1.add_argument("--dup", dest="dup_path", default=str(DUP))
    s1.add_argument("--bad", dest="bad_path", default=str(BAD))
    s1.add_argument("--encoding", default="utf-8-sig")

    # report
    s2 = sub.add_parser("report", help="プロジェクト2: 複数CSV統合 & Excelレポート")
    s2.add_argument("--glob", default="examples/sales/*.csv")
    s2.add_argument("--encoding", default="utf-8-sig")
    s2.add_argument("--outdir", default=str(ROOT / "out"))

    # scrape（1回）
    s3 = sub.add_parser("scrape", help="プロジェクト3: スクレイピング（1回実行）")
    s3.add_argument("--config", default="configs/scrape.yml")

    # scrape-daemon（常駐）
    s4 = sub.add_parser(
        "scrape-daemon", help="プロジェクト3: スクレイピング（常駐実行）"
    )
    s4.add_argument("--config", default="configs/scrape.yml")
    s4.add_argument("--interval", type=int, default=60, help="分間隔")

    args = parser.parse_args()

    if args.cmd == "clean":
        rows = read_csv(args.in_path, encoding=args.encoding)
        f_out, w_clean = writer(args.out_path, FIELDNAMES, args.encoding)
        f_dup, w_dup = writer(args.dup_path, FIELDNAMES + ["dup_reason"], args.encoding)
        orig_fields = list(rows[0].keys()) if rows else FIELDNAMES
        f_bad, w_bad = writer(args.bad_path, orig_fields, args.encoding)
        dedupe = DedupeState(key="email")
        try:
            for raw in rows:
                if not has_minimum_keys(raw):
                    w_bad.writerow(raw)
                    continue
                row = clean_row(raw)
                if dedupe.is_duplicate(row):
                    w_dup.writerow({**row, "dup_reason": "email"})
                    continue
                w_clean.writerow(row)
        finally:
            f_out.close()
            f_dup.close()
            f_bad.close()

    elif args.cmd == "report":
        out_dir = Path(args.outdir)
        out_dir.mkdir(parents=True, exist_ok=True)
        files = sorted(Path().glob(args.glob))
        if not files:
            print(f"[report] 対象がありません: {args.glob}")
            raise SystemExit(0)
        df = read_many_csv(files, encoding=args.encoding)
        df = preprocess(df)
        piv = make_pivots(df)
        export_outputs(df, piv, out_dir / "merged.csv", out_dir / "report.xlsx")
        print(f"[report] merged.csv / report.xlsx -> {out_dir.resolve()}")

    elif args.cmd == "scrape":
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
        )
        conf = load_config(args.config)
        added = scrape_once(conf)
        print(f"新規追加: {added} 件")

    elif args.cmd == "scrape-daemon":
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
        )
        conf = load_config(args.config)
        print(f"常駐開始（{args.interval}分間隔）… Ctrl+C で停止")
        try:
            while True:
                added = scrape_once(conf)
                logging.info(f"ループ完了：{added}件 追加")
                time.sleep(max(10, args.interval * 60))
        except KeyboardInterrupt:
            logging.info("Ctrl+C 受信：終了")

    else:
        # 何も指定されなければデフォルト動作（任意）
        rows = read_csv(str(IN))
        f_out, w_clean = writer(str(OUT), FIELDNAMES)
        f_dup, w_dup = writer(str(DUP), FIELDNAMES + ["dup_reason"])
        f_bad, w_bad = writer(str(BAD), FIELDNAMES)
        for r in rows:
            w_clean.writerow(clean_row(r))
        f_out.close()
        f_dup.close()
        f_bad.close()


# 直接 python src/catk/cli.py でも動くように（任意）
if __name__ == "__main__":
    main()
