# Copyright (c) 2026, GASTAT and contributors
# For license information, please see license.txt

"""PDF and Excel export for GASTAT reports."""

import base64
import html
import io
import json
import os

import frappe
from frappe.utils import flt, now_datetime, cint

from gastat_reports.api import get_production_report, get_employee_statistics, _log_report
from gastat_reports.utils import get_month_name_ar


# ============================================================================
# Shared HTML helpers
# ============================================================================

CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
html, body {
    margin: 0; padding: 0;
    font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
    color: #1f2937;
    direction: rtl;
    background: #ffffff;
}
.page {
    position: relative;
    min-height: 1080px;
    padding: 14mm 12mm 22mm 12mm;
}
/* Letterhead */
.letterhead {
    display: flex; align-items: center; justify-content: space-between;
    border-bottom: 3px solid #0f766e;
    padding-bottom: 6mm; width: 100%;
}
.letterhead .logo img { max-height: 34mm; max-width: 60mm; }
.letterhead .title-block { text-align: center; flex: 1; }
.letterhead .title-block h1 {
    margin: 0; font-size: 15pt; color: #0f766e;
    font-weight: 700;
}
.letterhead .title-block .subtitle {
    margin: 2px 0 0 0; font-size: 10pt; color: #475569;
}
.letterhead .spacer { width: 60mm; }
.letterhead .spacer-sm { width: 20mm; }

.header-meta {
    display: flex; justify-content: space-between;
    margin-top: 4mm; font-size: 9.5pt; color: #374151;
    border: 1px solid #e2e8f0; border-radius: 6px;
    padding: 3mm 4mm; background: #f8fafc;
}
.header-meta div strong { color: #0f766e; }

h2.section-title {
    font-size: 13pt; color: #0f766e; margin: 6mm 0 3mm;
    border-right: 4px solid #14b8a6; padding-right: 3mm;
}

table.data {
    width: 100%; border-collapse: collapse; font-size: 9pt;
	table-layout: fixed;
}
table.data th {
    background: #0f766e; color: #ffffff; padding: 2.2mm 2mm;
    font-weight: 600; border: 1px solid #0f766e; text-align: center;
	word-wrap: break-word; overflow-wrap: break-word; word-break: break-word;
}
table.data td {
    padding: 2mm 2mm; border: 1px solid #cbd5e1; text-align: center;
	word-wrap: break-word; overflow-wrap: break-word; word-break: break-word;
	white-space: normal;
}
table.data tbody tr:nth-child(even) { background: #f1f5f9; }
table.data tbody tr.total td {
    background: #0f766e !important; color: #ffffff; font-weight: 700;
}
td.num, th.num { text-align: left; }
td.r, th.r { text-align: right; }

.summary-box {
    display: flex; flex-wrap: wrap; gap: 3mm;
    margin: 4mm 0;
}
.summary-box .card {
    flex: 1 1 22%; border: 1px solid #e2e8f0; border-radius: 8px;
    padding: 3mm; text-align: center; background: #f8fafc;
}
.summary-box .card .k { font-size: 8.5pt; color: #64748b; margin-bottom: 1mm; }
.summary-box .card .v { font-size: 12pt; font-weight: 700; color: #0f766e; }

.notes {
    margin-top: 5mm; font-size: 8.5pt; color: #64748b;
    border-top: 1px solid #e2e8f0; padding-top: 2mm;
}
.signature-block {
    display: flex; justify-content: space-between; align-items: flex-end;
    margin-top: 16mm;
}
.signature-block .sig {
    text-align: center; width: 45%;
}
.signature-block .sig .line { border-bottom: 1px solid #334155; margin-bottom: 2mm; }
.signature-block .sig .name { font-weight: 700; }
.signature-block .sig .title { font-size: 9pt; color: #475569; }
.footer-note {
    position: absolute; bottom: 8mm; left: 12mm; right: 12mm;
    text-align: center; font-size: 8pt; color: #94a3b8;
    border-top: 1px solid #e2e8f0; padding-top: 2mm;
}
.employee-section-header td {
    background: #e2e8f0 !important; color: #0f766e;
    font-weight: 700; font-size: 10pt;
}
"""


def _img_data_uri(file_url, fallback_text=""):
	"""Convert an attachment URL to a base64 data URI, or return empty."""
	if not file_url:
		return ""
	try:
		path = file_url
		if file_url.startswith("/files/"):
			path = os.path.join(frappe.local.conf.get("sites_path"), "sites", frappe.local.site,
				file_url.lstrip("/"))
		elif file_url.startswith("/private"):
			path = os.path.join(frappe.local.conf.get("sites_path"), "sites", frappe.local.site,
				file_url.lstrip("/"))
		elif file_url.startswith("http"):
			return file_url
		if not os.path.exists(path):
			frappe.log_error(f"Logo file not found at {path}")
			return ""
		with open(path, "rb") as fh:
			data = base64.b64encode(fh.read()).decode()
		ext = os.path.splitext(path)[1].lstrip(".").lower()
		mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif", "svg": "image/svg+xml"}.get(ext, "image/png")
		return f"data:{mime};base64,{data}"
	except Exception as e:
		frappe.log_error(f"Logo embed failed: {e}")
		return ""


def _monetary(value):
	return f"{flt(value):,.2f}"


def _build_html(letterhead_html, body_html, footer_text, page_title, extra_css=""):
	settings = frappe.get_single("GASTAT Settings")
	return f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8"/>
<title>{page_title}</title>
<style>{CSS}
{extra_css}</style>
</head>
<body>
<div class="page">
    {letterhead_html}
    {body_html}
    <div class="footer-note">{footer_text or '&nbsp;'}</div>
</div>
</body>
</html>
"""


def _letterhead(title, subtitle):
	settings = frappe.get_single("GASTAT Settings")
	logo_url = settings.report_header_logo
	logo_img = ""
	if logo_url:
		uri = _img_data_uri(logo_url)
		if uri:
			logo_img = f'<img src="{uri}"/>'
	return f"""
<div class="letterhead">
    <div class="logo">{logo_img}</div>
    <div class="title-block">
        <h1>{title}</h1>
        <div class="subtitle">{subtitle}</div>
    </div>
    <div class="spacer"></div>
</div>
"""


def _header_meta(summary):
	company_name = summary.get("company_name") or summary.get("company") or "-"
	month_ar = get_month_name_ar(summary.get("month", 1), summary.get("year"))
	period = f"{month_ar} {summary.get('year')}"
	generated = frappe.utils.format_datetime(now_datetime(), "dd MMMM yyyy - hh:mm a")
	return f"""
<div class="header-meta">
    <div><strong>الشركة:</strong> {company_name}</div>
    <div><strong>الفترة:</strong> {period}</div>
    <div><strong>تاريخ التوليد:</strong> {generated}</div>
</div>
"""


def _signature_cells(cell, cell2=None):
	return f"""
<div class="signature-block">
    <div class="sig">
        <div class="line">&nbsp;</div>
        <div class="name">المعتمد / Authorized Signatory</div>
        <div class="title">{cell}</div>
    </div>
</div>
"""


def _build_pdf(html, orientation="Portrait"):
	options = {
		"page-size": "A4",
		"orientation": orientation,
		"margin-top": "0mm",
		"margin-bottom": "0mm",
		"margin-left": "0mm",
		"margin-right": "0mm",
		"encoding": "UTF-8",
		"enable-local-file-access": None,
	}
	from frappe.utils.pdf import get_pdf
	return get_pdf(html, options=options)


# ============================================================================
# Production HTML
# ============================================================================

def production_html(data):
	summary = data["summary"]
	rows = data["rows"]
	settings = frappe.get_single("GASTAT Settings")

	title = "تقرير المسح الصناعي الشهري"
	subtitle = "Industrial Production Survey – Monthly Report"
	head = _letterhead(title, subtitle)
	meta = _header_meta(summary)

	# summary cards
	ret_card = f"""
        <div class="card"><div class="k">خصم المرتجعات</div><div class="v">{_monetary(summary.get('returns_value', 0.0))} {summary.get('currency','')}</div></div>""" if flt(summary.get("returns_value", 0.0)) else ""
	cards = f"""
    <div class="summary-box">
        <div class="card"><div class="k">عدد الأصناف المنتجة</div><div class="v">{summary['total_items']}</div></div>
        <div class="card"><div class="k">إجمالي الكمية</div><div class="v">{_monetary(summary['total_qty'])}</div></div>
        <div class="card"><div class="k">متوسط سعر الوحدة</div><div class="v">{_monetary(summary['avg_unit_price'])}</div></div>
        <div class="card"><div class="k">إجمالي قيمة الإنتاج (الصافي)</div><div class="v">{_monetary(summary['total_value'])} {summary.get('currency','')}</div></div>
        {ret_card}
    </div>
    """

	trs = ""
	for r in rows:
		trs += f"""
        <tr>
            <td>{r['sr']}</td>
            <td class="r">{r['item_code']}</td>
            <td class="r">{r['item_name']}</td>
            <td>{r['hs_code'] or '-'}</td>
            <td>{_monetary(r['qty'])}</td>
            <td>{r['uom']}</td>
            <td class="num">{_monetary(r['unit_price'])}</td>
            <td class="num">{_monetary(r['total_value'])}</td>
        </tr>"""
	grand_qty = sum(r['qty'] for r in rows)
	grand_val = sum(r['total_value'] for r in rows)
	ret_qty = flt(summary.get('returns_qty', 0.0))
	ret_val = flt(summary.get('returns_value', 0.0))
	ret_rows = f"""
        <tr>
            <td colspan="4" class="r">خصم المرتجعات / Less: Returns</td>
            <td>{_monetary(ret_qty)}</td><td></td><td></td>
            <td class="num">{_monetary(ret_val)}</td>
        </tr>""" if ret_val else ""
	net_rows = f"""
        <tr class="total">
            <td colspan="4">الصافي / Net Total</td>
            <td>{_monetary(grand_qty + ret_qty)}</td><td></td><td></td>
            <td class="num">{_monetary(summary['total_value'])} {summary.get('currency','')}</td>
        </tr>"""
	table = f"""
    <h2 class="section-title">تفاصيل الإنتاج حسب الصنف</h2>
    <table class="data">
        <thead>
            <tr>
                <th>#</th><th>كود الصنف</th><th>اسم الصنف</th><th>رمز HS</th>
                <th>الكمية المنتجة</th><th>وحدة القياس</th><th>سعر الوحدة</th><th>القيمة الإجمالية</th>
            </tr>
        </thead>
        <tbody>
            {trs}
            <tr class="total">
                <td colspan="4">إجمالي المبيعات / Gross Total</td>
                <td>{_monetary(grand_qty)}</td><td></td><td></td>
                <td class="num">{_monetary(grand_val)} {summary.get('currency','')}</td>
            </tr>
            {ret_rows}
            {net_rows}
        </tbody>
    </table>
    """

	# signature
	auth_name = settings.authorized_signatory_name or ""
	auth_title = settings.authorized_signatory_title or ""
	sig = ""
	if auth_name:
		sig += f"<div class='name'>{auth_name}</div>"
	if auth_title:
		sig += f"<div class='title'>{auth_title}</div>"
	else:
		sig = ""

	signature = f"""
    <div class="signature-block">
        <div class="sig">
            <div class="line">&nbsp;</div>
            <div class="name">المعتمد / Authorized Signatory</div>
            <div class="title">{sig or '&nbsp;'}</div>
        </div>
    </div>
    """

	notes = f"<div class='notes'>مصدر البيانات: {summary.get('production_source','')} | مصدر الأسعار: {summary.get('price_source','')} | العملة: {summary.get('currency','')} | ملاحظات: {settings.report_footer_text or ''}</div>"

	body = meta + cards + table + notes + signature
	return _build_html(head, body, settings.report_footer_text, title)


# ============================================================================
# Employee HTML
# ============================================================================

# Ordered column definitions for the employee detail table. Each column maps to
# a key present on every employee row produced by get_employee_statistics.
# `type` values: text / num (work days) / money (currency amounts).
EMPLOYEE_COLUMNS = [
	{"key": "employee", "label": "رقم الموظف", "type": "text"},
	{"key": "national_id", "label": "رقم الهوية", "type": "text"},
	{"key": "employee_name", "label": "اسم الموظف", "type": "text"},
	{"key": "nationality", "label": "الجنسية", "type": "text"},
	{"key": "designation", "label": "المسمى الوظيفي", "type": "text"},
	{"key": "company", "label": "الشركة", "type": "text"},
	{"key": "payment_days", "label": "ايام العمل", "type": "num"},
	{"key": "basic", "label": "الاساسي", "type": "money"},
	{"key": "housing", "label": "بدل السكن", "type": "money"},
	{"key": "transportation", "label": "بدل المواصلات", "type": "money"},
	{"key": "allowances", "label": "البدلات", "type": "money"},
	{"key": "monthly_salary", "label": "اجمالي الراتب", "type": "money"},
	{"key": "total_transferred", "label": "اجمالي الراتب المحول", "type": "money"},
]

# Summary key that backs each money column (used for the grand-total row).
SUMMARY_TOTALS = {
	"basic": "total_basic",
	"housing": "total_housing",
	"transportation": "total_transportation",
	"allowances": "total_allowances",
	"monthly_salary": "total_salaries",
	"total_transferred": "total_transferred",
}

# RC ordering only makes sense for numeric columns.
_NUMERIC_FLDS = {"payment_days", "basic", "housing", "transportation", "allowances", "monthly_salary", "total_transferred"}

ALL_EMPLOYEE_COLUMN_KEYS = {c["key"] for c in EMPLOYEE_COLUMNS}

# Relative widths for the flat PDF table (used for the <colgroup>). The row # and
# رقم الموظف columns stay small while the long text columns get more room so the
# values wrap instead of spilling into neighbouring columns.
COLUMN_WIDTHS = {
	"employee": 6,
	"national_id": 10,
	"employee_name": 14,
	"nationality": 14,
	"designation": 10,
	"company": 18,
	"payment_days": 5,
	"basic": 6,
	"housing": 6,
	"transportation": 6,
	"allowances": 6,
	"monthly_salary": 6,
	"total_transferred": 6,
}
ROW_NUM_WIDTH = 7

# Estimated max chars per line per column. wkhtmltopdf's QtWebKit does NOT honour
# CSS `table-layout: fixed` / `word-wrap`, so long text (e.g. the company name) is
# broken at word boundaries with real <br> instead.
TEXT_WRAP_LENGTH = {
	"employee": 8,
	"national_id": 12,
	"employee_name": 22,
	"nationality": 10,
	"designation": 16,
	"company": 28,
	"payment_days": 7,
	"basic": 8,
	"housing": 8,
	"transportation": 8,
	"allowances": 8,
	"monthly_salary": 8,
	"total_transferred": 8,
}


def _wrap_text(value, budget):
	"""Escape text and insert <br> at word boundaries so no line exceeds `budget` chars."""
	text = frappe.utils.cstr(value)
	if not text or text == "-":
		return text or "-"
	words = text.split()
	lines, cur = [], ""
	for w in words:
		if len(cur) + len(w) + (1 if cur else 0) > budget:
			if cur:
				lines.append(cur)
			cur = w
		else:
			cur = (cur + " " + w) if cur else w
	if cur:
		lines.append(cur)
	escaped = "<br>".join(html.escape(l) for l in lines)
	return escaped


def _cal_colgroup(cols):
	"""Build a <colgroup> with normalized percentages for the given column defs."""
	widths = [ROW_NUM_WIDTH] + [COLUMN_WIDTHS.get(c["key"], 10) for c in cols]
	total = sum(widths) or 1
	return "".join(
		f'<col style="width:{w * 100.0 / total:.3f}%">' for w in widths
	)


def resolve_employee_columns(columns=None):
	"""Normalize a list/JSON of column keys (or resolved defs) into ordered column definitions.

	Invalid / unknown keys are ignored. `None`/empty returns all columns.
	"""
	if columns:
		if isinstance(columns, str):
			try:
				columns = json.loads(columns)
			except (ValueError, TypeError):
				columns = []
		if isinstance(columns, list):
			keys = []
			for c in columns:
				if isinstance(c, dict) and c.get("key"):
					keys.append(c["key"])
				elif isinstance(c, str) and c in ALL_EMPLOYEE_COLUMN_KEYS:
					keys.append(c)
			cols = [c for c in EMPLOYEE_COLUMNS if c["key"] in keys]
			if cols:
				return cols
	return list(EMPLOYEE_COLUMNS)


def _sort_employee_rows(rows, sort_by=None, sort_order=None):
	"""Sort employee rows by a column key (default: رقم الموظف = employee)."""
	if not sort_by or sort_by not in ALL_EMPLOYEE_COLUMN_KEYS:
		sort_by = "employee"
	reverse = str(sort_order or "").lower() in ("desc", "descending", "1", "true")

	if sort_by in _NUMERIC_FLDS:
		rows.sort(key=lambda x: flt(x.get(sort_by)), reverse=reverse)
	else:
		rows.sort(key=lambda x: (x.get(sort_by) or "").lower(), reverse=reverse)
	return rows


def employee_headers(columns=None):
	"""Header labels for the flat employee table (includes the Row # column)."""
	return ["الرقم"] + [c["label"] for c in resolve_employee_columns(columns)]


def _flat_salary_table(rows, summary, columns=None):
	cols = resolve_employee_columns(columns)

	trs = ""
	for i, r in enumerate(rows, start=1):
		cells = [f"<td>{i}</td>"]
		for c in cols:
			if c["type"] == "money":
				cells.append(f'<td class="num">{_monetary(r.get(c["key"]) or 0)}</td>')
			elif c["type"] == "num":
				cells.append(f'<td class="num">{_monetary(r.get(c["key"]) or 0)}</td>')
			else:
				cells.append(f'<td class="r">{_wrap_text(r.get(c["key"]) or "-", TEXT_WRAP_LENGTH.get(c["key"], 20))}</td>')
		trs += f"""
        <tr>
            {''.join(cells)}
        </tr>"""

	money_cols = [c for c in cols if c["type"] == "money"]
	# The grand-total label spans الرقم + all text columns; the work-days slot
	# stays as an empty num cell, then the money totals are filled.
	has_num = any(c["type"] == "num" for c in cols)
	text_count = len([c for c in cols if c["type"] == "text"])
	label_span = max(1 + text_count, 1)
	total_cells = [f'<td colspan="{label_span}" class="r">الإجمالي الكلي / Grand Total</td>']
	if has_num:
		total_cells.append('<td class="num"></td>')
	for c in money_cols:
		total_cells.append(f'<td class="num">{_monetary(summary.get(SUMMARY_TOTALS[c["key"]], 0.0))}</td>')

	th_cells = [f"<th>{_wrap_text('الرقم', 5)}</th>"] + [
		f"<th>{_wrap_text(c['label'], TEXT_WRAP_LENGTH.get(c['key'], 20))}</th>" for c in cols
	]
	table = f"""
    <h2 class="section-title">تفاصيل الموظفين ({len(rows)})</h2>
    <table class="data">
        <colgroup>{_cal_colgroup(cols)}</colgroup>
        <thead>
            <tr>
                {''.join(th_cells)}
            </tr>
        </thead>
        <tbody>
            {trs}
            <tr class="total">
                {''.join(total_cells)}
            </tr>
        </tbody>
    </table>
    """
	return table


def employee_html(data, columns=None):
	summary = data["summary"]
	rows = data["total_rows"]
	settings = frappe.get_single("GASTAT Settings")
	currency = summary.get("currency", "")

	title = "تقرير إحصاءات الموظفين"
	subtitle = "Employee Statistics – Monthly Report"
	head = _letterhead(title, subtitle)
	meta = _header_meta(summary)

	cards = f"""
    <div class="summary-box">
        <div class="card"><div class="k">نسبة السعوديين</div><div class="v">{summary['saudi_pct']}%</div></div>
        <div class="card"><div class="k">نسبة غير السعوديين</div><div class="v">{summary['nonsaudi_pct']}%</div></div>
        <div class="card"><div class="k">سعوديون (ذكور)</div><div class="v">{summary['saudi_male']}</div></div>
        <div class="card"><div class="k">سعوديات (إناث)</div><div class="v">{summary['saudi_female']}</div></div>
        <div class="card"><div class="k">غير سعوديين (ذكور)</div><div class="v">{summary['nonsaudi_male']}</div></div>
        <div class="card"><div class="k">غير سعوديات (إناث)</div><div class="v">{summary['nonsaudi_female']}</div></div>
        <div class="card"><div class="k">إجمالي رواتب السعوديين</div><div class="v">{_monetary(summary['saudi_salaries'])} {currency}</div></div>
        <div class="card"><div class="k">إجمالي رواتب غير السعوديين</div><div class="v">{_monetary(summary['nonsaudi_salaries'])} {currency}</div></div>
    </div>
    """

	table = _flat_salary_table(rows, summary, columns)

	auth_name = settings.authorized_signatory_name or ""
	auth_title = settings.authorized_signatory_title or ""
	sig_inner = (f"<div class='name'>{auth_name}</div>" if auth_name else "") + (f"<div class='title'>{auth_title}</div>" if auth_title else "")
	signature = f"""
    <div class="signature-block">
        <div class="sig">
            <div class="line">&nbsp;</div>
            <div class="name">المعتمد / Authorized Signatory</div>
            <div class="title">{sig_inner or '&nbsp;'}</div>
        </div>
    </div>
    """

	notes = f"<div class='notes'>مرجع الراتب: {summary.get('salary_col','')} | العملة: {currency} | ملاحظات: {settings.report_footer_text or ''}</div>"

	body = meta + cards + table + notes + signature
	# 12 columns need landscape orientation to remain readable
	extra_css = "@page { size: A4 landscape; margin: 0; }"
	return _build_html(head, body, settings.report_footer_text, title, extra_css)


# ============================================================================
# Whitelisted export endpoints
# ============================================================================

def _save_and_return(html, filename, report_type, month_no, year, company, orientation="Portrait"):
	pdf_data = _build_pdf(html, orientation=orientation)
	file_doc = frappe.get_doc({
		"doctype": "File",
		"file_name": filename,
		"is_private": 1,
		"content": pdf_data,
	})
	file_doc.save(ignore_permissions=True)
	# audit log
	name = _log_report(report_type, month_no, year, company, file_doc.file_url)
	frappe.db.commit()
	return file_doc.file_url


@frappe.whitelist()
def export_production_pdf(company=None, month=0, year=0, **kwargs):
	data = get_production_report(company=company, month=month or 0, year=year or 0)
	html = production_html(data)
	summary = data["summary"]
	filename = f"Production_Survey_{summary['month']:02d}_{summary['year']}.pdf"
	return _save_and_return(html, filename, "Production", summary["month"], summary["year"], summary["company"])


@frappe.whitelist()
def export_employee_pdf(company=None, month=0, year=0, columns=None, sort_by=None, sort_order=None, **kwargs):
	data = get_employee_statistics(company=company, month=month or 0, year=year or 0,
	                               sort_by=sort_by, sort_order=sort_order)
	html = employee_html(data, columns=columns)
	summary = data["summary"]
	filename = f"Employee_Statistics_{summary['month']:02d}_{summary['year']}.pdf"
	return _save_and_return(html, filename, "Employees", summary["month"], summary["year"], summary["company"],
	                        orientation="Landscape")


# ============================================================================
# Excel exports (openpyxl)
# ============================================================================

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


_TEAL = "0F766E"
_LIGHT = "E2E8F0"
_TOTAL = "B45309"


def _xlsx_style():
	thin = Side(style="thin", color="CBD5E1")
	return {
		"header_fill": PatternFill("solid", fgColor=_TEAL),
		"header_font": Font(color="FFFFFF", bold=True, name="Calibri", size=11),
		"sub_fill": PatternFill("solid", fgColor=_LIGHT),
		"sub_font": Font(color=_TEAL, bold=True, size=11),
		"total_fill": PatternFill("solid", fgColor=_TOTAL),
		"total_font": Font(color="FFFFFF", bold=True, size=11),
		"border": Border(left=thin, right=thin, top=thin, bottom=thin),
		"center": Alignment(horizontal="center", vertical="center"),
		"right": Alignment(horizontal="right", vertical="center"),
	}


def _write_header(ws, title, subtitle, ncols, style):
	ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
	c = ws.cell(row=1, column=1, value=title)
	c.font = Font(bold=True, size=16, color=_TEAL)
	c.alignment = style["center"]
	ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
	c2 = ws.cell(row=2, column=1, value=subtitle)
	c2.font = Font(italic=True, size=11, color="64748B")
	c2.alignment = style["center"]
	ws.row_dimensions[1].height = 28
	ws.row_dimensions[2].height = 16


def _write_table_header(ws, row_idx, headers, style):
	for col, h in enumerate(headers, start=1):
		c = ws.cell(row=row_idx, column=col, value=h)
		c.fill = style["header_fill"]
		c.font = style["header_font"]
		c.alignment = style["center"]
		c.border = style["border"]
	ws.row_dimensions[row_idx].height = 20
	return row_idx + 1


def _autofit(ws, widths):
	for i, w in enumerate(widths, start=1):
		ws.column_dimensions[get_column_letter(i)].width = w


def _save_xlsx(wb, filename, report_type, month_no, year, company):
	buf = io.BytesIO()
	wb.save(buf)
	buf.seek(0)
	file_doc = frappe.get_doc({
		"doctype": "File",
		"file_name": filename,
		"is_private": 1,
		"content": buf.getvalue(),
	})
	file_doc.save(ignore_permissions=True)
	name = _log_report(report_type, month_no, year, company, file_doc.file_url)
	frappe.db.commit()
	return file_doc.file_url


@frappe.whitelist()
def export_production_excel(company=None, month=0, year=0, **kwargs):
	data = get_production_report(company=company, month=month or 0, year=year or 0)
	summary = data["summary"]
	rows = data["rows"]
	style = _xlsx_style()
	wb = Workbook()
	ws = wb.active
	ws.title = "Production Survey"

	title = "تقرير المسح الصناعي الشهري (Industrial Production Survey)"
	subtitle = (f"{summary['company_name']} | {summary['month_name_ar']} {summary['year']}"
	            f" | Data source: {summary.get('production_source','')} | Currency: {summary.get('currency','')} | Price source: {summary.get('price_source','')}")
	_write_header(ws, title, subtitle, 8, style)

	# summary block
	srow = 4
	summary_items = [
		("Total Items Produced", summary["total_items"]),
		("Total Quantity", flt(summary["total_qty"])),
		("Average Unit Price", flt(summary["avg_unit_price"])),
		("Total Production Value", flt(summary["total_value"])),
	]
	for i, (k, v) in enumerate(summary_items):
		c = ws.cell(row=srow, column=1 + i * 2, value=k)
		c.font = Font(bold=True, size=10)
		c2 = ws.cell(row=srow, column=2 + i * 2, value=flt(v))
		c2.font = Font(bold=True, size=10, color=_TEAL)
	srow += 3

	headers = ["Row #", "Item Code", "Item Name", "HS Code", "Quantity Produced", "UOM", "Unit Price", "Total Value"]
	r = _write_table_header(ws, srow, headers, style)
	grand_qty = 0.0
	grand_val = 0.0
	for row in rows:
		grand_qty += row["qty"]
		grand_val += row["total_value"]
		vals = [row["sr"], row["item_code"], row["item_name"], row["hs_code"] or "-",
		        flt(row["qty"]), row["uom"], flt(row["unit_price"]), flt(row["total_value"])]
		for col, v in enumerate(vals, start=1):
			c = ws.cell(row=r, column=col, value=v)
			c.border = style["border"]
			c.alignment = style["right"] if col in (2, 3) else style["center"]
		r += 1

	# row writers
	def _total_row(label, qty, val, fill, font):
		nonlocal r
		vals = ["", "", label, "", flt(qty), "", "", flt(val)]
		for col, v in enumerate(vals, start=1):
			c = ws.cell(row=r, column=col, value=v)
			c.fill = fill
			c.font = font
			c.border = style["border"]
			c.alignment = style["center"]
		r += 1

	_total_row("Gross Total", grand_qty, grand_val, style["total_fill"], style["total_font"])
	ret_val = flt(summary.get("returns_value", 0.0))
	if ret_val:
		ret_fill = PatternFill("solid", fgColor="FFF7ED")
		ret_font = Font(color="C2410C", bold=True, size=11)
		_total_row("Less: Returns", flt(summary.get("returns_qty", 0.0)), ret_val, ret_fill, ret_font)
	_total_row("Net Total", flt(summary["total_qty"]), flt(summary["total_value"]),
	           style["total_fill"], Font(color="FFFFFF", bold=True, size=12))

	_autofit(ws, [8, 14, 30, 14, 16, 10, 14, 16])
	ws.freeze_panes = f"A{srow+2}"
	filename = f"Production_Survey_{summary['month']:02d}_{summary['year']}.xlsx"
	return _save_xlsx(wb, filename, "Production", summary["month"], summary["year"], summary["company"])


@frappe.whitelist()
def export_employee_excel(company=None, month=0, year=0, columns=None, sort_by=None, sort_order=None, **kwargs):
	data = get_employee_statistics(company=company, month=month or 0, year=year or 0,
	                               sort_by=sort_by, sort_order=sort_order)
	summary = data["summary"]
	rows = data["total_rows"]
	cols = resolve_employee_columns(columns)
	style = _xlsx_style()
	wb = Workbook()
	ws = wb.active
	ws.title = "Employee Statistics"
	ws.sheet_view.rightToLeft = True
	headers = employee_headers(cols)
	ncols = len(headers)

	title = "تقرير إحصاءات الموظفين (Employee Statistics)"
	subtitle = (f"{summary['company_name']} | {summary['month_name_ar']} {summary['year']}"
	            f" | Salary reference: {summary.get('salary_col','')} | Currency: {summary.get('currency','')}")
	_write_header(ws, title, subtitle, ncols, style)

	# summary
	srow = 4
	stats = [
		("Saudi %", summary["saudi_pct"]),
		("Non-Saudi %", summary["nonsaudi_pct"]),
		("Saudi Males", summary["saudi_male"]),
		("Saudi Females", summary["saudi_female"]),
		("Non-Saudi Males", summary["nonsaudi_male"]),
		("Non-Saudi Females", summary["nonsaudi_female"]),
		("Total Saudi Salaries", flt(summary["saudi_salaries"])),
		("Total Non-Saudi Salaries", flt(summary["nonsaudi_salaries"])),
	]
	for i, (k, v) in enumerate(stats):
		c = ws.cell(row=srow, column=1 + i, value=k)
		c.font = Font(bold=True, size=10)
		c2 = ws.cell(row=srow + 1, column=1 + i, value=flt(v))
		c2.font = Font(bold=True, size=10, color=_TEAL)
		c2.alignment = style["center"]
	srow += 3

	r = _write_table_header(ws, srow, headers, style)

	money_cols = [i + 2 for i, c in enumerate(cols) if c["type"] == "money"]
	text_cols = [i + 2 for i, c in enumerate(cols) if c["type"] == "text"]
	for idx, row in enumerate(rows, start=1):
		vals = [idx]
		for c in cols:
			v = row.get(c["key"])
			vals.append(flt(v) if c["type"] in ("num", "money") else (v or "-"))
		for col, v in enumerate(vals, start=1):
			c = ws.cell(row=r, column=col, value=v)
			c.border = style["border"]
			c.alignment = style["right"] if col in text_cols else style["center"]
		r += 1

	# grand total: the label spans الرقم + all text columns; an empty cell covers
	# the work-days slot (when selected), then the money totals are filled.
	totals = [summary.get(SUMMARY_TOTALS[c["key"]], 0.0) for c in cols if c["type"] == "money"]
	text_count = len([c for c in cols if c["type"] == "text"])
	has_num = any(c["type"] == "num" for c in cols)
	label_span = max(1 + text_count, 1)
	ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=label_span)
	c = ws.cell(row=r, column=1, value="الإجمالي الكلي / Grand Total")
	c.fill = style["total_fill"]
	c.font = style["total_font"]
	c.alignment = style["center"]
	if has_num:
		eme = ws.cell(row=r, column=label_span + 1, value=None)
		eme.fill = style["total_fill"]
		eme.font = style["total_font"]
		eme.border = style["border"]
	for i, t in enumerate(totals):
		cc = ws.cell(row=r, column=money_cols[i], value=flt(t))
		cc.fill = style["total_fill"]
		cc.font = style["total_font"]
		cc.border = style["border"]

	widths = [6]
	for c in cols:
		if c["type"] == "text":
			widths.append(22 if c["key"] in ("employee_name", "company") else 14)
		elif c["type"] == "money":
			widths.append(14 if c["key"] == "monthly_salary" else 12)
		else:
			widths.append(10)
	_autofit(ws, widths)
	ws.freeze_panes = f"A{srow + 2}"
	filename = f"Employee_Statistics_{summary['month']:02d}_{summary['year']}.xlsx"
	return _save_xlsx(wb, filename, "Employees", summary["month"], summary["year"], summary["company"])
