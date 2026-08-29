# Copyright (c) 2026, GASTAT and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class GASTATProductionItem(Document):
	def validate(self):
		if self.item_code and not self.item_name:
			self.item_name = frappe.db.get_value("Item", self.item_code, "item_name")
