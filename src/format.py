from collections import defaultdict

PER_USD = {
    "USD": 1,
    "EUR": 0.8668,
    "GBP": 0.7603,
    "BRL": 5.377,
    "AUD": 1.27,
    "JPY": 118.45,
}


def to_usd(amount, currency):
    if not amount or not currency:
        return amount or 0
    rate = PER_USD.get(currency.upper().strip())
    if not rate:
        return amount
    return round(amount / rate, 2)


def usd(val):
    return f"${val:,.0f}"


def format_partner_report(partner_name, subscriptions, bookings,
                          details=None, open_pipeline=None):
    lines = []
    div = "═" * 70
    thin = "─" * 70

    lines.append("")
    lines.append(div)
    lines.append(f"  PARTNER SUMMARY: {partner_name.upper()}")
    lines.append(div)

    if details is not None:
        _format_partner_details(lines, details, thin)
        lines.append("")

    _format_book_of_business(lines, subscriptions, thin)
    lines.append("")
    _format_bookings(lines, bookings, thin)

    if open_pipeline is not None:
        lines.append("")
        _format_open_pipeline(lines, open_pipeline, thin)

    lines.append("")
    lines.append(div)
    return "\n".join(lines)


def _format_partner_details(lines, rows, divider):
    lines.append("")
    lines.append("  PARTNER DETAILS (Salesforce)")
    lines.append(divider)

    if not rows:
        lines.append("  No partner account found in Salesforce.")
        return

    for row in rows:
        lines.append("")
        lines.append(f"  Partner:          {row.get('PARTNER_NAME', 'N/A')}")
        lines.append(f"  Account Owner:    {row.get('ACCOUNT_OWNER', 'N/A')}")
        lines.append(f"  Type:             {row.get('ACCOUNT_TYPE', 'N/A')}")
        lines.append(f"  Partner Type:     {row.get('PARTNER_TYPE', 'N/A')}")
        lines.append(f"  Channel Category: {row.get('CHANNEL_CATEGORY', 'N/A')}")
        lines.append(f"  Partner Level:    {row.get('PARTNER_LEVEL', 'N/A')}")
        lines.append(f"  Status:           {row.get('PARTNER_STATUS', 'N/A')}")
        lines.append(f"  Agreement Signed: {row.get('SIGNED_AGREEMENT', 'N/A')}")
        agreement_date = row.get('AGREEMENT_DATE')
        lines.append(f"  Agreement Date:   {str(agreement_date)[:10] if agreement_date else 'N/A'}")
        lines.append(f"  Serviced Region:  {row.get('SERVICED_REGION', 'N/A')}")


def _format_open_pipeline(lines, rows, divider):
    lines.append("  3. OPEN PIPELINE (Stages 02-06)")
    lines.append(divider)

    if not rows:
        lines.append("  No open pipeline found.")
        return

    by_source = defaultdict(lambda: {"arr": 0, "count": 0})
    for row in rows:
        src = row.get("SOURCED_INFLUENCED") or row.get("PARTNER_DEAL_SOURCE") or "Unknown"
        by_source[src]["arr"] += row.get("PRODUCT_ARR_USD", 0) or 0
        by_source[src]["count"] += 1

    total_arr = sum(v["arr"] for v in by_source.values())
    total_deals = sum(v["count"] for v in by_source.values())

    lines.append("")
    lines.append(f"  Total Open Pipeline:  {usd(total_arr)}  ({total_deals} deals)")
    lines.append("")
    lines.append("  By Partner Deal Source:")
    for src, v in sorted(by_source.items(), key=lambda x: x[1]["arr"], reverse=True):
        lines.append(f"    {src:<30} {usd(v['arr']):>14}  ({v['count']} deals)")

    top5 = rows[:5]
    if top5:
        lines.append("")
        lines.append("  Top 5 Opportunities:")
        lines.append(f"  {'Account':<30} {'Deal Type':<15} {'Source':<20} {'ARR (USD)':>14}")
        lines.append(f"  {'─'*30} {'─'*15} {'─'*20} {'─'*14}")
        for row in top5:
            acct = row.get("CRM_ACCOUNT_NAME", "N/A")
            acct = acct[:27] + "..." if len(str(acct)) > 30 else acct
            deal = row.get("DEAL_TYPE", "N/A") or "N/A"
            src = row.get("PARTNER_DEAL_SOURCE", "N/A") or "N/A"
            arr = row.get("PRODUCT_ARR_USD", 0) or 0
            lines.append(f"  {str(acct):<30} {str(deal):<15} {str(src):<20} {usd(arr):>14}")


def _format_book_of_business(lines, rows, divider):
    lines.append("")
    lines.append("  1. BOOK OF BUSINESS (Zuora Reseller Subscriptions)")
    lines.append(divider)

    if not rows:
        lines.append("  No reseller subscriptions found.")
        return

    resellers = defaultdict(list)
    for row in rows:
        resellers[row.get("ZUORA_ACCOUNT_NAME", "Unknown")].append(row)

    for reseller_name, reseller_rows in resellers.items():
        sfdc_id = reseller_rows[0].get("SFDC_ID")
        lines.append("")
        lines.append(f"  Reseller: {reseller_name}")
        if sfdc_id:
            lines.append(f"  SFDC ID:  {sfdc_id}")

        customers = {}
        for row in reseller_rows:
            cust_name = row.get("RESELLERCUSTOMER_ACCOUNTNAME")
            if not cust_name:
                continue
            if cust_name not in customers:
                customers[cust_name] = {
                    "name": cust_name,
                    "subdomain": row.get("RESELLERCUSTOMER_SUBDOMAIN"),
                    "sfdc_id": row.get("RESELLERCUSTOMER_SFDC_ID"),
                    "status": row.get("RESELLERCUSTOMER_STATUS"),
                    "arr": 0,
                    "subscriptions": [],
                }
            cust = customers[cust_name]
            arr_usd = to_usd(
                row.get("RESELLERCUSTOMER_ARR", 0),
                row.get("RESELLERCUSTOMER_CURRENCY", "USD"),
            )
            cust["arr"] = arr_usd
            cust["subscriptions"].append({
                "sub_number": row.get("RESELLERCUSTOMER_SUB_NUMBER"),
                "renewal_date": row.get("RESELLERCUSTOMER_SUB_RENEWAL_DATE"),
                "products": row.get("PRODUCT_NAMES"),
                "quantity": row.get("TOTAL_QUANTITY"),
                "billing": row.get("BILLING_PERIOD"),
            })

        total_arr = sum(c["arr"] for c in customers.values())

        lines.append("")
        lines.append(f"  Customers: {len(customers):,}    Total Subscription ARR: {usd(total_arr)}")
        lines.append("")

        header = f"  {'Customer':<35} {'ARR (USD)':>14} {'Renewal Date':>14} Products"
        lines.append(header)
        lines.append(f"  {'─'*35} {'─'*14} {'─'*14} {'─'*30}")

        sorted_custs = sorted(customers.values(), key=lambda c: c["arr"], reverse=True)
        for cust in sorted_custs:
            renewal_dates = [
                str(s["renewal_date"])[:10]
                for s in cust["subscriptions"]
                if s["renewal_date"]
            ]
            earliest = sorted(renewal_dates)[0] if renewal_dates else "N/A"
            products = ", ".join(sorted(set(
                s["products"] for s in cust["subscriptions"] if s["products"]
            )))
            name = cust["name"][:30] + "..." if len(cust["name"]) > 33 else cust["name"]
            lines.append(f"  {name:<35} {usd(cust['arr']):>14} {earliest:>14} {products}")


def _format_bookings(lines, rows, divider):
    lines.append("  2. BOOKINGS (GTM Pipeline & Partner Opps)")
    lines.append(divider)

    if not rows:
        lines.append("  No bookings found.")
        return

    total_bookings = sum(r.get("BOOKINGS", 0) or 0 for r in rows)
    total_pipeline = sum(r.get("PIPELINE", 0) or 0 for r in rows)

    sourced = sum(
        (r.get("BOOKINGS", 0) or 0)
        for r in rows if r.get("SOURCED_INFLUENCED") == "Partner Sourced"
    )
    influenced = sum(
        (r.get("BOOKINGS", 0) or 0)
        for r in rows if r.get("SOURCED_INFLUENCED") == "Partner Influenced"
    )

    lines.append("")
    lines.append(f"  Total Bookings ARR:  {usd(total_bookings)}")
    lines.append(f"  Total Pipeline ARR:  {usd(total_pipeline)}")
    lines.append(f"  Partner Sourced:     {usd(sourced)}")
    lines.append(f"  Partner Influenced:  {usd(influenced)}")

    _breakdown(lines, rows, "DEAL_TYPE", "By Deal Type:")
    _breakdown(lines, rows, "REGION", "By Region:")
    _breakdown(lines, rows, "PRO_FORMA_MARKET_SEGMENT", "By Segment:")
    _breakdown(lines, rows, "INDUSTRY", "By Industry:")


def _breakdown(lines, rows, key, label):
    agg = defaultdict(lambda: {"bookings": 0, "count": 0})
    for row in rows:
        k = row.get(key) or "Unknown"
        agg[k]["bookings"] += row.get("BOOKINGS", 0) or 0
        agg[k]["count"] += 1

    sorted_agg = sorted(agg.items(), key=lambda x: x[1]["bookings"], reverse=True)

    lines.append("")
    lines.append(f"  {label}")
    for k, v in sorted_agg:
        lines.append(f"    {k:<30} {usd(v['bookings']):>14}  ({v['count']} deals)")
