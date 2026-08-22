// Copyright (c) 2026, Finstein and contributors
// For license information, please see license.txt

frappe.ui.form.on("Notify Settings", {
	refresh(frm) {
		// Send a test push to the current user's devices
		frm.add_custom_button(__("Send Test Notification"), () => {
			frappe.call({
				method: "notify.api.send_test_notification",
				freeze: true,
				callback: (r) => {
					if (r.message && r.message.success) {
						frappe.show_alert({ message: __("Test sent to your devices."), indicator: "green" });
					} else {
						frappe.msgprint(
							__("No push was sent. Make sure Firebase is configured and this browser is registered (open the Desk and allow notifications).")
						);
					}
				},
			});
		});

		// Convenience: paste the whole firebaseConfig {...} object to fill the web fields
		frm.add_custom_button(__("Paste firebaseConfig"), () => {
			const d = new frappe.ui.Dialog({
				title: __("Paste Firebase Web Config"),
				fields: [
					{
						fieldtype: "Code",
						fieldname: "cfg",
						label: __("firebaseConfig object or JSON"),
						reqd: 1,
						description: __("Paste the firebaseConfig = { ... } snippet from the Firebase console."),
					},
				],
				primary_action_label: __("Fill Fields"),
				primary_action(values) {
					const parsed = parse_firebase_config(values.cfg);
					if (!parsed) {
						frappe.msgprint(__("Could not parse the config. Paste the object with apiKey, projectId, etc."));
						return;
					}
					frm.set_value("firebase_api_key", parsed.apiKey || "");
					frm.set_value("firebase_auth_domain", parsed.authDomain || "");
					frm.set_value("firebase_project_id", parsed.projectId || "");
					frm.set_value("firebase_messaging_sender_id", parsed.messagingSenderId || "");
					frm.set_value("firebase_app_id", parsed.appId || "");
					d.hide();
					frappe.show_alert({ message: __("Web config filled. Now add the VAPID key and Service Account JSON."), indicator: "blue" });
				},
			});
			d.show();
		});

		// Readiness hint
		frappe.call({
			method: "notify.api.client_config",
			callback: (r) => {
				const c = r.message || {};
				const color = c.ready ? "green" : "orange";
				const msg = c.ready
					? __("Push is configured and ready.")
					: __("Not ready yet — fill in the Firebase web config, VAPID key, and Service Account JSON, then save.");
				frm.dashboard.set_headline(`<span class="indicator ${color}">${msg}</span>`);
			},
		});
	},
});

function parse_firebase_config(text) {
	if (!text) return null;
	// Try strict JSON first
	try {
		return JSON.parse(text);
	} catch (e) {
		// ignore
	}
	// Extract the { ... } block and coerce JS-object syntax to JSON
	const match = text.match(/\{[\s\S]*\}/);
	if (!match) return null;
	let body = match[0];
	// quote unquoted keys: apiKey: -> "apiKey":
	body = body.replace(/([{,]\s*)([A-Za-z0-9_]+)\s*:/g, '$1"$2":');
	// single quotes -> double quotes
	body = body.replace(/'/g, '"');
	// remove trailing commas
	body = body.replace(/,(\s*[}\]])/g, "$1");
	try {
		return JSON.parse(body);
	} catch (e) {
		return null;
	}
}
