# Copyright (c) 2026, GASTAT and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class GASTATMonthlyReportLog(Document):
	def before_insert(self):
		if not self.generated_by:
			self.generated_by = frappe.session.user
		if not self.generated_on:
			self.generated_on = frappe.utils.now_datetime()

	@frappe.whitelist()
	def set_file_url(self, file_url):
		"""Attach the generated report file URL for the audit trail."""
		self.file_url = file_url
		self.save(ignore_permissions=True)
		return self.name
