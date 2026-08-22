# Copyright (c) 2026, Finstein and contributors
# For license information, please see license.txt
"""Whitelisted endpoints, boot config, and scheduled maintenance for Notify."""

import frappe
from frappe import _
from frappe.utils import now_datetime

from notify import push
from notify.notify.doctype.notify_device.notify_device import (
	hash_token,
)
from notify.notify.doctype.notify_settings.notify_settings import (
	get_settings,
)


# ---------------------------------------------------------------------------
# Client config (browser)
# ---------------------------------------------------------------------------


def get_client_config() -> dict:
	"""Public Firebase web config + app flags for the browser client.

	Reads from site config:
	  - fin_firebase_config: {apiKey, authDomain, projectId, messagingSenderId, appId}
	  - fin_firebase_vapid_key: "<web push public VAPID key>"
	Never exposes the service-account key (that lives on the relay only).
	"""
	settings = get_settings()
	config = settings.get_firebase_web_config()
	vapid = settings.firebase_vapid_key
	web_config_complete = settings.is_web_config_complete()
	ready = bool(
		settings.enabled
		and web_config_complete
		and vapid
		and push.relay_available(settings.project_name or "notify")
	)
	return {
		"enabled": bool(settings.enabled),
		"ready": ready,
		"project_name": settings.project_name or "notify",
		"firebase_config": config,
		"vapid_key": vapid or "",
		"sound": bool(settings.default_sound),
		"sound_url": settings.sound_url(),
	}


@frappe.whitelist()
def client_config() -> dict:
	return get_client_config()


@frappe.whitelist(allow_guest=True, methods=["GET"])
def service_worker():
	"""Serve the FCM service worker at a top-level path with root scope.

	Frappe's static renderer refuses to serve `.js` files from `www/`, so the SW is
	served here instead. The `Service-Worker-Allowed: /` header lets the browser
	register it with scope '/' even though the script URL is under /api/method/.
	"""
	import os

	from werkzeug.wrappers import Response

	path = os.path.join(frappe.get_app_path("notify"), "service_worker.js")
	with open(path, encoding="utf-8") as f:
		content = f.read()

	response = Response(content, mimetype="application/javascript")
	response.headers["Service-Worker-Allowed"] = "/"
	response.headers["Cache-Control"] = "no-cache"
	return response


@frappe.whitelist(allow_guest=True, methods=["GET"])
def notification_sound():
	"""Stream the configured notification chime with a public, cacheable URL.

	Custom sounds are often uploaded as *private* Files (`/private/files/...`), which
	the browser's `new Audio()` cannot reliably load. Serving the bytes here makes the
	foreground chime work regardless of how the sound was uploaded. Falls back to the
	bundled public asset when no custom sound is configured or it cannot be read.
	"""
	import os

	from werkzeug.wrappers import Response

	settings = get_settings()
	content = None
	mimetype = "audio/wav"

	custom = settings.custom_sound
	if custom:
		try:
			file_doc = frappe.get_doc("File", {"file_url": custom})
			content = file_doc.get_content()
			if custom.lower().endswith(".mp3"):
				mimetype = "audio/mpeg"
			elif custom.lower().endswith(".ogg"):
				mimetype = "audio/ogg"
		except Exception:
			content = None

	if content is None:
		path = os.path.join(
			frappe.get_app_path("notify"), "public", "sounds", "notify.wav"
		)
		with open(path, "rb") as f:
			content = f.read()
		mimetype = "audio/wav"

	response = Response(content, mimetype=mimetype)
	response.headers["Cache-Control"] = "public, max-age=3600"
	response.headers["Accept-Ranges"] = "bytes"
	return response


def boot_firebase_config(bootinfo):
	"""extend_bootinfo hook: attach client config for logged-in desk users."""
	if frappe.session.user and frappe.session.user != "Guest":
		try:
			bootinfo["notify"] = get_client_config()
		except Exception:
			bootinfo["notify"] = {"enabled": False, "ready": False}


# ---------------------------------------------------------------------------
# Device registration
# ---------------------------------------------------------------------------


@frappe.whitelist()
def register_device(token: str, platform: str = "Desktop", user_agent: str = None, project: str = None):
	"""Register (or refresh) this browser/device's FCM token for the current user."""
	if not token:
		frappe.throw(_("Token is required"))
	name = _store_device(frappe.session.user, token, platform=platform or "Desktop", project=project, user_agent=user_agent)
	return {"success": True, "device": name}


def _store_device(user: str, token: str, platform: str = "Desktop", project: str = None, user_agent: str = None) -> str:
	"""Create or refresh a Notify Device row for (user, token)."""
	settings = get_settings()
	project = project or settings.project_name or "notify"
	th = hash_token(token)

	existing = frappe.db.get_value("Notify Device", {"token_hash": th}, "name")
	if existing:
		doc = frappe.get_doc("Notify Device", existing)
		doc.user = user
		doc.platform = platform or doc.platform
		if user_agent:
			doc.user_agent = user_agent
		doc.project = project
		doc.enabled = 1
		doc.last_seen = now_datetime()
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Notify Device",
				"user": user,
				"fcm_token": token,
				"platform": platform or "Desktop",
				"user_agent": user_agent,
				"project": project,
				"enabled": 1,
				"last_seen": now_datetime(),
			}
		).insert(ignore_permissions=True)
	return doc.name


# ---------------------------------------------------------------------------
# HRMS ESS / mobile PWA compatibility
#
# The Frappe HR PWA is hard-wired to call three "relay" endpoints. We override
# those method names (see hooks: override_whitelisted_methods) and point them at
# our own direct-FCM engine — so mobile works with NO external relay and NO change
# to HRMS. `notification_relay.api.get_config` -> relay_get_config;
# `frappe.push_notification.subscribe`/`unsubscribe` -> subscribe/unsubscribe.
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True, methods=["GET"])
def relay_get_config(project_name: str = None):
	"""Return firebase web config + VAPID key in the raw shape the HRMS PWA expects.

	The real relay is a Go server that returns {config, vapid_public_key} at the top
	level (not wrapped in Frappe's {"message": ...}), so we emit a raw JSON response.
	"""
	import json as _json

	from werkzeug.wrappers import Response

	settings = get_settings()
	cfg = settings.get_firebase_web_config()
	vapid = settings.firebase_vapid_key or ""
	body = _json.dumps({"config": cfg, "vapid_public_key": vapid})
	return Response(body, mimetype="application/json")


@frappe.whitelist(methods=["GET"])
def subscribe(fcm_token: str = None, project_name: str = None):
	"""Override of frappe.push_notification.subscribe — store the PWA's token locally."""
	if not fcm_token:
		frappe.throw(_("fcm_token is required"))
	user_agent = frappe.get_request_header("User-Agent")
	_store_device(frappe.session.user, fcm_token, platform="Mobile", project=project_name or "hrms", user_agent=user_agent)
	# HRMS calls this as a GET; Frappe does not auto-commit writes on GET.
	frappe.db.commit()  # nosemgrep
	return {"success": True, "message": "Subscribed"}


@frappe.whitelist(methods=["GET"])
def unsubscribe(fcm_token: str = None, project_name: str = None):
	"""Override of frappe.push_notification.unsubscribe — remove the PWA's token."""
	if fcm_token:
		name = frappe.db.get_value("Notify Device", {"token_hash": hash_token(fcm_token)}, "name")
		if name:
			frappe.delete_doc("Notify Device", name, ignore_permissions=True, force=True)
			frappe.db.commit()  # nosemgrep — GET request needs explicit commit
	return {"success": True, "message": "Unsubscribed"}


@frappe.whitelist()
def unregister_device(token: str, project: str = None):
	"""Remove this device's token (e.g. on logout / permission revoked)."""
	user = frappe.session.user
	settings = get_settings()
	project = project or settings.project_name or "notify"
	th = hash_token(token)

	name = frappe.db.get_value("Notify Device", {"token_hash": th}, "name")
	if name:
		frappe.delete_doc("Notify Device", name, ignore_permissions=True, force=True)
	push.remove_token(user, token, project)
	return {"success": True}


@frappe.whitelist()
def heartbeat(token: str):
	"""Update last_seen so the device is not pruned as stale."""
	name = frappe.db.get_value("Notify Device", {"token_hash": hash_token(token)}, "name")
	if name:
		frappe.db.set_value("Notify Device", name, "last_seen", now_datetime(), update_modified=False)
	return {"success": bool(name)}


# ---------------------------------------------------------------------------
# Test + maintenance
# ---------------------------------------------------------------------------


@frappe.whitelist()
def send_test_notification():
	"""Send a test push to the current user's devices."""
	user = frappe.session.user
	ok = push.send_to_user(
		user=user,
		title=_("Notify test"),
		body=_("If you can see this, desktop/mobile push is working."),
		link=frappe.utils.get_url("/app"),
	)
	return {"success": ok}


def cleanup_stale_devices():
	"""Daily scheduler: remove devices not seen within the configured window."""
	settings = get_settings()
	days = settings.stale_device_days or 60
	cutoff = frappe.utils.add_days(now_datetime(), -days)
	stale = frappe.get_all(
		"Notify Device",
		filters=[["last_seen", "<", cutoff]],
		pluck="name",
	)
	for name in stale:
		frappe.delete_doc("Notify Device", name, ignore_permissions=True, force=True)
	if stale:
		frappe.db.commit()
