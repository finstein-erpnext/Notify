/* Notify — Service Worker
 *
 * Served from the site root (/notify-sw.js) so its scope covers the
 * whole Desk. Receives FCM background messages and shows the OS toast, and opens
 * the target document on click.
 *
 * Firebase web config is passed as query params when the page registers this SW
 * (see notify.bundle.js), because a static SW cannot read bootinfo.
 */

/* global importScripts, firebase, clients */

importScripts("https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging-compat.js");

function paramsFromUrl() {
	const p = new URL(self.location).searchParams;
	return {
		apiKey: p.get("apiKey"),
		authDomain: p.get("authDomain"),
		projectId: p.get("projectId"),
		messagingSenderId: p.get("messagingSenderId"),
		appId: p.get("appId"),
	};
}

try {
	const config = paramsFromUrl();
	if (config.projectId) {
		firebase.initializeApp(config);
		const messaging = firebase.messaging();

		messaging.onBackgroundMessage((payload) => {
			const data = payload && payload.data ? payload.data : {};
			const title = data.title || "Notification";
			const options = {
				body: data.body || "",
				requireInteraction: false,
				data: { url: data.click_action || "/app" },
			};
			// renotify is only valid together with a non-empty tag
			if (data.notification_log) {
				options.tag = data.notification_log;
				options.renotify = true;
			}
			if (data.notification_icon) {
				options.icon = data.notification_icon;
			}
			return self.registration.showNotification(title, options);
		});
	}
} catch (e) {
	// swallow — a broken SW must not block the page
}

// Bridge every push to any open page so the Desk can show its in-app toast + chime
// even when Firebase's foreground onMessage doesn't fire. This runs IN ADDITION to
// Firebase's own handler above; it does NOT show a notification itself (the page
// decides, and only when it is visible), so there is never a duplicate OS toast.
self.addEventListener("push", (event) => {
	let data = {};
	try {
		const j = event.data && event.data.json();
		data = (j && j.data) || j || {};
	} catch (e) {
		return;
	}
	if (!data || (!data.title && !data.body)) return;
	event.waitUntil(
		self.clients
			.matchAll({ type: "window", includeUncontrolled: true })
			.then((cs) => cs.forEach((c) => c.postMessage({ __notify: true, data })))
	);
});

// Debug/test hook: a page can ask the SW to broadcast a fake bridge message so the
// in-app toast + chime path can be verified without a real FCM push.
self.addEventListener("message", (event) => {
	const m = event && event.data;
	if (!m || !m.__notifyTest) return;
	self.clients
		.matchAll({ type: "window", includeUncontrolled: true })
		.then((cs) =>
			cs.forEach((c) =>
				c.postMessage({
					__notify: true,
					data: m.data || { title: "SW Bridge Test", body: "Delivered via service worker" },
				})
			)
		);
});

self.addEventListener("notificationclick", (event) => {
	event.notification.close();
	const url = (event.notification.data && event.notification.data.url) || "/app";
	event.waitUntil(
		clients.matchAll({ type: "window", includeUncontrolled: true }).then((windowClients) => {
			for (const client of windowClients) {
				if (client.url.indexOf(url) !== -1 && "focus" in client) {
					return client.focus();
				}
			}
			if (clients.openWindow) {
				return clients.openWindow(url);
			}
		})
	);
});

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
