# Copyright (c) 2026, GASTAT and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class GASTATSettings(Document):
	def validate(self):
		self.set_default_currency()

	def set_default_currency(self):
		"""Auto-fill default currency from the selected company."""
		if self.company:
			company_currency = frappe.db.get_value("Company", self.company, "default_currency")
			if company_currency:
				self.default_currency = company_currency

	@frappe.whitelist()
	def get_inclusion_config(self):
		"""Return configured included item groups and items for the production report."""
		included_groups = [r.item_group for r in self.production_item_groups if r.is_included]
		included_items = [r.item_code for r in self.production_items if r.is_included]
		return {"included_groups": included_groups, "included_items": included_items}


def get_gastat_settings():
	return frappe.get_single("GASTAT Settings")
