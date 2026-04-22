#!/usr/bin/env python3
import json
import os
import sys
from snowflake_conn import execute_query, close
from queries import (reseller_subscriptions_query, partner_bookings_query,
                     partner_details_query, partner_open_pipeline_query,
                     sourced_pipeline_query)
from format import format_partner_report, _fiscal_quarter
from pdf_report import generate_pdf

ALIASES_PATH = os.path.join(os.path.dirname(__file__), "aliases.json")


def resolve_names(partner_name):
    try:
        with open(ALIASES_PATH) as f:
            aliases = json.load(f)
    except FileNotFoundError:
        return [partner_name]

    for key, names in aliases.items():
        if partner_name.lower() == key.lower():
            return names
        if partner_name.lower() in [n.lower() for n in names]:
            return names

    return [partner_name]


def main():
    partner_name = " ".join(sys.argv[1:]).strip()
    if not partner_name:
        print('Usage: python3 partner_lookup.py "Partner Name"')
        print('Example: python3 partner_lookup.py "Accenture"')
        sys.exit(1)

    search_names = resolve_names(partner_name)

    print(f"\nLooking up partner: {partner_name}")
    if len(search_names) > 1:
        print(f"  Including aliases: {', '.join(search_names)}")
    print("Connecting to Snowflake (SSO browser will open)...\n")

    print("  Running partner details query...")
    details = execute_query(partner_details_query(search_names))
    print(f"  Partner details: {len(details)} rows")

    print("  Running reseller subscriptions query...")
    subscriptions = execute_query(reseller_subscriptions_query(search_names))
    print(f"  Reseller query: {len(subscriptions)} rows")

    print("  Running bookings query...")
    bookings = execute_query(partner_bookings_query(search_names))
    print(f"  Bookings query: {len(bookings)} rows")

    print("  Running open pipeline query...")
    open_pipeline = execute_query(partner_open_pipeline_query(search_names))
    print(f"  Open pipeline: {len(open_pipeline)} rows")

    from datetime import date, timedelta
    today = date.today()
    fy, fq, cq_start, _ = _fiscal_quarter(today)
    fy1, fq1, cqm1_start, _ = _fiscal_quarter(cq_start - timedelta(days=1))
    fy2, fq2, _, _ = _fiscal_quarter(cqm1_start - timedelta(days=1))
    fiscal_quarters = [f"FY{fy2}Q{fq2}", f"FY{fy1}Q{fq1}", f"FY{fy}Q{fq}"]

    print(f"  Running sourced pipeline query ({', '.join(fiscal_quarters)})...")
    sourced = execute_query(sourced_pipeline_query(search_names, fiscal_quarters))
    print(f"  Sourced pipeline: {len(sourced)} rows")

    report = format_partner_report(partner_name, subscriptions, bookings,
                                   details=details, open_pipeline=open_pipeline,
                                   sourced_pipeline=sourced)
    print(report)

    print("\n  Generating PDF...")
    pdf_path = generate_pdf(partner_name, subscriptions, bookings,
                            details=details, open_pipeline=open_pipeline,
                            sourced_pipeline=sourced)
    print(f"  PDF saved: {pdf_path}")

    close()


if __name__ == "__main__":
    main()
