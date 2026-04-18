from collections import defaultdict
from datetime import date

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

    lines.append("")
    lines.append(f"  {'Partner':<35} {'Owner':<20} {'Partner Tier':<12} {'Agreement':<25} {'Date':>10}")
    lines.append(f"  {'─'*35} {'─'*20} {'─'*12} {'─'*25} {'─'*10}")
    for row in rows:
        name = str(row.get('PARTNER_NAME', 'N/A'))
        name = name[:32] + "..." if len(name) > 35 else name
        owner = str(row.get('ACCOUNT_OWNER', 'N/A'))
        owner = owner[:17] + "..." if len(owner) > 20 else owner
        tier = str(row.get('CHANNEL_CATEGORY') or 'N/A')
        agreement = str(row.get('SIGNED_AGREEMENT') or 'N/A')
        agreement = agreement[:22] + "..." if len(agreement) > 25 else agreement
        ag_date = row.get('AGREEMENT_DATE')
        date_str = str(ag_date)[:10] if ag_date else "N/A"
        lines.append(f"  {name:<35} {owner:<20} {tier:<12} {agreement:<25} {date_str:>10}")


def _fiscal_quarter(today):
    """Fiscal year starts Feb 1. Q1=Feb-Apr, Q2=May-Jul, Q3=Aug-Oct, Q4=Nov-Jan."""
    FQ_STARTS = [(2, 1), (5, 1), (8, 1), (11, 1)]

    if today.month >= 2:
        fy = today.year + 1
    else:
        fy = today.year

    for i, (m, d) in enumerate(FQ_STARTS):
        start_year = fy - 1 if m >= 2 else fy
        q_start = date(start_year, m, d)
        next_i = (i + 1) % 4
        nm, nd = FQ_STARTS[next_i]
        next_year = start_year if nm > m else start_year + 1
        q_end = date(next_year, nm, nd)
        if q_start <= today < q_end:
            return fy, i + 1, q_start, q_end

    return fy, 4, date(fy - 1, 11, 1), date(fy, 2, 1)


def _quarter_bounds(today):
    fy, fq, cq_start, cq1_start = _fiscal_quarter(today)
    _, _, _, cq1_end = _fiscal_quarter(cq1_start)
    return cq_start, cq1_start, cq1_end, fy, fq


def _bucket_deal(close_date, cq_start, cq1_start, cq1_end):
    if not close_date:
        return "other"
    d = close_date if isinstance(close_date, date) else date.fromisoformat(str(close_date)[:10])
    if cq_start <= d < cq1_start:
        return "cq"
    if cq1_start <= d < cq1_end:
        return "cq1"
    return "other"


def _collapse_opps(rows):
    opps = {}
    for row in rows:
        opp_id = row.get("CRM_OPPORTUNITY_ID")
        if not opp_id:
            continue
        product = str(row.get("PRODUCT", "") or "")
        if opp_id not in opps:
            opps[opp_id] = {
                "account": row.get("CRM_ACCOUNT_NAME", "N/A"),
                "deal_type": row.get("DEAL_TYPE", "N/A") or "N/A",
                "source": row.get("PARTNER_DEAL_SOURCE", "N/A") or "N/A",
                "closedate": row.get("CLOSEDATE"),
                "arr": 0,
                "products": [],
            }
        opp = opps[opp_id]
        if product.lower() == "total booking":
            opp["arr"] = row.get("PRODUCT_ARR_USD", 0) or 0
        else:
            if product and product not in opp["products"]:
                opp["products"].append(product)

    result = []
    for opp in opps.values():
        opp["products"] = ", ".join(opp["products"]) if opp["products"] else "N/A"
        result.append(opp)
    return result


def _format_open_pipeline(lines, rows, divider):
    lines.append("  3. OPEN PIPELINE (Stages 02-06)")
    lines.append(divider)

    if not rows:
        lines.append("  No open pipeline found.")
        return

    today = date.today()
    cq_start, cq1_start, cq1_end, fy, fq = _quarter_bounds(today)
    nq = fq + 1 if fq < 4 else 1
    nfy = fy if fq < 4 else fy + 1
    cq_label = f"FY{fy}Q{fq}"
    cq1_label = f"FY{nfy}Q{nq}"

    by_source = defaultdict(lambda: {"cq": 0, "cq1": 0, "total": 0, "count": 0})
    for row in rows:
        src = row.get("SOURCED_INFLUENCED") or row.get("PARTNER_DEAL_SOURCE") or "Unknown"
        arr = row.get("PRODUCT_ARR_USD", 0) or 0
        bucket = _bucket_deal(row.get("CLOSEDATE"), cq_start, cq1_start, cq1_end)
        by_source[src]["total"] += arr
        by_source[src]["count"] += 1
        if bucket == "cq":
            by_source[src]["cq"] += arr
        elif bucket == "cq1":
            by_source[src]["cq1"] += arr

    grand = {"cq": 0, "cq1": 0, "total": 0, "count": 0}
    for v in by_source.values():
        for k in grand:
            grand[k] += v[k]

    lines.append("")
    lines.append(f"  {'Source':<25} {cq_label + ' (CQ)':>14} {cq1_label + ' (CQ+1)':>14} {'Total $':>14} {'Deals':>8}")
    lines.append(f"  {'─'*25} {'─'*14} {'─'*14} {'─'*14} {'─'*8}")
    for src, v in sorted(by_source.items(), key=lambda x: x[1]["total"], reverse=True):
        lines.append(f"  {src:<25} {usd(v['cq']):>14} {usd(v['cq1']):>14} {usd(v['total']):>14} {v['count']:>8}")
    lines.append(f"  {'─'*25} {'─'*14} {'─'*14} {'─'*14} {'─'*8}")
    lines.append(f"  {'TOTAL':<25} {usd(grand['cq']):>14} {usd(grand['cq1']):>14} {usd(grand['total']):>14} {grand['count']:>8}")

    opps = _collapse_opps(rows)
    sorted_opps = sorted(opps, key=lambda o: str(o["closedate"] or "9999"))
    top5 = sorted_opps[:5]
    if top5:
        lines.append("")
        lines.append("  Top 5 Opportunities:")
        lines.append(f"  {'Account':<25} {'Products':<30} {'Deal Type':<12} {'Source':<16} {'Close Date':>12} {'ARR (USD)':>12}")
        lines.append(f"  {'─'*25} {'─'*30} {'─'*12} {'─'*16} {'─'*12} {'─'*12}")
        for opp in top5:
            acct = str(opp["account"])
            acct = acct[:22] + "..." if len(acct) > 25 else acct
            prod = opp["products"]
            prod = prod[:27] + "..." if len(prod) > 30 else prod
            deal = str(opp["deal_type"])
            deal = deal[:9] + "..." if len(deal) > 12 else deal
            src = str(opp["source"])
            src = src[:13] + "..." if len(src) > 16 else src
            cd_str = str(opp["closedate"])[:10] if opp["closedate"] else "N/A"
            lines.append(f"  {acct:<25} {prod:<30} {deal:<12} {src:<16} {cd_str:>12} {usd(opp['arr']):>12}")


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
