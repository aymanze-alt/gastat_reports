# Copyright (c) 2026, GASTAT and contributors
# For license information, please see license.txt

import frappe

from gastat_reports.api import get_employee_statistics, get_company_options


@frappe.whitelist()
def get_report(company=None, month=0, year=0):
	"""Data endpoint for the employee statistics page."""
	return get_employee_statistics(company=company, month=month or 0, year=year or 0)


@frappe.whitelist()
def get_company_list():
	"""Companies for the employee statistics filter (settings-first, non-empty)."""
	return get_company_options(["Salary Slip"])
