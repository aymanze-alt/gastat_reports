# Copyright (c) 2026, GASTAT and contributors
# For license information, please see license.txt

import frappe

from gastat_reports.api import get_production_report, get_available_items_options, get_company_options


@frappe.whitelist()
def get_report(company=None, month=0, year=0):
	"""Data endpoint for the production survey page."""
	return get_production_report(company=company, month=month or 0, year=year or 0)


@frappe.whitelist()
def get_options():
	"""Item groups / items for the page (used by settings helper)."""
	return get_available_items_options()


@frappe.whitelist()
def get_company_list():
	"""Companies for the production survey filter (settings-first, non-empty)."""
	return get_company_options(["Sales Order"])
