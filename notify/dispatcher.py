# Copyright (c) 2026, Finstein and contributors
# For license information, please see license.txt
"""Core dispatcher: turn Frappe bell notifications (Notification Log) into pushes.

Hooked from `Notification Log` after_insert. The heavy work (relay call) runs in a
background job so document saves are never slowed down or broken by push delivery.
"""

import frappe
from frappe.utils import get_url_to_form, strip_html

from notify import push
from notify.notify.doctype.notify_settings.notify_settings import (
	get_settings,
)

# Map Notification Log `type` to our Rule `event` vocabulary.
TYPE_TO_EVENT = {
	"Assignment": "Assignment",
	"Mention": "Mention",
	"Share": "New",
	"Alert": "Custom",
	"Energy Point": "Custom",
	"Notification": "New",
}


def on_notification_log(doc, method=None):
	"""after_insert hook on Notification Log. Enqueue processing."""
	# Cheap guards inline; anything heavier happens in the background job.
	if not doc.get("for_user"):
		return
	try:
		settings = get_settings()
	except Exception:
		return
	if not settings.enabled:
		return

	try:
		frappe.enqueue(
			"notify.dispatcher.process_notification_log",
			queue="short",
			enqueue_after_commit=True,
			notification_log=doc.name,
			job_id=f"notify-{doc.name}",
			deduplicate=True,
		)
	except Exception:
		# A broken/unavailable queue must never block the source notification.
		frappe.log_error(title="Notify: enqueue failed")


def on_pwa_notification(doc, method=None):
	"""after_insert hook on HRMS 'PWA Notification'. Push to the recipient's devices."""
	if not doc.get("to_user"):
		return
	try:
		settings = get_settings()
	except Exception:
		return
	if not settings.enabled:
		return
	try:
		frappe.enqueue(
			"notify.dispatcher.process_pwa_notification",
			queue="short",
			enqueue_after_commit=True,
			pwa_notification=doc.name,
			job_id=f"notify-pwa-{doc.name}",
			deduplicate=True,
		)
	except Exception:
		frappe.log_error(title="Notify: PWA enqueue failed")


def process_pwa_notification(pwa_notification: str):
	"""Background worker for HRMS PWA Notification."""
	try:
		note = frappe.get_doc("PWA Notification", pwa_notification)
	except frappe.DoesNotExistError:
		return

	settings = get_settings()
	user = note.get("to_user")
	if not settings.enabled or not user or not _user_has_devices(user):
		return
	if not _can_access(user, note.get("reference_document_type"), note.get("reference_document_name")):
		return
	if settings.is_in_quiet_hours():
		return

	title = note.get("reference_document_type") or "Notification"
	body = strip_html(note.get("message") or "")[:1000]
	link = None
	getter = getattr(note, "get_notification_link", None)
	if callable(getter):
		try:
			link = getter()
		except Exception:
			link = None
	if not link:
		link = frappe.utils.get_url("/hrms")

	log = _log(
		user,
		frappe._dict(document_type=note.get("reference_document_type"), document_name=note.get("reference_document_name")),
		status="Queued",
		content={"title": title, "body": body, "link": link},
		devices=_device_count(user),
	)
	success = push.send_to_user(
		user=user,
		title=title,
		body=body,
		link=link,
		data={
			"reference_doctype": note.get("reference_document_type") or "",
			"reference_name": note.get("reference_document_name") or "",
		},
	)
	log.db_set("status", "Sent" if success else "Failed")


def process_notification_log(notification_log: str):
	"""Background worker: build content, apply rules/quiet hours, send push, log result."""
	try:
		note = frappe.get_doc("Notification Log", notification_log)
	except frappe.DoesNotExistError:
		return

	settings = get_settings()
	if not settings.enabled or not note.for_user:
		return

	# The per-recipient path mirrors the bell to the targeted user. Fan-out to
	# whole roles/doctypes is handled separately by Notify Rule.
	if not settings.push_all_notification_logs:
		return

	user = note.for_user

	# Skip disabled users / users with no registered devices.
	if not _user_has_devices(user):
		return

	# Access gate: never push a document the recipient cannot read.
	if not _can_access(user, note.document_type, note.document_name):
		_log(user, note, status="Skipped", error="No access to referenced document")
		return

	if settings.is_in_quiet_hours():
		_log(user, note, status="Skipped", error="Quiet hours")
		return

	content = _build_content(note, None)
	if not content["title"] and not content["body"]:
		return

	log = _log(user, note, status="Queued", content=content, devices=_device_count(user))

	success = push.send_to_user(
		user=user,
		title=content["title"],
		body=content["body"],
		link=content["link"],
		icon=content["icon"],
		data={
			"reference_doctype": note.document_type or "",
			"reference_name": note.document_name or "",
			"notification_log": note.name,
		},
	)

	log.db_set("status", "Sent" if success else "Failed")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _can_access(user: str, doctype: str | None, name: str | None) -> bool:
	"""True if the recipient may read the referenced document.

	Notifications with no document reference (e.g. plain alerts) are always allowed.
	The System Manager / Administrator bypass mirrors Frappe's own permission model.
	"""
	if not doctype or not name:
		return True
	try:
		return bool(frappe.has_permission(doctype=doctype, ptype="read", doc=name, user=user))
	except Exception:
		# if permission can't be evaluated, fail safe by not sending
		return False


def _user_has_devices(user: str) -> bool:
	return bool(
		frappe.db.exists("Notify Device", {"user": user, "enabled": 1})
	)


def _device_count(user: str) -> int:
	return frappe.db.count("Notify Device", {"user": user, "enabled": 1})


# ===========================================================================
# Role / access-based fan-out (Notify Rule)
# ===========================================================================

_RULE_CACHE_KEY = "notify_rule_doctypes"


def clear_rule_cache():
	frappe.cache.delete_value(_RULE_CACHE_KEY)


def _rule_doctypes() -> set:
	"""Cached set of DocTypes that have at least one enabled fan-out rule."""
	cached = frappe.cache.get_value(_RULE_CACHE_KEY)
	if cached is not None:
		return set(cached)
	doctypes = frappe.get_all(
		"Notify Rule", filters={"enabled": 1}, distinct=True, pluck="reference_doctype"
	)
	doctypes = [d for d in doctypes if d]
	frappe.cache.set_value(_RULE_CACHE_KEY, doctypes)
	return set(doctypes)


def on_document_event(doc, method=None):
	"""Wildcard doc hook: run enabled fan-out rules for this doctype/event.

	Kept extremely cheap for the common case (a fast cached membership test) so it
	does not slow down document saves across the system.
	"""
	try:
		if getattr(doc, "doctype", None) in ("Notify Log", "Notify Device"):
			return
		if doc.doctype not in _rule_doctypes():
			return
		settings = get_settings()
		if not settings.enabled:
			return
	except Exception:
		return

	rules = frappe.get_all(
		"Notify Rule",
		filters={"enabled": 1, "reference_doctype": doc.doctype},
		fields=["name", "trigger_event", "workflow_state"],
	)
	for r in rules:
		if not _rule_triggers(r, doc, method):
			continue
		try:
			frappe.enqueue(
				"notify.dispatcher.fan_out",
				queue="short",
				enqueue_after_commit=True,
				rule=r.name,
				doctype=doc.doctype,
				docname=doc.name,
				job_id=f"notify-fanout-{r.name}-{doc.name}",
				deduplicate=True,
			)
		except Exception:
			frappe.log_error(title="Notify: fan-out enqueue failed")


def _rule_triggers(rule, doc, method) -> bool:
	te = rule.get("trigger_event")
	if method == "after_insert":
		return te == "New Document"
	if method == "on_submit":
		return te == "On Submit"
	if method in ("on_update", "on_change"):
		if te == "On Update":
			return True
		if te == "Workflow State Reached":
			state = doc.get("workflow_state")
			if not state or state != rule.get("workflow_state"):
				return False
			# only when it actually changed into that state
			try:
				return bool(doc.has_value_changed("workflow_state"))
			except Exception:
				return True
	return False


def fan_out(rule: str, doctype: str, docname: str):
	"""Notify every user with access (or the chosen roles) about this document."""
	try:
		r = frappe.get_doc("Notify Rule", rule)
		doc = frappe.get_doc(doctype, docname)
	except frappe.DoesNotExistError:
		return

	settings = get_settings()
	if not settings.enabled or settings.is_in_quiet_hours():
		return

	recipients = _resolve_recipients(r, doctype)
	if not recipients:
		return

	content = _build_fanout_content(doc, r)
	ref = frappe._dict(document_type=doctype, document_name=docname)

	for user in recipients:
		if not _user_has_devices(user):
			continue
		if not _can_access(user, doctype, docname):
			continue
		log = _log(user, ref, status="Queued", content=content, devices=_device_count(user))
		ok = push.send_to_user(
			user=user,
			title=content["title"],
			body=content["body"],
			link=content["link"],
			data={"reference_doctype": doctype, "reference_name": docname, "rule": rule},
		)
		log.db_set("status", "Sent" if ok else "Failed")


def _resolve_recipients(rule, doctype: str) -> list:
	"""Users to notify: those holding the rule's roles (or every role that can read
	the doctype), intersected with users who actually have a registered device."""
	if rule.notify == "Users With Specific Roles":
		roles = [d.role for d in (rule.roles or []) if d.role]
	else:
		roles = _roles_with_read_access(doctype)

	if not roles:
		return []

	role_users = set(
		frappe.get_all(
			"Has Role",
			filters={"role": ["in", list(roles)], "parenttype": "User"},
			distinct=True,
			pluck="parent",
		)
	)
	device_users = set(
		frappe.get_all("Notify Device", filters={"enabled": 1}, distinct=True, pluck="user")
	)
	candidates = role_users & device_users
	candidates.discard("Guest")
	# only enabled users
	enabled = set(
		frappe.get_all(
			"User", filters={"name": ["in", list(candidates)], "enabled": 1}, pluck="name"
		)
	) if candidates else set()
	return list(enabled)


def _roles_with_read_access(doctype: str) -> set:
	roles = set(frappe.get_all("Custom DocPerm", filters={"parent": doctype, "read": 1}, pluck="role"))
	if not roles:
		roles = set(frappe.get_all("DocPerm", filters={"parent": doctype, "read": 1}, pluck="role"))
	roles.discard("")
	return roles


def _build_fanout_content(doc, rule) -> dict:
	title = f"{doc.doctype} {doc.name}"
	body = strip_html(doc.get("subject") or doc.get("title") or doc.get("naming_series") or doc.name or "")
	link = None
	try:
		link = get_url_to_form(doc.doctype, doc.name)
	except Exception:
		link = frappe.utils.get_url("/app")

	ctx = {"doc": doc, "user": None}
	if rule.get("title_template"):
		title = _render(rule.get("title_template"), ctx) or title
	if rule.get("body_template"):
		body = _render(rule.get("body_template"), ctx) or body
	if rule.get("link_template"):
		link = _render(rule.get("link_template"), ctx) or link

	if len(body) > 1000:
		body = body[:1000]
	return {"title": title, "body": body, "link": link, "icon": None}


def _build_content(note, rule) -> dict:
	title = strip_html(note.subject or "")[:140]
	body = strip_html(note.email_content or note.subject or "")
	link = _doc_link(note)
	icon = None

	if rule:
		ctx = {"note": note, "doc": _safe_ref_doc(note), "user": note.for_user}
		if rule.get("title_template"):
			title = _render(rule["title_template"], ctx) or title
		if rule.get("body_template"):
			body = _render(rule["body_template"], ctx) or body
		if rule.get("link_template"):
			link = _render(rule["link_template"], ctx) or link

	if len(body) > 1000:
		body = body[:1000]

	return {"title": title, "body": body, "link": link, "icon": icon}


def _doc_link(note):
	if note.document_type and note.document_name:
		try:
			return get_url_to_form(note.document_type, note.document_name)
		except Exception:
			return None
	if note.get("link"):
		return frappe.utils.get_url(note.link)
	return frappe.utils.get_url("/app")


def _safe_ref_doc(note):
	if note.document_type and note.document_name:
		try:
			return frappe.get_doc(note.document_type, note.document_name)
		except Exception:
			return None
	return None


def _render(template: str, context: dict) -> str:
	# nosemgrep: `template` is a Notify Rule field editable only by users with
	# write access to Notify Rule (System Manager by default), never end-user or
	# request input. This is the same trust model as Frappe's own Notification /
	# Email Template Jinja fields.
	try:
		return frappe.render_template(template, context)  # nosemgrep
	except Exception:
		return ""


def _log(user, note, status, error=None, content=None, devices=0):
	content = content or {}
	doc = frappe.get_doc(
		{
			"doctype": "Notify Log",
			"user": user,
			"status": status,
			"channel": "Both",
			"devices_count": devices,
			"title": content.get("title"),
			"body": content.get("body"),
			"link": content.get("link"),
			"reference_doctype": note.document_type,
			"reference_name": note.document_name,
			"error": error,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc
