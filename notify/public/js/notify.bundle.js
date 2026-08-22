/* Notify — Desk client
 *
 * - Loads the Firebase web SDK (compat) on demand.
 * - Registers the root-scope service worker (/notify-sw.js).
 * - Requests notification permission and registers the FCM token with the server.
 * - Shows an in-app toast + plays a sound when a message arrives while the tab is focused.
 *
 * Config comes from `frappe.boot.notify` (injected by extend_bootinfo).
 */

frappe.provide("frappe.notify");

(function () {
	const FIREBASE_VERSION = "10.12.2";
	const SW_URL = "/api/method/notify.api.service_worker";

	const state = {
		cfg: null,
		messaging: null,
		token: null,
		swReg: null,
		initialised: false,
		bridgeBound: false,
	};

	function cfg() {
		return (frappe.boot && frappe.boot.notify) || {};
	}

	function supported() {
		return "serviceWorker" in navigator && "Notification" in window && "PushManager" in window;
	}

	function loadScript(src) {
		return new Promise((resolve, reject) => {
			if (document.querySelector(`script[src="${src}"]`)) return resolve();
			const s = document.createElement("script");
			s.src = src;
			s.onload = resolve;
			s.onerror = reject;
			document.head.appendChild(s);
		});
	}

	async function loadFirebase() {
		const base = `https://www.gstatic.com/firebasejs/${FIREBASE_VERSION}`;
		await loadScript(`${base}/firebase-app-compat.js`);
		await loadScript(`${base}/firebase-messaging-compat.js`);
	}

	function swUrlWithConfig(fb) {
		const p = new URLSearchParams({
			apiKey: fb.apiKey || "",
			authDomain: fb.authDomain || "",
			projectId: fb.projectId || "",
			messagingSenderId: fb.messagingSenderId || "",
			appId: fb.appId || "",
		});
		return `${SW_URL}?${p.toString()}`;
	}

	async function ensureFirebase() {
		if (state.initialised) return true;
		const c = cfg();
		if (!c.ready || !c.firebase_config || !c.vapid_key) return false;
		if (!supported()) return false;

		await loadFirebase();
		if (!window.firebase.apps.length) {
			window.firebase.initializeApp(c.firebase_config);
		}
		state.swReg = await navigator.serviceWorker.register(swUrlWithConfig(c.firebase_config), {
			scope: "/",
		});
		// getToken() fails if the SW isn't active yet — wait for it to be ready/controlling.
		try {
			await navigator.serviceWorker.ready;
		} catch (e) {
			/* ignore — proceed and let getToken retry */
		}
		state.messaging = window.firebase.messaging();

		// Foreground messages -> in-app toast + sound (Firebase's own path)...
		state.messaging.onMessage((payload) => onForegroundMessage(payload));
		// ...plus our reliable SW->page bridge as a backstop.
		bindServiceWorkerBridge();
		state.cfg = c;
		state.initialised = true;
		return true;
	}

	async function registerToken() {
		const c = state.cfg || cfg();
		let token;
		try {
			token = await state.messaging.getToken({
				vapidKey: c.vapid_key,
				serviceWorkerRegistration: state.swReg,
			});
		} catch (e) {
			// Common causes: permission not granted, wrong VAPID key, SW not active,
			// or the browser blocked push. Surface it instead of failing silently.
			state.lastError = String((e && e.message) || e);
			console.error("Notify: getToken failed —", e);
			return null;
		}
		if (!token) {
			state.lastError = "getToken returned empty (permission not granted?)";
			console.warn("Notify: getToken returned no token");
			return null;
		}
		state.token = token;
		state.lastError = null;
		try {
			await frappe.call({
				method: "notify.api.register_device",
				args: { token, platform: "Desktop", user_agent: navigator.userAgent },
			});
		} catch (e) {
			state.lastError = "register_device call failed: " + String((e && e.message) || e);
			console.error("Notify: register_device failed —", e);
			return null;
		}
		return token;
	}

	// Dedup so the same message shown via BOTH Firebase's onMessage and our
	// service-worker bridge (below) only produces one toast/chime.
	const _recent = new Map();
	function _isDuplicate(data) {
		const key = data.notification_log || (data.title || "") + "|" + (data.body || "");
		const now = Date.now();
		for (const [k, t] of _recent) {
			if (now - t > 10000) _recent.delete(k);
		}
		if (_recent.has(key)) return true;
		_recent.set(key, now);
		return false;
	}

	// Single entry point for showing a message inside the Desk (toast + OS popup + sound).
	function handleForeground(data) {
		data = data || {};
		if (_isDuplicate(data)) return;
		const title = data.title || __("Notification");
		const body = data.body || "";

		// 1) In-app toast (visible while working inside the Desk)
		frappe.show_alert(
			{
				message: `<b>${frappe.utils.escape_html(title)}</b><br>${frappe.utils.escape_html(body)}`,
				indicator: "blue",
			},
			8
		);

		// 2) Real OS desktop popup — even though the tab is focused — so it behaves
		//    like Outlook. Uses the service worker registration when available.
		showOsNotification(title, body, data);

		playSound();
	}

	// Firebase's foreground callback (fires only when it decides the tab is focused).
	function onForegroundMessage(payload) {
		handleForeground((payload && payload.data) || {});
	}

	// Bridge: our service worker posts every push here too, so the in-app toast +
	// chime fire even when Firebase's onMessage doesn't (its foreground/background
	// routing is unreliable across browsers). We only act when the tab is actually
	// visible; when it's hidden, the OS notification from the SW is the right UX.
	function bindServiceWorkerBridge() {
		if (state.bridgeBound || !("serviceWorker" in navigator)) return;
		navigator.serviceWorker.addEventListener("message", (event) => {
			const msg = event && event.data;
			if (!msg || !msg.__notify) return;
			if (document.visibilityState !== "visible") return;
			handleForeground(msg.data || {});
		});
		state.bridgeBound = true;
	}

	function showOsNotification(title, body, data) {
		if (!("Notification" in window) || Notification.permission !== "granted") return;
		const options = {
			body: body || "",
			// When our own chime is unlocked we play it via Audio() and keep the OS
			// toast silent to avoid a double sound. If audio is NOT yet unlocked
			// (browser autoplay policy), let the OS toast make the system sound so the
			// user always hears *something*.
			silent: _audioUnlocked,
			data: { url: data.click_action || "/app" },
		};
		// renotify is only valid together with a non-empty tag
		if (data.notification_log) {
			options.tag = data.notification_log;
			options.renotify = true;
		}
		if (data.notification_icon) options.icon = data.notification_icon;
		try {
			if (state.swReg && state.swReg.showNotification) {
				state.swReg.showNotification(title, options);
			} else {
				new Notification(title, options);
			}
		} catch (e) {
			try {
				new Notification(title, { body: body || "" });
			} catch (e2) {
				/* ignore */
			}
		}
	}

	// ---- Sound (with autoplay-policy unlock) --------------------------------
	// Browsers block Audio.play() until the user has interacted with the page.
	// A push arrives with no user gesture, so we keep ONE reusable <audio> element
	// and prime it on the first click/keypress so later chimes are allowed to play.
	let _audio = null;
	let _audioUnlocked = false;

	function getAudio() {
		if (!_audio) {
			const c = state.cfg || cfg();
			_audio = new Audio(c.sound_url || "/assets/notify/sounds/notify.mp3");
			_audio.preload = "auto";
			_audio.volume = 0.6;
		}
		return _audio;
	}

	function unlockAudio() {
		if (_audioUnlocked) return;
		const a = getAudio();
		const wasMuted = a.muted;
		a.muted = true;
		const p = a.play();
		if (p && p.then) {
			p.then(() => {
				a.pause();
				a.currentTime = 0;
				a.muted = wasMuted;
				_audioUnlocked = true;
			}).catch(() => {
				a.muted = wasMuted;
			});
		} else {
			a.muted = wasMuted;
			_audioUnlocked = true;
		}
	}

	function bindAudioUnlock() {
		["pointerdown", "keydown", "touchstart"].forEach((ev) =>
			window.addEventListener(ev, unlockAudio, { passive: true, capture: true })
		);
	}

	function playSound() {
		const c = state.cfg || cfg();
		if (!c.sound) return;
		try {
			const a = getAudio();
			a.currentTime = 0;
			const p = a.play();
			if (p && p.catch) {
				p.catch((err) => {
					// Autoplay blocked: the user hasn't interacted with this tab yet, so
					// the browser refuses to play audio. Show a visible one-click prompt
					// (the click both unlocks audio and plays the chime immediately).
					console.warn("Notify: chime blocked by autoplay policy", err);
					showSoundPrompt();
				});
			}
		} catch (e) {
			console.warn("Notify: chime failed to play", e);
		}
	}

	// Visible fallback when the browser blocks the chime before any user gesture.
	let _soundPromptShown = false;
	function showSoundPrompt() {
		if (_soundPromptShown || _audioUnlocked) return;
		_soundPromptShown = true;
		frappe.show_alert(
			{
				message:
					"🔔 " +
					__("Click here to enable notification sound") +
					' <a href="#" onclick="frappe.notify.enableSound();return false;" ' +
					'style="text-decoration:underline;font-weight:600">' +
					__("Enable") +
					"</a>",
				indicator: "orange",
			},
			15
		);
	}

	// Public: called by the "Enable notifications" action (needs a user gesture on some browsers).
	async function enable() {
		// This runs inside a click handler — a valid gesture to unlock audio.
		unlockAudio();
		if (!supported()) {
			frappe.msgprint(__("This browser does not support desktop notifications."));
			return;
		}
		const ok = await ensureFirebase();
		if (!ok) {
			frappe.msgprint(__("Push notifications are not configured on this site yet."));
			return;
		}
		const permission = await Notification.requestPermission();
		if (permission !== "granted") {
			frappe.show_alert({ message: __("Notifications were blocked."), indicator: "orange" });
			return;
		}
		const token = await registerToken();
		if (token) {
			markEnabled(); // remember so the banner never nags again on this browser
			removeBanner();
			frappe.show_alert({ message: __("Desktop notifications enabled."), indicator: "green" });
		} else {
			frappe.msgprint({
				title: __("Could not register this browser"),
				indicator: "red",
				message:
					__("Notifications are allowed, but registering the push token failed.") +
					"<br><b>" +
					frappe.utils.escape_html(state.lastError || "unknown error") +
					"</b><br>" +
					__("Reload the page and try again; if it persists, check the Firebase VAPID key in Notify Settings."),
			});
		}
	}

	async function sendTest() {
		await frappe.call({ method: "notify.api.send_test_notification" });
		frappe.show_alert({ message: __("Test notification sent."), indicator: "blue" });
	}

	// ---- Persistent "enable notifications" banner (like camera/mic prompts) ----
	const BANNER_ID = "notify-banner";
	const LS_ENABLED = "notify_enabled"; // this browser has enabled before
	const LS_DISMISSED = "notify_dismissed"; // user closed the banner on purpose

	function _lsGet(k) {
		try {
			return localStorage.getItem(k) === "1";
		} catch (e) {
			return false;
		}
	}
	function _lsSet(k) {
		try {
			localStorage.setItem(k, "1");
		} catch (e) {
			/* private mode / storage disabled — ignore */
		}
	}
	function _lsClear(k) {
		try {
			localStorage.removeItem(k);
		} catch (e) {
			/* ignore */
		}
	}
	function markEnabled() {
		_lsSet(LS_ENABLED);
		_lsClear(LS_DISMISSED);
	}
	function wasEnabled() {
		return _lsGet(LS_ENABLED);
	}

	function removeBanner() {
		const el = document.getElementById(BANNER_ID);
		if (el) el.remove();
	}

	function showEnableBanner(permission) {
		if (document.getElementById(BANNER_ID)) return;
		// Never nag again once the user has actually ENABLED notifications on this browser.
		// (Dismissing only hides it for the current page load — it should keep offering
		// the option until notifications are really turned on.)
		if (wasEnabled()) return;

		const bar = document.createElement("div");
		bar.id = BANNER_ID;
		bar.setAttribute(
			"style",
			"position:fixed;top:0;left:0;right:0;z-index:1031;" +
				"background:#2490ef;color:#fff;padding:9px 16px;" +
				"display:flex;align-items:center;justify-content:center;gap:14px;" +
				"font-size:13px;line-height:1.3;box-shadow:0 1px 6px rgba(0,0,0,.18)"
		);

		const denied = permission === "denied";
		const text = document.createElement("span");
		text.innerHTML = denied
			? "🔔 " +
			  __("Notifications are blocked. Click the lock/tune icon in the address bar → Site settings → allow Notifications, then reload.")
			: "🔔 " + __("Turn on notifications to get desktop alerts and sound for new updates.");
		bar.appendChild(text);

		if (!denied) {
			const btn = document.createElement("button");
			btn.textContent = __("Enable Notifications");
			btn.setAttribute(
				"style",
				"background:#fff;color:#2490ef;border:none;border-radius:6px;" +
					"padding:5px 14px;font-weight:600;cursor:pointer;white-space:nowrap"
			);
			btn.onclick = async () => {
				await enable();
				if (Notification.permission === "granted") removeBanner();
				else if (Notification.permission === "denied") {
					removeBanner();
					showEnableBanner("denied");
				}
			};
			bar.appendChild(btn);
		}

		const close = document.createElement("span");
		close.textContent = "✕";
		close.title = __("Dismiss");
		close.setAttribute("style", "cursor:pointer;opacity:.85;margin-left:6px;font-size:15px");
		close.onclick = removeBanner; // hide for now; reappears next load until actually enabled
		bar.appendChild(close);

		document.body.appendChild(bar);

		// nudge the navbar down so the banner doesn't cover it
		const navbar = document.querySelector(".navbar");
		if (navbar) navbar.style.top = bar.offsetHeight + "px";
	}

	// Auto-init: register silently if granted, else keep prompting via a top banner.
	async function autoInit() {
		if (!supported()) return;
		const c = cfg();
		if (!c.ready) return;

		// Prime the chime on the first user interaction so foreground sounds are allowed.
		bindAudioUnlock();
		// Bind the SW->page bridge early (harmless without permission) so the in-app
		// toast + chime fire as soon as pushes start arriving.
		bindServiceWorkerBridge();

		if (Notification.permission === "granted") {
			markEnabled(); // permission is live — record it so we never nag again
			removeBanner();
			try {
				const ok = await ensureFirebase();
				if (ok) await registerToken();
			} catch (e) {
				console.warn("Notify init failed", e);
			}
		} else if (wasEnabled()) {
			// Enabled before but permission is not currently granted (e.g. revoked in the
			// browser) -> stay quiet. They can re-enable via frappe.notify.register()
			// or Notify Settings.
			removeBanner();
		} else {
			// Not enabled yet -> offer the enable banner (shows each load until enabled).
			showEnableBanner(Notification.permission);
		}
	}

	frappe.notify.enable = enable;
	frappe.notify.sendTest = sendTest;
	frappe.notify.state = state;
	// Force (re-)registration of this browser's push token and report the result.
	frappe.notify.register = async function () {
		if (Notification.permission !== "granted") {
			const perm = await Notification.requestPermission();
			if (perm !== "granted") {
				frappe.msgprint(__("Notifications are not allowed for this site."));
				return null;
			}
		}
		const ok = await ensureFirebase();
		if (!ok) {
			frappe.msgprint(__("Push is not configured/ready on this site."));
			return null;
		}
		const token = await registerToken();
		if (token) {
			markEnabled();
			removeBanner();
			frappe.show_alert({ message: __("This browser is registered for push."), indicator: "green" });
			console.log("Notify token:", token);
		} else {
			frappe.msgprint(__("Registration failed: ") + (state.lastError || "unknown"));
		}
		return token;
	};
	// Clear the "don't nag" flags and show the enable banner again (e.g. if dismissed by mistake).
	frappe.notify.resetPrompt = function () {
		_lsClear(LS_ENABLED);
		_lsClear(LS_DISMISSED);
		if (Notification.permission !== "granted") showEnableBanner(Notification.permission);
		else frappe.show_alert({ message: __("Notifications are already enabled."), indicator: "green" });
	};

	// --- Debug helpers (run from the browser console) ------------------------
	// frappe.notify.playSound()  -> play the chime directly (bypasses FCM)
	// frappe.notify.simulate()   -> fake a foreground message (toast+OS+sound)
	// frappe.notify.diagnose()   -> print why sound/popup may not work
	frappe.notify.playSound = playSound;
	frappe.notify.unlockAudio = unlockAudio;
	// Called from the visible "Enable notification sound" prompt (a real click gesture).
	frappe.notify.enableSound = function () {
		_audioUnlocked = false; // force a fresh unlock attempt inside this gesture
		const a = getAudio();
		a.muted = false;
		a.currentTime = 0;
		const p = a.play();
		if (p && p.then) {
			p.then(() => {
				_audioUnlocked = true;
				frappe.show_alert({ message: __("Notification sound enabled."), indicator: "green" }, 4);
			}).catch((e) => {
				console.warn("Notify: could not enable sound", e);
				frappe.show_alert(
					{ message: __("Could not play sound — check the tab is not muted."), indicator: "red" },
					6
				);
			});
		}
	};
	frappe.notify.simulate = function () {
		onForegroundMessage({ data: { title: "Simulated", body: "Foreground test message" } });
	};
	// Round-trips through the service worker to prove the real push->page bridge works.
	frappe.notify.testBridge = function (data) {
		bindServiceWorkerBridge();
		const sw = (state.swReg && (state.swReg.active || state.swReg.installing)) ||
			(navigator.serviceWorker && navigator.serviceWorker.controller);
		if (!sw) {
			frappe.show_alert({ message: __("No service worker registered yet."), indicator: "orange" });
			return;
		}
		sw.postMessage({ __notifyTest: true, data: data || { title: "Bridge test", body: "via service worker" } });
	};
	frappe.notify.diagnose = function () {
		const c = state.cfg || cfg();
		const info = {
			ready: c.ready,
			sound_enabled: c.sound,
			sound_url: c.sound_url,
			notification_permission: window.Notification && Notification.permission,
			messaging_initialised: state.initialised,
			has_token: !!state.token,
			audio_unlocked: _audioUnlocked,
			tab_visible: document.visibilityState,
		};
		console.table(info);
		console.log("Fetching sound_url to check it loads…");
		fetch(c.sound_url, { credentials: "same-origin" })
			.then((r) => console.log("sound_url HTTP", r.status, r.headers.get("content-type")))
			.catch((e) => console.error("sound_url fetch failed", e));
		return info;
	};

	$(document).on("app_ready", function () {
		// slight delay so boot + desk are settled
		setTimeout(autoInit, 3000);
	});
})();
