// Notify — Enable / Disable desktop notifications from the user's own User form.
//
// Only adds toolbar buttons; it never sets a field on the document, so it
// can't leave the form in the "Not Saved" state.

frappe.ui.form.on("User", {
	refresh(frm) {
		notify_render_buttons(frm);
	},
});

function notify_render_buttons(frm) {
	const group = __("Notifications");
	[__("Enable"), __("Disable"), __("Send Test")].forEach((label) =>
		frm.remove_custom_button(label, group)
	);

	// Push is per browser, so only offer it on the logged-in user's own record.
	if (frm.is_new() || frm.doc.name !== frappe.session.user) return;
	// Always offer the button on the user's own record; enable() explains why it
	// can't turn on (unsupported/insecure browser, push not configured, blocked).
	const notify = frappe.notify;
	if (!notify || !notify.enable) return;

	if (notify.isEnabled()) {
		frm.add_custom_button(
			__("Disable"),
			async () => {
				await notify.disable();
				notify_render_buttons(frm);
			},
			group
		);
		frm.add_custom_button(__("Send Test"), () => notify.sendTest(), group);
	} else {
		frm.add_custom_button(
			__("Enable"),
			async () => {
				await notify.enable();
				notify_render_buttons(frm);
			},
			group
		);
	}
}
