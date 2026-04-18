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
                  details=None, open_pipeline=None):
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

    for row in rows:
        pdf.label_value("Partner:", str(row.get("PARTNER_NAME", "N/A")))
        pdf.label_value("Account Owner:", str(row.get("ACCOUNT_OWNER", "N/A")))
        pdf.label_value("Type:", str(row.get("ACCOUNT_TYPE", "N/A")))
        pdf.label_value("Partner Type:", str(row.get("PARTNER_TYPE", "N/A")))
        pdf.label_value("Channel Category:", str(row.get("CHANNEL_CATEGORY", "N/A")))
        pdf.label_value("Partner Level:", str(row.get("PARTNER_LEVEL", "N/A")))
        pdf.label_value("Status:", str(row.get("PARTNER_STATUS", "N/A")))
        pdf.label_value("Agreement Signed:", str(row.get("SIGNED_AGREEMENT", "N/A")))
        ag_date = row.get("AGREEMENT_DATE")
        pdf.label_value("Agreement Date:", str(ag_date)[:10] if ag_date else "N/A")
        pdf.label_value("Serviced Region:", str(row.get("SERVICED_REGION", "N/A")))
        pdf.ln(4)


def _pdf_open_pipeline(pdf, rows):
    pdf.section_title("3. Open Pipeline (Stages 02-06)")

    if not rows:
        pdf.set_font("ArialUni", "", 10)
        pdf.cell(0, 8, "No open pipeline found.", ln=True)
        return

    by_source = defaultdict(lambda: {"arr": 0, "count": 0})
    for row in rows:
        src = row.get("SOURCED_INFLUENCED") or row.get("PARTNER_DEAL_SOURCE") or "Unknown"
        by_source[src]["arr"] += row.get("PRODUCT_ARR_USD", 0) or 0
        by_source[src]["count"] += 1

    total_arr = sum(v["arr"] for v in by_source.values())
    total_deals = sum(v["count"] for v in by_source.values())

    pdf.label_value("Total Open Pipeline:", f"{usd(total_arr)}  ({total_deals} deals)")
    pdf.ln(2)

    pdf.sub_heading("By Partner Deal Source")
    cols = [("Source", 70), ("ARR (USD)", 35), ("Deals", 20)]
    pdf.table_header(cols)
    for src, v in sorted(by_source.items(), key=lambda x: x[1]["arr"], reverse=True):
        pdf.table_row(cols, [src, usd(v["arr"]), str(v["count"])])
    pdf.ln(4)

    top5 = rows[:5]
    if top5:
        pdf.sub_heading("Top 5 Opportunities")
        cols = [("Account", 55), ("Deal Type", 30), ("Source", 40), ("ARR (USD)", 30)]
        pdf.table_header(cols)
        for row in top5:
            acct = str(row.get("CRM_ACCOUNT_NAME", "N/A"))
            acct = acct[:28] + ".." if len(acct) > 30 else acct
            deal = str(row.get("DEAL_TYPE", "N/A") or "N/A")
            src = str(row.get("PARTNER_DEAL_SOURCE", "N/A") or "N/A")
            arr = row.get("PRODUCT_ARR_USD", 0) or 0
            pdf.table_row(cols, [acct, deal, src, usd(arr)])


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
