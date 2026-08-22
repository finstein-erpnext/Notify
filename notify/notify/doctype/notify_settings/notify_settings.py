# Copyright (c) 2026, Finstein and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_time, now_datetime


class NotifySettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		custom_sound: DF.Attach | None
		default_icon: DF.AttachImage | None
		default_sound: DF.Check
		enable_mobile_push: DF.Check
		enabled: DF.Check
		firebase_api_key: DF.Data | None
		firebase_app_id: DF.Data | None
		firebase_auth_domain: DF.Data | None
		firebase_messaging_sender_id: DF.Data | None
		firebase_project_id: DF.Data | None
		firebase_vapid_key: DF.SmallText | None
		project_name: DF.Data | None
		push_all_notification_logs: DF.Check
		quiet_hours_end: DF.Time | None
		quiet_hours_start: DF.Time | None
		respect_quiet_hours: DF.Check
		service_account_json: DF.Code | None
		site_url: DF.Data | None
		stale_device_days: DF.Int
	# end: auto-generated types

	def validate(self):
		self._validate_service_account()

	def _validate_service_account(self):
		if not self.service_account_json:
			return
		try:
			data = json.loads(self.service_account_json)
		except Exception:
			frappe.throw(_("Service Account JSON is not valid JSON."))
		required = {"type", "project_id", "private_key", "client_email"}
		missing = required - set(data.keys())
		if missing:
			frappe.throw(_("Service Account JSON is missing: {0}").format(", ".join(sorted(missing))))
		# Keep the web project id in sync if not set
		if not self.firebase_project_id:
			self.firebase_project_id = data.get("project_id")

	def on_update(self):
		self._sync_site_config_for_mobile()
		# reset the cached firebase app so new credentials take effect immediately
		try:
			from notify import push

			push.reset_cache()
		except Exception:
			pass

	def _sync_site_config_for_mobile(self):
		"""The HRMS ESS PWA reads push_relay_server_url from site config and the
		'enable_push_notification_relay' flag from Push Notification Settings. Keep
		both in sync with our UI so mobile works without hand-editing config files."""
		from frappe.installer import update_site_config

		if self.enable_mobile_push:
			url = self.site_url or frappe.utils.get_url()
			update_site_config("push_relay_server_url", url)
			_set_relay_flag(1)
		else:
			# leave push_relay_server_url as-is; just hide the ESS toggle
			_set_relay_flag(0)

	# ---- accessors -------------------------------------------------------

	def get_firebase_web_config(self) -> dict:
		return {
			"apiKey": self.firebase_api_key or "",
			"authDomain": self.firebase_auth_domain or "",
			"projectId": self.firebase_project_id or "",
			"messagingSenderId": self.firebase_messaging_sender_id or "",
			"appId": self.firebase_app_id or "",
		}

	def get_service_account_dict(self) -> dict | None:
		if not self.service_account_json:
			return None
		try:
			return json.loads(self.service_account_json)
		except Exception:
			return None

	def is_web_config_complete(self) -> bool:
		return all(
			[self.firebase_api_key, self.firebase_app_id, self.firebase_messaging_sender_id, self.firebase_project_id]
		)

	def sound_url(self) -> str:
		if self.custom_sound:
			# Custom sounds are commonly uploaded as *private* Files, which the browser's
			# Audio() cannot load directly (permission + no range support). Stream those
			# through a whitelisted endpoint so the foreground chime always plays.
			if self.custom_sound.startswith("/private/"):
				return "/api/method/notify.api.notification_sound"
			return self.custom_sound
		return "/assets/notify/sounds/notify.wav"

	def is_in_quiet_hours(self) -> bool:
		if not self.respect_quiet_hours or not self.quiet_hours_start or not self.quiet_hours_end:
			return False
		now = now_datetime().time()
		start = get_time(self.quiet_hours_start)
		end = get_time(self.quiet_hours_end)
		if start <= end:
			return start <= now <= end
		return now >= start or now <= end


def _set_relay_flag(value: int):
	try:
		if frappe.db.exists("DocType", "Push Notification Settings"):
			current = frappe.db.get_single_value("Push Notification Settings", "enable_push_notification_relay")
			if int(current or 0) != value:
				frappe.db.set_single_value("Push Notification Settings", "enable_push_notification_relay", value)
	except Exception:
		pass


def get_settings() -> "NotifySettings":
	return frappe.get_cached_doc("Notify Settings")
