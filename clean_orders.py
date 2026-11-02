"""合成数据演示：保留原始 CSV，按公开规则清洗并隔离异常。Python 3.10+，仅标准库。"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

FIELDS = ["order_id", "order_date", "channel", "product", "amount_cny", "status"]
STATUSES = {"已支付", "已退款", "待支付"}
DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日")
MONEY_RE = re.compile(r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?\Z")


def parse_date(text: str) -> str:
    if not re.match(r"^\d{4}(?:[-/]|年)", text):
        raise ValueError("日期缺少年份前置的明确格式，未猜测日/月顺序")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError("日期不存在或格式不受支持")


def parse_money(text: str) -> Decimal:
    value = text.strip()
    for prefix in ("CNY", "￥", "¥"):
        if value.startswith(prefix):
            value = value[len(prefix):].strip()
            break
    if value.endswith("元"):
        value = value[:-1].strip()
    if not MONEY_RE.fullmatch(value):
        raise ValueError("金额为空、分组错误、为负数或超过两位小数")
    try:
        return Decimal(value.replace(",", "")).quantize(Decimal("0.01"))
    except InvalidOperation as exc:
        raise ValueError("金额无法解析") from exc


def csv_write(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def process(input_path: Path, output_dir: Path) -> dict:
    output_names = {"clean_orders.csv", "exceptions.csv", "duplicates.csv", "row_ledger.csv", "channel_summary.csv", "audit.json"}
    if input_path.resolve().parent == output_dir.resolve() and input_path.name in output_names:
        raise ValueError("输出目录会覆盖输入文件，请选择其他目录")
    source_bytes = input_path.read_bytes()
    with input_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise ValueError(f"列名及顺序必须为 {FIELDS}")
        raw = list(reader)

    prepared = []
    for line, record in enumerate(raw, start=2):
        if None in record or any(value is None for value in record.values()):
            raise ValueError(f"源文件第 {line} 行字段数量错误")
        clean = {key: record[key].strip() for key in FIELDS}
        issues = []
        if not clean["order_id"]:
            issues.append("订单号缺失")
        if not clean["channel"]:
            issues.append("渠道缺失")
        if not clean["product"]:
            issues.append("商品名缺失")
        try:
            clean["order_date"] = parse_date(clean["order_date"])
        except ValueError as exc:
            issues.append(str(exc))
        try:
            clean["amount_cny"] = str(parse_money(clean["amount_cny"]))
        except ValueError as exc:
            issues.append(str(exc))
        if clean["status"] not in STATUSES:
            issues.append("状态不在已支付/已退款/待支付范围内")
        prepared.append({"source_line": line, "raw": record, "clean": clean, "issues": issues})

    # 本演示明确规定：一个订单号对应一条订单记录。相同 ID 内容冲突时全部隔离。
    by_id = defaultdict(list)
    for row in prepared:
        if row["clean"]["order_id"]:
            by_id[row["clean"]["order_id"]].append(row)
    conflict_ids = {
        key for key, group in by_id.items()
        if len({tuple(row["clean"][field] for field in FIELDS) for row in group}) > 1
    }

    clean_rows, exception_rows, duplicate_rows, ledger = [], [], [], []
    first_line = {}
    for row in prepared:
        clean = row["clean"]
        line = row["source_line"]
        issues = list(row["issues"])
        if clean["order_id"] in conflict_ids:
            issues.append("同订单号内容冲突，全部隔离等待确认")
        if issues:
            reason = "；".join(issues)
            exception_rows.append({"source_line": line, **row["raw"], "reason": reason})
            disposition = "异常隔离"
        else:
            key = tuple(clean[field] for field in FIELDS)
            if key in first_line:
                reason = f"标准化后全字段一致，保留源文件第 {first_line[key]} 行"
                duplicate_rows.append({"source_line": line, **row["raw"], "kept_source_line": first_line[key], "reason": reason})
                disposition = "重复留痕"
            else:
                first_line[key] = line
                clean_rows.append({"source_line": line, **clean})
                disposition, reason = "纳入干净数据", "格式标准化，字段校验通过"
        ledger.append({"source_line": line, "order_id": clean["order_id"], "disposition": disposition, "reason": reason})

    summary = []
    for channel in sorted({row["channel"] for row in clean_rows}):
        channel_rows = [row for row in clean_rows if row["channel"] == channel]
        result = {"channel": channel}
        for status, prefix in (("已支付", "paid"), ("已退款", "refunded"), ("待支付", "unpaid")):
            selected = [row for row in channel_rows if row["status"] == status]
            result[prefix + "_orders"] = len(selected)
            result[prefix + "_amount_cny"] = str(sum((Decimal(row["amount_cny"]) for row in selected), Decimal("0.00")))
        summary.append(result)

    totals = {}
    for status, prefix in (("已支付", "paid"), ("已退款", "refunded"), ("待支付", "unpaid")):
        selected = [row for row in clean_rows if row["status"] == status]
        totals[prefix + "_orders"] = len(selected)
        totals[prefix + "_amount_cny"] = str(sum((Decimal(row["amount_cny"]) for row in selected), Decimal("0.00")))
    audit = {
        "data_notice": "全部数据为合成演示，不代表真实客户、销售或收入。",
        "source_file": input_path.name,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_rows": len(raw),
        "clean_rows": len(clean_rows),
        "exception_rows": len(exception_rows),
        "duplicate_rows": len(duplicate_rows),
        "row_conservation": len(raw) == len(clean_rows) + len(exception_rows) + len(duplicate_rows),
        "conflict_order_ids": sorted(conflict_ids),
        "totals": totals,
        "summary": summary,
        "clean_orders": clean_rows,
        "exceptions": exception_rows,
        "duplicates": duplicate_rows,
        "raw_orders": [{"source_line": line, **row} for line, row in enumerate(raw, 2)],
        "limitations": "汇总仅覆盖校验通过且去重后的记录。异常金额未估计。已退款记录额单列，不计算净收入或推断退款额。",
    }
    assert audit["row_conservation"]
    assert len({row["order_id"] for row in clean_rows}) == len(clean_rows)
    assert len({row["source_line"] for row in ledger}) == len(raw)
    for prefix in ("paid", "refunded", "unpaid"):
        assert sum((Decimal(row[prefix + "_amount_cny"]) for row in summary), Decimal("0.00")) == Decimal(totals[prefix + "_amount_cny"])

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_write(output_dir / "clean_orders.csv", ["source_line"] + FIELDS, clean_rows)
    csv_write(output_dir / "exceptions.csv", ["source_line"] + FIELDS + ["reason"], exception_rows)
    csv_write(output_dir / "duplicates.csv", ["source_line"] + FIELDS + ["kept_source_line", "reason"], duplicate_rows)
    csv_write(output_dir / "row_ledger.csv", ["source_line", "order_id", "disposition", "reason"], ledger)
    csv_write(output_dir / "channel_summary.csv", ["channel", "paid_orders", "paid_amount_cny", "refunded_orders", "refunded_amount_cny", "unpaid_orders", "unpaid_amount_cny"], summary)
    (output_dir / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=Path(__file__).with_name("raw_orders.csv"))
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("output"))
    args = parser.parse_args()
    audit = process(args.input.resolve(), args.out.resolve())
    print(json.dumps({key: audit[key] for key in ("source_rows", "clean_rows", "exception_rows", "duplicate_rows", "row_conservation", "totals")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
