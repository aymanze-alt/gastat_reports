from . import __version__ as app_version

app_name = "gastat_reports"
app_title = "GASTAT Reports"
app_publisher = "GASTAT"
app_description = "Monthly Industrial Production and Employee Statistics reports for the General Authority for Statistics (GASTAT), Saudi Arabia."
app_email = "info@gastat-reports.local"
app_license = "mit"

app_include_js = "/assets/gastat_reports/js/pages_common.js"
app_include_css = "/assets/gastat_reports/css/gastat_reports.css"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/gastat_reports/css/gastat_reports.css"
# app_include_js = "/assets/gastat_reports/js/gastat_reports.js"

# include js, css files in header of web template
# web_include_css = "/assets/gastat_reports/css/gastat_reports.css"
# web_include_js = "/assets/gastat_reports/js/gastat_reports.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "gastat_reports/public/scss/website"

# include js, css files in header of web form
# web_include_js = ["/assets/gastat_reports/js/gastat_reports.js"]
# web_include_css = ["/assets/gastat_reports/css/gastat_reports.css"]

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "gastat_reports/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "gastat_reports.utils.jinja_methods",
# 	"filters": "gastat_reports.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "gastat_reports.install.before_install"
# after_install = "gastat_reports.install.after_install"

# Uninstallation
# ------------
# before_uninstall = "gastat_reports.uninstall.before_uninstall"
# after_uninstall = "gastat_reports.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "gastat_reports.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"Todo": "custom_app.overrides.CustomTodo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"gastat_reports.tasks.all"
# 	],
# 	"daily": [
# 		"gastat_reports.tasks.daily"
# 	],
# 	"hourly": [
# 		"gastat_reports.tasks.hourly"
# 	],
# 	"weekly": [
# 		"gastat_reports.tasks.weekly"
# 	],
# 	"monthly": [
# 		"gastat_reports.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "gastat_reports.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "gastat_reports.event.get_events"
# }
#
# override_doctype_class = {
# 	"Todo": "gastat_reports.overrides.CustomTodo"
# }

# Messenger Slack Webhook URL
# --------------------------

# messenger_slack_webhook_url = "https://hooks.slack.com/services/xxxxxxxxxxxx"

# Website Routing
# ----------------
# ------
# A list of routing rules that may be used to send users to specific pages
# based on their data
#
# More info: https://frappeframework.com/docs/user/en/guides/routing
#
# website_route_rules = []

# Fixtures
# --------
# List of fixtures to be imported every time the app is installed
#
# fixtures = ["Custom Field", "Role", "Client Script"]

# Print Formats
# --------------
# Create print formats for custom doctypes
#
# print_format = [
# 	{
# 		"doctype": "GASTAT Monthly Report Log",
# 		"name": "GASTAT Production Survey",
# 		"print_format_builder": 0,
# 		"doc_type": "GASTAT Monthly Report Log"
# 	}
# ]

# TODO List
# ---------
# Add items to the todo list
#
# todo_list = ["Approve link to work"]

# Internal Routes
# -------------
# Add routes to the internal server to redirect users
#
# internal_route_whitelist = ["link-to-navigable-page"]
