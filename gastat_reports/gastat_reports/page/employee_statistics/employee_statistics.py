# Copyright (c) 2026, GASTAT and contributors
# For license information, please see license.txt

import frappe

from gastat_reports.api import get_employee_statistics


@frappe.whitelist()
def get_report(company=None, month=0, year=0):
	"""Data endpoint for the employee statistics page."""
	return get_employee_statistics(company=company, month=month or 0, year=year or 0)


@frappe.whitelist()
def get_company_list():
	"""Companies that have payroll (Salary Slip) data."""
	return frappe.db.sql(
		"SELECT DISTINCT company FROM `tabSalary Slip` WHERE docstatus = 1 ORDER BY company",
		as_list=True,
	)
