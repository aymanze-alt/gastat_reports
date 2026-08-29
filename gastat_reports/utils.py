# Copyright (c) 2026, GASTAT and contributors
# For license information, please see license.txt

import calendar

import frappe

MONTHS_AR = [
	"يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
	"يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]

MONTHS_EN = [
	"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December",
]


def get_month_number(month):
	"""Return the 1-based month number given a month name (Arabic, English, or number)."""
	if month is None:
		month = frappe.utils.now_datetime().month
	if isinstance(month, int):
		return max(1, min(12, month))
	month = str(month).strip()
	if month.isdigit():
		return max(1, min(12, int(month)))
	low = month.lower()
	for i, name in enumerate(MONTHS_EN, start=1):
		if name.lower() == low:
			return i
	for i, name in enumerate(MONTHS_AR, start=1):
		if name == month:
			return i
	raise frappe.ValidationError(f"Invalid month: {month}")


def get_month_name_ar(month_number, year=None):
	if year is not None:
		month_number = get_month_number(month_number)
	return MONTHS_AR[month_number - 1]


def month_range(month_number, year):
	"""First and last day of the given month."""
	month_number = get_month_number(month_number)
	last_day = calendar.monthrange(int(year), month_number)[1]
	first = frappe.utils.getdate(f"{int(year)}-{month_number:02d}-01")
	end = frappe.utils.getdate(f"{int(year)}-{month_number:02d}-{last_day}")
	return first, end
