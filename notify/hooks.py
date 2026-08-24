app_name = "notify"
app_title = "Notify"
app_publisher = "Finstein"
app_description = "Outlook-style desktop and mobile push notifications for Frappe/ERPNext bell notifications"
app_email = "prabakaran.b@finstein.ai"
app_license = "mit"
app_logo_url = "/assets/notify/images/logo.png"
app_icon = "octicon octicon-bell"
app_color = "#4C5BD4"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "notify",
		"logo": "/assets/notify/images/logo.png",
		"title": "Notify",
		"route": "/app/notify-settings",
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/notify/css/notify.css"
# app_include_js = "/assets/notify/js/notify.js"

# include js, css files in header of web template
# web_include_css = "/assets/notify/css/notify.css"
# web_include_js = "/assets/notify/js/notify.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "notify/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

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
# app_include_icons = "notify/public/icons.svg"

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
# 	"methods": "notify.utils.jinja_methods",
# 	"filters": "notify.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "notify.install.before_install"
# after_install = "notify.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "notify.uninstall.before_uninstall"
# after_uninstall = "notify.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "notify.utils.before_app_install"
# after_app_install = "notify.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "notify.utils.before_app_uninstall"
# after_app_uninstall = "notify.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "notify.notifications.get_notification_config"

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
# 	"ToDo": "custom_app.overrides.CustomToDo"
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
# 		"notify.tasks.all"
# 	],
# 	"daily": [
# 		"notify.tasks.daily"
# 	],
# 	"hourly": [
# 		"notify.tasks.hourly"
# 	],
# 	"weekly": [
# 		"notify.tasks.weekly"
# 	],
# 	"monthly": [
# 		"notify.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "notify.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "notify.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "notify.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["notify.utils.before_request"]
# after_request = ["notify.utils.after_request"]

# Job Events
# ----------
# before_job = ["notify.utils.before_job"]
# after_job = ["notify.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"notify.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


# =============================================================================
# Notify — active configuration
# =============================================================================

# Desk client: registers the service worker, requests permission, registers the
# FCM token, and shows in-app toasts + sound when the tab is focused.
# Referenced as a *bundle* so Frappe serves it with a content-hash filename that
# auto-busts the browser cache on every change (a plain /assets path is cached forever).
app_include_js = "notify.bundle.js"

# Inject the (public) Firebase web config into bootinfo for logged-in desk users.
extend_bootinfo = "notify.api.boot_firebase_config"

# Core dispatcher: every bell notification (Notification Log) becomes a push.
# PWA Notification is HRMS's own approval/leave/expense notification doctype.
doc_events = {
	"Notification Log": {
		"after_insert": "notify.dispatcher.on_notification_log",
	},
	"PWA Notification": {
		"after_insert": "notify.dispatcher.on_pwa_notification",
	},
	# Wildcard: powers role/access fan-out rules (Notify Rule). Cheap no-op
	# for doctypes without a rule (fast cached membership check).
	"*": {
		"after_insert": "notify.dispatcher.on_document_event",
		"on_update": "notify.dispatcher.on_document_event",
		"on_submit": "notify.dispatcher.on_document_event",
	},
}

# Make the Frappe HR (HRMS) ESS mobile PWA work against our direct-FCM engine
# instead of an external relay, without modifying HRMS. The PWA is hard-wired to
# call these method names; we intercept them here.
override_whitelisted_methods = {
	"notification_relay.api.get_config": "notify.api.relay_get_config",
	"frappe.push_notification.subscribe": "notify.api.subscribe",
	"frappe.push_notification.unsubscribe": "notify.api.unsubscribe",
}

# Daily cleanup of stale device tokens.
scheduler_events = {
	"daily": [
		"notify.api.cleanup_stale_devices",
	],
}

