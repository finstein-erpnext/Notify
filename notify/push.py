# Copyright (c) 2026, Finstein and contributors
# For license information, please see license.txt
"""Direct FCM sender for Notify (no external relay server).

Sends push messages straight to Firebase Cloud Messaging using the firebase-admin
SDK and a service-account key. Device tokens live in the `Notify Device`
doctype (populated by notify.api.register_device).

Site config keys used (in common_site_config.json or site_config.json):
  - fin_firebase_service_account_path : path to the service-account JSON
  - fin_firebase_config               : public web config (browser)  [read in api.py]
  - fin_firebase_vapid_key            : web push VAPID key            [read in api.py]

All public functions are safe: they never raise, so a notification can never break
the originating transaction.
"""

import frappe

from notify.notify.doctype.notify_settings.notify_settings import (
	get_settings,
)

# Cache the initialised firebase app per-process, keyed by service-account fingerprint.
_APP_CACHE = {}


def reset_cache():
	"""Drop cached firebase apps so new credentials take effect (called on settings save)."""
	global _APP_CACHE
	try:
		import firebase_admin

		for app in list(firebase_admin._apps.values()):
			if app.name.startswith("notify"):
				firebase_admin.delete_app(app)
	except Exception:
		pass
	_APP_CACHE = {}


def relay_available(project_name: str = "notify") -> bool:
	"""True when direct FCM sending is configured and usable."""
	return _get_app() is not None


def _get_app():
	"""Return an initialised firebase_admin app built from the service-account JSON
	stored in Notify Settings, or None if not configured."""
	sa = get_settings().get_service_account_dict()
	if not sa:
		return None

	fingerprint = str(sa.get("private_key_id") or sa.get("client_email") or sa.get("project_id"))
	cached = _APP_CACHE.get(fingerprint)
	if cached is not None:
		return cached

	try:
		import firebase_admin
		from firebase_admin import credentials
	except ImportError:
		frappe.log_error(title="Notify: firebase-admin not installed")
		return None

	try:
		app_name = f"notify_{fingerprint[:24]}"
		try:
			app = firebase_admin.get_app(app_name)
		except ValueError:
			cred = credentials.Certificate(sa)
			app = firebase_admin.initialize_app(cred, name=app_name)
		_APP_CACHE[fingerprint] = app
		return app
	except Exception:
		frappe.log_error(title="Notify: firebase init failed")
		return None


# ---------------------------------------------------------------------------
# Token registry helpers (kept for API compatibility; tokens live in our doctype)
# ---------------------------------------------------------------------------


def add_token(user: str, token: str, project_name: str = "notify") -> bool:
	# With direct FCM there is no relay to mirror to; the Device doctype is the registry.
	return True


def remove_token(user: str, token: str, project_name: str = "notify") -> bool:
	return True


def _user_tokens(user: str) -> list[dict]:
	return frappe.get_all(
		"Notify Device",
		filters={"user": user, "enabled": 1},
		fields=["name", "fcm_token"],
	)


def _disable_device(name: str, reason: str = ""):
	try:
		frappe.db.set_value("Notify Device", name, "enabled", 0, update_modified=False)
	except Exception:
		pass


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------


def send_to_user(
	user: str,
	title: str,
	body: str,
	link: str | None = None,
	icon: str | None = None,
	data: dict | None = None,
	project_name: str | None = None,
) -> bool:
	"""Send a data-message push to every enabled device of `user`.

	Uses data-only messages so our service worker / PWA client fully controls how
	the notification is displayed (title, body, icon, click_action). Returns True if
	at least one device accepted the message.
	"""
	app = _get_app()
	if not app:
		return False

	devices = _user_tokens(user)
	if not devices:
		return False

	settings = get_settings()
	if not icon and settings.default_icon:
		icon = frappe.utils.get_url(settings.default_icon)

	try:
		from firebase_admin import messaging
	except ImportError:
		return False

	# FCM data values must all be strings.
	payload = {
		"title": frappe.utils.cstr(title or "Notification"),
		"body": frappe.utils.strip_html(frappe.utils.cstr(body or ""))[:1000],
	}
	if link:
		payload["click_action"] = link
	if icon:
		payload["notification_icon"] = icon
	for k, v in (data or {}).items():
		payload[k] = frappe.utils.cstr(v)

	sent_any = False
	for dev in devices:
		token = dev.get("fcm_token")
		if not token:
			continue
		message = messaging.Message(data=payload, token=token)
		try:
			messaging.send(message, app=app)
			sent_any = True
		except messaging.UnregisteredError:
			# token no longer valid — disable the device so it is pruned
			_disable_device(dev["name"], "unregistered")
		except Exception:
			frappe.log_error(title=f"Notify: FCM send failed ({user})")

	return sent_any


def send_test(user: str) -> bool:
	return send_to_user(
		user=user,
		title="Notify test",
		body="If you can see this, push is working.",
		link=frappe.utils.get_url("/app"),
	)
