#!/usr/bin/env python3
import json
import os
import sys
import openpyxl
from snowflake_conn import get_connection, execute_query, close
from queries import (reseller_subscriptions_query, partner_bookings_query,
                     partner_details_query, partner_open_pipeline_query)
from format import format_partner_report
from pdf_report import generate_pdf

ALIASES_PATH = os.path.join(os.path.dirname(__file__), "aliases.json")
INPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "agent-input")


def load_aliases():
    try:
        with open(ALIASES_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def resolve_names(partner_name, aliases):
    for key, names in aliases.items():
        if partner_name.lower() == key.lower():
            return key, names
        if partner_name.lower() in [n.lower() for n in names]:
            return key, names
    return partner_name, [partner_name]


def extract_partners_from_excel():
    raw_names = set()
    for fname in os.listdir(INPUT_DIR):
        if not fname.endswith(".xlsx"):
            continue
        wb = openpyxl.load_workbook(os.path.join(INPUT_DIR, fname), read_only=True, data_only=True)
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                continue
            header = [str(c).strip().lower() if c else "" for c in rows[0]]
            name_col = None
            for i, h in enumerate(header):
                if "partner" in h and "name" in h:
                    name_col = i
                    break
            if name_col is None:
                continue
            for row in rows[1:]:
                val = row[name_col] if name_col < len(row) else None
                if val and str(val).strip():
                    raw_names.add(str(val).strip())
        wb.close()
    return raw_names


def deduplicate(raw_names, aliases):
    seen = set()
    partners = []
    for name in sorted(raw_names):
        display_name, search_names = resolve_names(name, aliases)
        key = display_name.lower()
        if key not in seen:
            seen.add(key)
            partners.append((display_name, search_names))
    return partners


def main():
    print("Reading Excel files from agent-input/...")
    raw_names = extract_partners_from_excel()
    print(f"  Found {len(raw_names)} raw partner names")

    aliases = load_aliases()
    partners = deduplicate(raw_names, aliases)
    print(f"  Deduplicated to {len(partners)} unique partners\n")

    for i, (display_name, search_names) in enumerate(partners, 1):
        label = display_name
        if len(search_names) > 1:
            label += f" (incl. {', '.join(n for n in search_names if n.lower() != display_name.lower())})"

        print(f"[{i}/{len(partners)}] {label}")

        try:
            details = execute_query(partner_details_query(search_names))
            subs = execute_query(reseller_subscriptions_query(search_names))
            bookings = execute_query(partner_bookings_query(search_names))
            open_pipe = execute_query(partner_open_pipeline_query(search_names))

            report = format_partner_report(display_name, subs, bookings,
                                           details=details, open_pipeline=open_pipe)
            print(report)

            pdf_path = generate_pdf(display_name, subs, bookings,
                                    details=details, open_pipeline=open_pipe)
            print(f"  PDF saved: {pdf_path}\n")
        except Exception as e:
            print(f"  ERROR: {e}\n")

    close()
    print("Done!")


if __name__ == "__main__":
    main()
