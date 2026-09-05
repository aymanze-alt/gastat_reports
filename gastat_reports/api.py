# Copyright (c) 2026, GASTAT and contributors
# For license information, please see license.txt

"""Server-side APIs for the GASTAT reports application."""

import json

import frappe
from frappe import _
from frappe.utils import flt, now_datetime, cint

from gastat_reports.utils import get_month_number, month_range, get_month_name_ar, MONTHS_EN


# ----------------------------------------------------------------------------
# Settings / helpers
# ----------------------------------------------------------------------------

def get_settings():
	return frappe.get_single("GASTAT Settings")


def get_price_columns():
	"""Map price source option -> (Item field, SO aggregation flag)."""
	return {
		"Standard Selling Rate": "standard_rate",
		"Valuation Rate": "valuation_rate",
		"Last Purchase Rate": "last_purchase_rate",
	}


def get_salary_column():
	"""Map the settings option to the Salary Slip field used for the salary total.

	"Total Earnings" resolves to the `custom_total` custom field (salary before any
	deduction); if that is empty for a slip the report falls back to `total_earnings`.
	"""
	return {
		"Net Pay": "net_pay",
		"Gross Pay": "gross_pay",
		"Total Earnings": "custom_total",
	}.get(frappe.get_single("GASTAT Settings").salary_component_for_total, "net_pay")


def _standardize_params(args):
	"""Normalize month/year/company from whitelist kwargs (json or dict)."""
	company = args.get("company")
	month = args.get("month", 0)
	year = cint(args.get("year", 0))

	settings = get_settings()
	if not company:
		company = settings.company

	if year == 0:
		year = now_datetime().year
	month_no = get_month_number(month if month else now_datetime().month)

	# resolve currency with fallback to company default
	currency = settings.default_currency
	if not currency:
		currency = frappe.db.get_value("Company", company, "default_currency")

	return company, month_no, year, currency, settings


def _format_number(value, currency=None):
	if currency:
		return f"{flt(value):,.2f} {currency}"
	return f"{flt(value):,.2f}"


def get_company_options(transaction_tables=None):
	"""De-duplicated list of companies for the report filter dropdowns.

	Order: the company configured in GASTAT Settings (always first / default),
	then companies with submitted transactional data, then every company
	defined in the Company master. Guarantees a non-empty list on a fresh site
	as long as a settings company or a Company record exists.
	"""
	settings_company = frappe.db.get_single_value("GASTAT Settings", "company") or ""
	seen = set()
	ordered = []

	def add(company):
		company = (company or "").strip()
		if company and company not in seen:
			seen.add(company)
			ordered.append(company)

	add(settings_company)

	for table in transaction_tables or ["Sales Order"]:
		for (company,) in frappe.db.sql(
			f"SELECT DISTINCT company FROM `tab{table}` WHERE docstatus = 1 ORDER BY company",
			as_list=True,
		):
			add(company)

	for (company,) in frappe.db.sql(
		"SELECT name FROM `tabCompany` ORDER BY `tabCompany`.name", as_list=True
	):
		add(company)

	return [[company] for company in ordered]


def _log_report(report_type, month_no, year, company, file_url):
	"""Create an audit log entry for a generated report."""
	month_name = MONTHS_EN[month_no - 1]
	doc = frappe.get_doc(
		{
			"doctype": "GASTAT Monthly Report Log",
			"report_type": report_type,
			"month": month_name,
			"year": year,
			"company": company,
			"generated_by": frappe.session.user,
			"generated_on": now_datetime(),
			"file_url": file_url or "",
		}
	)
	doc.insert(ignore_permissions=True, ignore_mandatory=True)
	return doc.name


# ----------------------------------------------------------------------------
# Report 1: Industrial Production Survey (from Sales Orders)
# ----------------------------------------------------------------------------

def _inclusion_rules(settings):
	included_groups = set(r.item_group for r in settings.production_item_groups if r.is_included)
	included_items = set(r.item_code for r in settings.production_items if r.is_included)
	hs_map = {r.item_code: r.custom_hs_code for r in settings.production_items if r.custom_hs_code}
	return included_groups, included_items, hs_map


def _item_passes(item_group, item_code, included_groups, included_items):
	"""An item passes if it satisfies active group and item constraints."""
	group_ok = (not included_groups) or (item_group in included_groups)
	item_ok = (not included_items) or (item_code in included_items)
	return group_ok and item_ok


@frappe.whitelist()
def get_production_report(company=None, month=0, year=0):
	company, month_no, year, currency, settings = _standardize_params(
		{"company": company, "month": month, "year": year}
	)
	if not company:
		frappe.throw(_("Please select a company."))

	start_date, end_date = month_range(month_no, year)
	included_groups, included_items, hs_map = _inclusion_rules(settings)
	price_source = settings.production_price_source or "Standard Selling Rate"
	source = settings.production_source or "Sales Orders"

	# Pick the source document (Sales Order / Sales Invoice) for production data.
	if source == "Sales Invoices":
		doc_table = "`tabSales Invoice`"
		item_table = "`tabSales Invoice Item`"
		date_col = "posting_date"
	else:
		source = "Sales Orders"
		doc_table = "`tabSales Order`"
		item_table = "`tabSales Order Item`"
		date_col = "transaction_date"

	# Returns (credit notes) only exist for Sales Invoices; keep them off the item
	# rows and report them separately as a deduction line.
	returns_filter = "AND so.is_return = 0" if source == "Sales Invoices" else ""

	# Fetch submitted items of the selected source document within the period.
	so_items = frappe.db.sql(
		f"""
		SELECT
			soi.item_code,
			soi.item_name,
			soi.item_group,
			soi.uom,
			SUM(soi.qty) AS total_qty,
			SUM(soi.base_net_amount) AS total_amount,
			SUM(soi.base_rate * soi.qty) AS rate_x_qty
		FROM {item_table} AS soi
		INNER JOIN {doc_table} AS so ON so.name = soi.parent
		WHERE so.docstatus = 1
			{returns_filter}
			AND so.{date_col} BETWEEN %(start)s AND %(end)s
			AND so.company = %(company)s
		GROUP BY soi.item_code, soi.item_name, soi.item_group, soi.uom
		ORDER BY total_amount DESC
		""",
		{"start": start_date, "end": end_date, "company": company},
		as_dict=True,
	)

	# Item-level detail (standard / valuation / last purchase rate)
	item_codes = [r.item_code for r in so_items]
	item_meta = {}
	if item_codes:
		price_field = get_price_columns().get(price_source)
		select = "name, item_name"
		if price_field:
			select += f", {price_field} AS price"
		rows = frappe.db.sql(
			f"SELECT {select} FROM `tabItem` WHERE name IN %(codes)s",
			{"codes": item_codes},
			as_dict=True,
		)
		item_meta = {r["name"]: r for r in rows}

	# Aggregate returned sales invoice items (credit notes) as a single deduction,
	# respecting the same inclusion rules as the item rows.
	returns_qty = 0.0
	returns_value = 0.0
	if source == "Sales Invoices":
		ret_rows = frappe.db.sql(
			f"""
			SELECT
				soi.item_code,
				soi.item_group,
				SUM(soi.qty) AS ret_qty,
				SUM(soi.base_net_amount) AS ret_amount
			FROM `tabSales Invoice Item` AS soi
			INNER JOIN `tabSales Invoice` AS so ON so.name = soi.parent
			WHERE so.docstatus = 1
				AND so.is_return = 1
				AND so.posting_date BETWEEN %(start)s AND %(end)s
				AND so.company = %(company)s
			GROUP BY soi.item_code, soi.item_group
			""",
			{"start": start_date, "end": end_date, "company": company},
			as_dict=True,
		)
		for rr in ret_rows:
			if _item_passes(rr.item_group, rr.item_code, included_groups, included_items):
				returns_qty += flt(rr.ret_qty)
				returns_value += flt(rr.ret_amount)

	rows = []
	grand_qty = 0.0
	grand_value = 0.0
	for r in so_items:
		if not _item_passes(r.item_group, r.item_code, included_groups, included_items):
			continue
		meta = item_meta.get(r.item_code, {})

		if price_source == "Sales Order Rate":
			total_value = flt(r.total_amount)
			unit_price = total_value / flt(r.total_qty) if flt(r.total_qty) else 0
		elif meta.get("price") is not None:
			unit_price = flt(meta.get("price"))
			total_value = flt(r.total_qty) * unit_price
		else:
			unit_price = 0
			total_value = 0
		grand_qty += flt(r.total_qty)
		grand_value += flt(total_value)

		rows.append(
			{
				"item_code": r.item_code,
				"item_name": r.item_name or meta.get("item_name") or r.item_code,
				"item_group": r.item_group,
				"hs_code": hs_map.get(r.item_code, ""),
				"uom": r.uom,
				"qty": flt(r.total_qty),
				"unit_price": flt(unit_price),
				"total_value": flt(total_value),
			}
		)

	# Sort by total value descending and add row numbers
	rows.sort(key=lambda x: (x["total_value"], x["qty"]), reverse=True)
	for i, r in enumerate(rows, start=1):
		r["sr"] = i

	net_qty = flt(grand_qty) + flt(returns_qty)
	net_value = flt(grand_value) + flt(returns_value)

	summary = {
		"total_items": len(rows),
		"total_qty": flt(net_qty),
		"avg_unit_price": flt(net_value) / flt(net_qty) if flt(net_qty) else 0,
		"total_value": flt(net_value),
		"gross_value": flt(grand_value),
		"returns_value": flt(returns_value),
		"returns_qty": flt(returns_qty),
		"currency": currency,

		"price_source": price_source,
		"production_source": source,
		"month": month_no,
		"month_name_ar": get_month_name_ar(month_no, year),
		"year": year,
		"company": company,
		"company_name": frappe.db.get_value("Company", company, "company_name") or company,
		"start_date": start_date,
		"end_date": end_date,
		"generated_on": now_datetime(),
	}

	chart = {
		"labels": [f"{r['item_code']} - {r['item_name']}"[:40] for r in rows[:12]],
		"values": [r["total_value"] for r in rows[:12]],
	}

	return {"rows": rows, "summary": summary, "chart": chart}


def get_available_items_options():
	"""Item groups and items available for the production inclusion config."""
	groups = frappe.db.sql(
		"""
		SELECT item_group, COUNT(*) AS item_count
		FROM `tabItem` GROUP BY item_group ORDER BY item_group
		""",
		as_dict=True,
	)
	items = frappe.db.sql(
		"SELECT name, item_name, item_group FROM `tabItem` ORDER BY item_group, name",
		as_dict=True,
	)
	return {"groups": groups, "items": items}


@frappe.whitelist()
def get_production_config_options():
	return get_available_items_options()


# ----------------------------------------------------------------------------
# Report 2: Employee Statistics
# ----------------------------------------------------------------------------

@frappe.whitelist()
def get_employee_statistics(company=None, month=0, year=0):
	company, month_no, year, currency, settings = _standardize_params(
		{"company": company, "month": month, "year": year}
	)
	if not company:
		frappe.throw(_("Please select a company."))

	start_date, end_date = month_range(month_no, year)
	salary_col = get_salary_column()

	if salary_col == "custom_total":
		salary_expr = "COALESCE(ss.custom_total, ss.total_earnings, 0)"
	else:
		salary_expr = f"ss.{salary_col}"

	# Driver is the Salary Slip table (submitted slips in the period), joined to the
	# Employee master for nationality / gender / id. This makes the employee count
	# follow the payroll of the selected month instead of the static employee list.
	slips = frappe.db.sql(
		"""
		SELECT
			ss.employee,
			ss.employee_name,
			ss.posting_date,
			emp.gender,
			emp.custom_nationality,
			emp.custom_id_number,
			{salary_expr} AS month_salary
		FROM `tabSalary Slip` AS ss
		LEFT JOIN `tabEmployee` AS emp ON emp.name = ss.employee
		WHERE ss.docstatus = 1
			AND ss.company = %(company)s
			AND ss.start_date BETWEEN %(start)s AND %(end)s
		ORDER BY ss.employee, ss.posting_date DESC
		""".format(salary_expr=salary_expr),
		{"company": company, "start": start_date, "end": end_date},
		as_dict=True,
	)

	# Keep the latest slip per employee
	seen = {}
	ordered = []
	for s in slips:
		if s.employee not in seen:
			seen[s.employee] = True
			ordered.append(s)

	saudi_rows = []
	nonsaudi_rows = []
	stats = {
		"saudi_male": 0,
		"saudi_female": 0,
		"nonsaudi_male": 0,
		"nonsaudi_female": 0,
		"saudi_salaries": 0.0,
		"nonsaudi_salaries": 0.0,
	}

	for s in ordered:
		nationality = (s.custom_nationality or "").strip()
		is_saudi = "السعودية" in nationality or "سعود" in nationality or nationality.lower() in ("saudi", "saudi arabia")
		gender = (s.gender or "").strip()
		monthly_salary = flt(s.month_salary)

		row = {
			"employee": s.employee,
			"employee_name": s.employee_name or s.employee,
			"national_id": s.custom_id_number or "",
			"nationality": nationality,
			"gender": gender,
			"category": "سعودي" if is_saudi else "غير سعودي",
			"monthly_salary": monthly_salary,
		}

		if is_saudi:
			saudi_rows.append(row)
			stats["saudi_salaries"] += monthly_salary
			if gender == "Female":
				stats["saudi_female"] += 1
			else:
				stats["saudi_male"] += 1
		else:
			nonsaudi_rows.append(row)
			stats["nonsaudi_salaries"] += monthly_salary
			if gender == "Female":
				stats["nonsaudi_female"] += 1
			else:
				stats["nonsaudi_male"] += 1

	saudi_rows.sort(key=lambda x: (x["employee_name"] or ""))
	nonsaudi_rows.sort(key=lambda x: (x["employee_name"] or ""))
	total_rows = saudi_rows + nonsaudi_rows

	total_employees = stats["saudi_male"] + stats["saudi_female"] + stats["nonsaudi_male"] + stats["nonsaudi_female"]
	total_salaries = stats["saudi_salaries"] + stats["nonsaudi_salaries"]

	saudi_total = stats["saudi_male"] + stats["saudi_female"]
	nonsaudi_total = stats["nonsaudi_male"] + stats["nonsaudi_female"]
	saudi_pct = round(flt(saudi_total) * 100 / total_employees, 1) if total_employees else 0
	nonsaudi_pct = round(flt(nonsaudi_total) * 100 / total_employees, 1) if total_employees else 0

	summary = {
		"saudi_male": stats["saudi_male"],
		"saudi_female": stats["saudi_female"],
		"nonsaudi_male": stats["nonsaudi_male"],
		"nonsaudi_female": stats["nonsaudi_female"],
		"saudi_total": saudi_total,
		"nonsaudi_total": nonsaudi_total,
		"saudi_pct": saudi_pct,
		"nonsaudi_pct": nonsaudi_pct,
		"total_employees": total_employees,
		"saudi_salaries": stats["saudi_salaries"],
		"nonsaudi_salaries": stats["nonsaudi_salaries"],
		"total_salaries": total_salaries,
		"salary_col": settings.salary_component_for_total,
		"currency": currency,
		"month": month_no,
		"month_name_ar": get_month_name_ar(month_no, year),
		"year": year,
		"company": company,
		"company_name": frappe.db.get_value("Company", company, "company_name") or company,
		"start_date": start_date,
		"end_date": end_date,
		"generated_on": now_datetime(),
	}

	charts = {
		"saudi_vs_nonsaudi": {
			"labels": ["سعودي", "غير سعودي"],
			"values": [saudi_total, nonsaudi_total],
			"colors": ["#16a34a", "#7c3aed"],
		},
		"male_vs_female": {
			"labels": ["ذكور", "إناث"],
			"values": [stats["saudi_male"] + stats["nonsaudi_male"], stats["saudi_female"] + stats["nonsaudi_female"]],
			"colors": ["#2563eb", "#ec4899"],
		},
		"salary_by_category": {
			"labels": ["سعودي", "غير سعودي"],
			"values": [stats["saudi_salaries"], stats["nonsaudi_salaries"]],
			"colors": ["#16a34a", "#7c3aed"],
		},
	}

	return {
		"saudi_rows": saudi_rows,
		"nonsaudi_rows": nonsaudi_rows,
		"total_rows": total_rows,
		"summary": summary,
		"charts": charts,
	}


def _employees_signature_block(settings):
	blocks = {}
	name = settings.authorized_signatory_name or ""
	title = settings.authorized_signatory_title or ""
	blocks["name"] = name
	blocks["title"] = title
	signature_cell = ""
	if name:
		lines = [_(f"Authorized Signatory: {name}")]
		if title:
			lines.append(_(f"Title: {title}"))
		signature_cell = "<br/>".join(lines)
	blocks["cell"] = signature_cell
	return blocks


# ----------------------------------------------------------------------------
# Export wrappers (page JS calls gastat_reports.api.<method>)
# ----------------------------------------------------------------------------

@frappe.whitelist()
def export_production_pdf(company=None, month=0, year=0, **kwargs):
	from gastat_reports.print_report import export_production_pdf as _impl
	return _impl(company=company, month=month, year=year, **kwargs)


@frappe.whitelist()
def export_production_excel(company=None, month=0, year=0, **kwargs):
	from gastat_reports.print_report import export_production_excel as _impl
	return _impl(company=company, month=month, year=year, **kwargs)


@frappe.whitelist()
def export_employee_pdf(company=None, month=0, year=0, **kwargs):
	from gastat_reports.print_report import export_employee_pdf as _impl
	return _impl(company=company, month=month, year=year, **kwargs)


@frappe.whitelist()
def export_employee_excel(company=None, month=0, year=0, **kwargs):
	from gastat_reports.print_report import export_employee_excel as _impl
	return _impl(company=company, month=month, year=year, **kwargs)
