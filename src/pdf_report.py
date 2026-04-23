import os
from collections import defaultdict
from datetime import date
from fpdf import FPDF
from format import to_usd, usd

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "agent-output")
UNICODE_FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"


class PartnerReport(FPDF):
    def __init__(self, partner_name):
        super().__init__()
        self.partner_name = partner_name
        self.add_font("ArialUni", "", UNICODE_FONT, uni=True)
        self.add_font("ArialUni", "B", UNICODE_FONT, uni=True)

    def header(self):
        self.set_font("ArialUni", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, f"Partner Summary: {self.partner_name}", ln=True, align="R")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("ArialUni", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{self.pages_count}", align="C")

    def section_title(self, title):
        self.set_font("ArialUni", "B", 13)
        self.set_text_color(30, 30, 30)
        self.cell(0, 10, title, ln=True)
        self.set_draw_color(50, 50, 50)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def sub_heading(self, text):
        self.set_font("ArialUni", "B", 11)
        self.set_text_color(50, 50, 50)
        self.cell(0, 8, text, ln=True)

    def label_value(self, label, value):
        self.set_font("ArialUni", "", 10)
        self.set_text_color(80, 80, 80)
        self.cell(45, 6, label)
        self.set_text_color(30, 30, 30)
        self.set_font("ArialUni", "B", 10)
        self.cell(0, 6, str(value), ln=True)

    def table_header(self, cols):
        self.set_font("ArialUni", "B", 9)
        self.set_fill_color(240, 240, 240)
        self.set_text_color(30, 30, 30)
        for label, width in cols:
            self.cell(width, 7, label, border=0, fill=True)
        self.ln()

    def table_row(self, cols, values):
        self.set_font("ArialUni", "", 9)
        self.set_text_color(50, 50, 50)
        for i, (_, width) in enumerate(cols):
            text = str(values[i]) if i < len(values) else ""
            self.cell(width, 6, text, border=0)
        self.ln()


def generate_pdf(partner_name, subscriptions, bookings,
                  details=None, open_pipeline=None, sourced_pipeline=None,
                  certifications=None):
    pdf = PartnerReport(partner_name)
    pdf.add_page()

    # Title
    pdf.set_font("ArialUni", "B", 18)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 12, f"Partner Summary: {partner_name}", ln=True)
    pdf.set_font("ArialUni", "", 10)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, f"Generated: {date.today().isoformat()}", ln=True)
    pdf.ln(6)

    if details is not None:
        _pdf_partner_details(pdf, details)
        pdf.ln(4)

    _pdf_book_of_business(pdf, subscriptions)
    pdf.ln(4)
    _pdf_bookings(pdf, bookings)

    if open_pipeline is not None:
        pdf.ln(4)
        _pdf_open_pipeline(pdf, open_pipeline)

    if sourced_pipeline is not None:
        pdf.ln(4)
        _pdf_sourced_pipeline(pdf, sourced_pipeline)

    if certifications is not None:
        pdf.ln(4)
        _pdf_certifications(pdf, certifications)

    filename = f"{partner_name.replace(' ', '_')}_Partner_Summary_{date.today().isoformat()}.pdf"
    filepath = os.path.join(OUTPUT_DIR, filename)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pdf.output(filepath)
    return filepath


def _pdf_partner_details(pdf, rows):
    pdf.section_title("Partner Details (Salesforce)")

    if not rows:
        pdf.set_font("ArialUni", "", 10)
        pdf.cell(0, 8, "No partner account found in Salesforce.", ln=True)
        return

    cols = [("Partner", 50), ("Owner", 30), ("Partner Tier", 22), ("Agreement", 40), ("Date", 20)]
    pdf.table_header(cols)
    for row in rows:
        name = str(row.get("PARTNER_NAME", "N/A"))
        name = name[:26] + ".." if len(name) > 28 else name
        owner = str(row.get("ACCOUNT_OWNER", "N/A"))
        owner = owner[:16] + ".." if len(owner) > 18 else owner
        tier = str(row.get("CHANNEL_CATEGORY") or "N/A")
        agreement = str(row.get("SIGNED_AGREEMENT") or "N/A")
        agreement = agreement[:20] + ".." if len(agreement) > 22 else agreement
        ag_date = row.get("AGREEMENT_DATE")
        date_str = str(ag_date)[:10] if ag_date else "N/A"
        pdf.table_row(cols, [name, owner, tier, agreement, date_str])


def _pdf_open_pipeline(pdf, rows):
    from format import _quarter_bounds, _bucket_deal, _collapse_opps

    pdf.section_title("3. Open Pipeline (Stages 02-06)")

    if not rows:
        pdf.set_font("ArialUni", "", 10)
        pdf.cell(0, 8, "No open pipeline found.", ln=True)
        return

    today = date.today()
    cq_start, cq1_start, cq1_end, fy, fq = _quarter_bounds(today)
    nq = fq + 1 if fq < 4 else 1
    nfy = fy if fq < 4 else fy + 1
    cq_label = f"FY{fy}Q{fq} (CQ)"
    cq1_label = f"FY{nfy}Q{nq} (CQ+1)"

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

    cols = [("Source", 50), (cq_label, 30), (cq1_label, 30), ("Total $", 30), ("Deals", 20)]
    pdf.table_header(cols)
    for src, v in sorted(by_source.items(), key=lambda x: x[1]["total"], reverse=True):
        pdf.table_row(cols, [src, usd(v["cq"]), usd(v["cq1"]), usd(v["total"]), str(v["count"])])

    pdf.set_font("ArialUni", "B", 9)
    pdf.set_text_color(30, 30, 30)
    pdf.set_fill_color(230, 230, 230)
    for label, width in cols:
        val = {"Source": "TOTAL", cq_label: usd(grand["cq"]), cq1_label: usd(grand["cq1"]),
               "Total $": usd(grand["total"]), "Deals": str(grand["count"])}[label]
        pdf.cell(width, 7, val, border=0, fill=True)
    pdf.ln()
    pdf.ln(4)

    opps = _collapse_opps(rows)
    sorted_opps = sorted(opps, key=lambda o: str(o["closedate"] or "9999"))
    top5 = sorted_opps[:5]
    if top5:
        pdf.sub_heading("Top 5 Opportunities")
        cols = [("Account", 30), ("Products", 40), ("Deal Type", 20), ("Source", 28), ("Close", 20), ("ARR", 20)]
        pdf.table_header(cols)
        for opp in top5:
            acct = str(opp["account"])
            acct = acct[:16] + ".." if len(acct) > 18 else acct
            prod = opp["products"]
            prod = prod[:22] + ".." if len(prod) > 24 else prod
            deal = str(opp["deal_type"])
            src = str(opp["source"])
            src = src[:14] + ".." if len(src) > 16 else src
            cd_str = str(opp["closedate"])[:10] if opp["closedate"] else "N/A"
            pdf.table_row(cols, [acct, prod, deal, src, cd_str, usd(opp["arr"])])


def _pdf_sourced_pipeline(pdf, rows):
    pdf.section_title("4. Sourced Pipeline (CQ / CQ-1 / CQ-2)")

    if not rows:
        pdf.set_font("ArialUni", "", 10)
        pdf.cell(0, 8, "No sourced pipeline found.", ln=True)
        return

    REGION_MAP_LOCAL = {
        "americas": "AMER", "amer": "AMER", "na": "AMER", "north america": "AMER",
        "emea": "EMEA", "apac": "APAC", "latam": "LATAM",
    }

    by_qtr = defaultdict(lambda: {"total": 0, "count": 0, "ai": 0, "es": 0, "ccaas": 0,
                                   "regions": defaultdict(lambda: 0)})
    for row in rows:
        fq = row.get("FISCAL_YEAR_QUARTER") or "Unknown"
        arr = row.get("OPPORTUNITY_BOOKING_ARR_USD", 0) or 0
        region_raw = str(row.get("PRO_FORMA_REGION") or "Unknown").lower().strip()
        region = REGION_MAP_LOCAL.get(region_raw, row.get("PRO_FORMA_REGION") or "Unknown")
        by_qtr[fq]["total"] += arr
        by_qtr[fq]["count"] += 1
        by_qtr[fq]["ai"] += row.get("NEW_AI_BOOKING_ARR_USD", 0) or 0
        by_qtr[fq]["es"] += row.get("ES_BOOKING_ARR_USD", 0) or 0
        by_qtr[fq]["ccaas"] += row.get("CCaaS_BOOKING_ARR_USD", 0) or 0
        by_qtr[fq]["regions"][region] += arr

    cols = [("Quarter", 25), ("Total", 25), ("Deals", 15), ("AI", 22), ("ES", 22), ("CCaaS", 22), ("AMER", 22), ("EMEA", 22), ("APAC", 22), ("LATAM", 22)]
    pdf.table_header(cols)
    for fq in sorted(by_qtr.keys()):
        v = by_qtr[fq]
        pdf.table_row(cols, [
            fq, usd(v["total"]), str(v["count"]),
            usd(v["ai"]), usd(v["es"]), usd(v["ccaas"]),
            usd(v["regions"].get("AMER", 0)), usd(v["regions"].get("EMEA", 0)),
            usd(v["regions"].get("APAC", 0)), usd(v["regions"].get("LATAM", 0)),
        ])


def _pdf_certifications(pdf, rows):
    from collections import defaultdict

    pdf.section_title("5. Certifications (Skilljar)")

    if not rows:
        pdf.set_font("ArialUni", "", 10)
        pdf.cell(0, 8, "No certifications found.", ln=True)
        return

    by_group = defaultdict(lambda: {"completed": set(), "in_progress": set(), "all": set()})
    for row in rows:
        group = row.get("COURSE_GROUP") or "Ungrouped"
        if group in ("None", "Ungrouped"):
            continue
        contact = row.get("CONTACT_EMAIL") or row.get("CONTACT_NAME")
        if not contact:
            continue
        by_group[group]["all"].add(contact)
        if row.get("SKILLJAR_COMPLETED_AT_C"):
            by_group[group]["completed"].add(contact)
        else:
            by_group[group]["in_progress"].add(contact)

    if not by_group:
        pdf.set_font("ArialUni", "", 10)
        pdf.cell(0, 8, "No certifications found.", ln=True)
        return

    all_completed = set()
    all_in_progress = set()
    all_contacts = set()
    for v in by_group.values():
        all_completed |= v["completed"]
        all_in_progress |= v["in_progress"]
        all_contacts |= v["all"]

    pdf.label_value("Enrolled:", str(len(all_contacts)))
    pdf.label_value("With Completions:", str(len(all_completed)))
    pdf.label_value("In Progress:", str(len(all_in_progress)))
    pdf.ln(2)

    cols = [("Course Group", 70), ("Certified", 25), ("In Progress", 30), ("Enrolled", 25)]
    pdf.table_header(cols)
    for group, v in sorted(by_group.items(), key=lambda x: len(x[1]["completed"]), reverse=True):
        name = group[:38] + ".." if len(group) > 40 else group
        pdf.table_row(cols, [name, str(len(v["completed"])), str(len(v["in_progress"])), str(len(v["all"]))])


def _pdf_book_of_business(pdf, rows):
    pdf.section_title("1. Book of Business (Zuora Reseller Subscriptions)")

    if not rows:
        pdf.set_font("ArialUni", "", 10)
        pdf.cell(0, 8, "No reseller subscriptions found.", ln=True)
        return

    resellers = defaultdict(list)
    for row in rows:
        resellers[row.get("ZUORA_ACCOUNT_NAME", "Unknown")].append(row)

    grand_total_customers = 0
    grand_total_arr = 0

    for reseller_name, reseller_rows in resellers.items():
        sfdc_id = reseller_rows[0].get("SFDC_ID")

        customers = {}
        for row in reseller_rows:
            cust_name = row.get("RESELLERCUSTOMER_ACCOUNTNAME")
            if not cust_name:
                continue
            if cust_name not in customers:
                customers[cust_name] = {
                    "name": cust_name,
                    "arr": 0,
                    "subscriptions": [],
                }
            cust = customers[cust_name]
            cust["arr"] = to_usd(
                row.get("RESELLERCUSTOMER_ARR", 0),
                row.get("RESELLERCUSTOMER_CURRENCY", "USD"),
            )
            cust["subscriptions"].append({
                "renewal_date": row.get("RESELLERCUSTOMER_SUB_RENEWAL_DATE"),
                "products": row.get("PRODUCT_NAMES"),
            })

        total_arr = sum(c["arr"] for c in customers.values())
        grand_total_customers += len(customers)
        grand_total_arr += total_arr

        pdf.sub_heading(reseller_name)
        if sfdc_id:
            pdf.set_font("ArialUni", "", 9)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(0, 5, f"SFDC ID: {sfdc_id}", ln=True)
        pdf.label_value("Customers:", str(len(customers)))
        pdf.label_value("Subscription ARR:", usd(total_arr))
        pdf.ln(2)

        cols = [("Customer", 55), ("ARR (USD)", 28), ("Renewal", 25), ("Products", 82)]
        pdf.table_header(cols)

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
            name = cust["name"][:28] + ".." if len(cust["name"]) > 30 else cust["name"]
            prods = products[:45] + ".." if len(products) > 47 else products
            pdf.table_row(cols, [name, usd(cust["arr"]), earliest, prods])

        pdf.ln(4)

    pdf.set_draw_color(50, 50, 50)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(2)
    pdf.label_value("Total Customers:", str(grand_total_customers))
    pdf.label_value("Total ARR:", usd(grand_total_arr))


def _pdf_bookings(pdf, rows):
    pdf.section_title("2. Bookings (GTM Pipeline & Partner Opps)")

    if not rows:
        pdf.set_font("ArialUni", "", 10)
        pdf.cell(0, 8, "No bookings found.", ln=True)
        return

    total_bookings = sum(r.get("BOOKINGS", 0) or 0 for r in rows)
    sourced = sum(
        (r.get("BOOKINGS", 0) or 0)
        for r in rows if r.get("SOURCED_INFLUENCED") == "Partner Sourced"
    )
    influenced = sum(
        (r.get("BOOKINGS", 0) or 0)
        for r in rows if r.get("SOURCED_INFLUENCED") == "Partner Influenced"
    )

    pdf.label_value("Total Bookings ARR:", usd(total_bookings))
    pdf.label_value("Partner Sourced:", usd(sourced))
    pdf.label_value("Partner Influenced:", usd(influenced))
    pdf.ln(4)

    _pdf_breakdown(pdf, rows, "DEAL_TYPE", "By Deal Type")
    _pdf_breakdown(pdf, rows, "REGION", "By Region")
    _pdf_breakdown(pdf, rows, "PRO_FORMA_MARKET_SEGMENT", "By Segment")
    _pdf_breakdown(pdf, rows, "INDUSTRY", "By Industry")


def _pdf_breakdown(pdf, rows, key, label):
    agg = defaultdict(lambda: {"bookings": 0, "count": 0})
    for row in rows:
        k = row.get(key) or "Unknown"
        agg[k]["bookings"] += row.get("BOOKINGS", 0) or 0
        agg[k]["count"] += 1

    sorted_agg = sorted(agg.items(), key=lambda x: x[1]["bookings"], reverse=True)

    pdf.sub_heading(label)
    cols = [("Category", 70), ("Bookings ARR", 35), ("Deals", 20)]
    pdf.table_header(cols)
    for k, v in sorted_agg:
        name = k[:38] + ".." if len(k) > 40 else k
        pdf.table_row(cols, [name, usd(v["bookings"]), str(v["count"])])
    pdf.ln(4)
