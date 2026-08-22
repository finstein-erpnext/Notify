# Notify — Implementation Plan (PLANS.md)

> Engineering build guide for the `notify` Frappe app.
> Goal: **Outlook-style notifications** — a desktop toast at the top of the screen (even when the Frappe tab is not focused) **and** a phone lock-screen push via the HRMS ESS app — both with sound and click-through, driven by Frappe's bell notifications.
>
> Companion document: `../../Notify-Plan.md` (bench root) holds the high-level gap analysis and decisions. This file is the **step-by-step, file-by-file** execution plan.

---

## 0. How this project is delivered

- **One app repo:** `notify` (this repo) — portable, install on any site with `bench install-app notify`.
- **One-time bench infra:** a **notification relay server** + a **Firebase (FCM) project**, configured once per bench in `common_site_config.json`. Shared by all sites (like a mail server).
- **Mobile lock-screen** push specifically requires **HRMS** installed on the target site (the ESS mobile app *is* the HRMS PWA). Desktop toast is app-agnostic.

### Reused framework building blocks (do NOT rebuild)
| Building block | Location | We use it for |
|---|---|---|
| `PushNotification` client | `frappe/push_notification.py` | Sending pushes to the relay (`send_notification_to_user`, `subscribe`, token add/remove). |
| `Push Notification Settings` (Single) | `frappe/integrations/doctype/push_notification_settings/` | Enable relay + auto-registered API key/secret. |
| `subscribe` / `unsubscribe` whitelisted API | `frappe/push_notification.py` | Register a client's FCM token: `frappe.push_notification.subscribe(fcm_token, project_name)`. |
| HRMS PWA push (reference impl) | `hrms/hr/doctype/pwa_notification/pwa_notification.py`, `hrms/frontend/public/frappe-push-notification.js` | Template for our Desk web-push client + proof the mobile pipe works. |
| Desk bell (in-app) | `frappe/public/js/frappe/ui/notifications/notifications.js` | The UI we augment with an "enable desktop notifications" control. |

---

## 1. Target app layout (end state)

```
notify/
├── PLANS.md                      ← this file
├── notify/
│   ├── hooks.py                  ← doc_events, app_include_js, boot, scheduler
│   ├── api.py                    ← whitelisted endpoints (register device, prefs, test push)
│   ├── dispatcher.py             ← core: Notification Log → push to user's devices
│   ├── push.py                   ← thin wrapper around frappe.push_notification for project "notify"
│   ├── config/
│   ├── public/
│   │   ├── js/
│   │   │   ├── notify_desk.js      ← Desk client: init firebase, permission, register token, sound
│   │   │   └── firebase-config.js            ← injected web config (from site config)
│   │   ├── notify-sw.js            ← service worker (background messages → showNotification)
│   │   └── sounds/notify.mp3                 ← default notification sound
│   ├── notify/doctype/
│   │   ├── notify_settings/        ← Single: master switches, project name, sound, quiet hours
│   │   ├── notify_device/          ← one row per user+browser/device: FCM token, platform
│   │   ├── notify_rule/            ← which doctype/event → template/target (optional, Phase 3)
│   │   └── notify_log/             ← audit of sends + delivery status (optional, Phase 3)
│   ├── templates/
│   └── www/
│       └── notify-sw.js            ← (if service worker must be served from site root scope)
└── ...
```

> **Service worker scope note:** a service worker can only control pages at/below its own path. To cover the whole Desk, it must be served from a top-level path. Plan: serve `notify-sw.js` from site root via a `www/` page or a route rule, and register it with `{ scope: '/' }` (or the widest allowed). Validate scope early in Phase 2.

---

## 2. Decisions locked for this plan (adjust if changed)

| Ref | Decision | Assumed value |
|---|---|---|
| D1 | Relay hosting | **Self-host** `frappe/notification_relay` + own Firebase project |
| D2 | Desktop reach | **Web-push first**; native tray agent = optional Phase 4 |
| D3 | Event scope | **Configurable**, default = all HR/ESS + assignments + mentions + approvals + workflow |
| D4 | Pilot site | `primevyuh` |
| D5 | iOS support | Yes — document "Add to Home Screen" for iPhone users |

---

## 3. PHASE 0 — Infrastructure & pipeline proof  *(~0.5–1 day)*

**Objective:** relay live, Firebase ready, relay enabled on pilot site, and an existing HRMS push confirmed landing on a real phone. No app code yet.

### 0.1 Firebase / FCM project
- [ ] Create a free Firebase project (console.firebase.google.com).
- [ ] **Project settings → Cloud Messaging:** ensure the FCM API (V1) is enabled.
- [ ] **Add a Web App** → copy the web config: `apiKey`, `authDomain`, `projectId`, `messagingSenderId`, `appId`.
- [ ] **Cloud Messaging → Web configuration → Generate key pair** → copy the **VAPID public key**.
- [ ] **Project settings → Service accounts → Generate new private key** → download `service-account.json` (used by the relay only; keep secret).

### 0.2 Relay server (`frappe/notification_relay`)
- [ ] Deploy the relay (Docker or Go binary) on a host reachable over **HTTPS**.
- [ ] Provide it the `service-account.json` + Firebase project id (per its README).
- [ ] Confirm the relay health endpoint responds.
- [ ] Record its public URL, e.g. `https://relay.finstein.internal`.

### 0.3 Bench + site config
- [ ] Add to `sites/common_site_config.json`:
  ```json
  {
    "push_relay_server_url": "https://relay.finstein.internal"
  }
  ```
- [ ] Ensure the pilot site (`primevyuh`) is served over **HTTPS** (Web Push requirement).
- [ ] On the site: **Push Notification Settings** → tick **Enable Push Notification Relay** → Save.
      (`api_key`/`api_secret` auto-register via the relay `auth_webhook`.)

### 0.4 Prove the pipeline (before writing any app code)
- [ ] Install/confirm HRMS on `primevyuh`; open the HR PWA on a phone, grant notification permission (registers an FCM token under project `"hrms"`).
- [ ] Trigger an HR event that HRMS already pushes (e.g. approve a Leave Application for that employee).
- [ ] **Verify the phone shows a lock-screen push.** ✅ = the whole FCM path (relay + Firebase + device) works.

**Exit criteria:** real push reaches a real phone. If not, fix here before building anything.

---

## 4. PHASE 1 — Mobile ESS coverage complete  *(~1–2 days)*

**Objective:** every relevant notification for a user reaches their phone (not only the 3 HR approval events), and enrolment is smooth.

### 1.1 Wrapper module — `notify/push.py`
- [ ] `send_to_user(user, title, body, link=None, icon=None, data=None)` → constructs `PushNotification("notify")` and calls `send_notification_to_user(...)`, guarded by `is_enabled()`.
- [ ] Central place for icon default, url building, html-strip, error logging.

### 1.2 Device enrolment for mobile
- [ ] Confirm HR PWA registers tokens once relay is on (it calls `frappe.push_notification.subscribe`). Our own device registry (Phase 3) will also capture these via a shared registration endpoint.
- [ ] Employee-facing doc: how to **install** the ESS app (Android: Add to Home Screen; iOS 16.4+: Add to Home Screen → Allow Notifications).

### 1.3 Broaden mobile events (interim, before full dispatcher)
- [ ] Verify approvals/leave/expense/shift still fire.
- [ ] (Optional interim) add a couple of high-value HR events if needed for the pilot demo.

**Exit criteria:** target employee receives lock-screen push for the pilot's key events, click opens the ESS document.

---

## 5. PHASE 2 — Desktop Desk web-push (the main new build)  *(~3–4 days)*

**Objective:** an OS toast at the top of the desktop when a notification arrives on the Desk (`/app`), even when the tab is unfocused/closed (browser running), with sound and click-through. This is the piece Frappe does **not** have today.

### 2.1 Service worker — `public/notify-sw.js`
- [ ] Import Firebase compat SDK (messaging) inside the SW.
- [ ] `firebase.initializeApp(<web config>)`, `messaging.onBackgroundMessage(payload => registration.showNotification(title, {body, icon, data:{url}}))`.
- [ ] `self.addEventListener('notificationclick', ...)` → `clients.openWindow(data.url)` / focus existing.
- [ ] Serve at a **top-level scope** (see §1 scope note); register with the widest scope allowed on the Desk.

### 2.2 Desk client — `public/js/notify_desk.js`
- [ ] Loaded via `app_include_js` in `hooks.py` (Desk only).
- [ ] On load (for logged-in users): init Firebase web app with the injected `firebase-config.js`.
- [ ] Register the service worker; on ready, `getToken({ vapidKey, serviceWorkerRegistration })`.
- [ ] Send token to server: `frappe.call('notify.api.register_device', {token, platform:'desktop', user_agent})` (wraps `frappe.push_notification.subscribe`).
- [ ] `onMessage` (tab focused) → show in-app toast + play sound (`public/sounds/notify.mp3`).
- [ ] Handle `Notification.permission` states; re-register on token refresh.

### 2.3 Permission / enable UX
- [ ] Add an **"Enable desktop notifications"** control (bell dropdown item or a small settings toggle) that calls `Notification.requestPermission()` then runs registration.
- [ ] States: default (show enable button), granted (show "on" + sound toggle), denied (show help to re-enable in browser settings).
- [ ] Persist per-user preference (sound on/off) in `Notify Settings` child or user settings.

### 2.4 Config injection — `firebase-config.js`
- [ ] Expose the **public** Firebase web config + VAPID key to the browser via a `boot` hook or a whitelisted `get_client_config()` (never expose the service-account key).

### 2.5 hooks.py wiring
```python
app_include_js = ["/assets/notify/js/notify_desk.js"]
# boot: inject firebase web config for logged-in users
extend_bootinfo = "notify.api.boot_firebase_config"
```

**Exit criteria:** with the Desk tab in the background (or closed, browser open), a triggered notification pops an OS toast + sound; clicking opens the doc. Test on Chrome, Edge, Firefox.

---

## 6. PHASE 3 — Dispatcher, doctypes, scope & sound  *(~3–4 days)*

**Objective:** *every* bell notification (Notification Log) routes to the user's desktop **and** mobile devices, governed by settings/rules, with sound, dedup, quiet hours, and an audit trail.

### 6.1 Doctypes

**Notify Settings** (Single)
- `enabled` (Check), `project_name` (Data, default `notify`)
- `push_all_notification_logs` (Check), `default_sound` (Check)
- `quiet_hours_start` / `quiet_hours_end` (Time), `respect_user_quiet_hours` (Check)
- Child table `eligible_events` → links to Notify Rule
- `default_icon` (Attach Image)

**Notify Device** (per user+client)
- `user` (Link User, index), `fcm_token` (Data, unique), `platform` (Select: desktop/mobile)
- `user_agent` (Small Text), `enabled` (Check), `last_seen` (Datetime), `project` (Data)
- Purpose: "send to all my devices", stale-token cleanup.

**Notify Rule** (optional, powers D3 "configurable")
- `reference_doctype` (Link DocType), `event` (Select: New/Assignment/Mention/Workflow/Approval/Custom)
- `title_template` / `body_template` (Data/Small Text, Jinja), `link_template` (Data)
- `target` (Select: recipient/role/field), `roles` (Table MultiSelect), `sound` (Check), `enabled` (Check)

**Notify Log** (optional audit)
- `user`, `title`, `body`, `link`, `channel` (desktop/mobile/both), `status` (queued/sent/failed), `error`, `device` (Link)

### 6.2 Core dispatcher — `dispatcher.py`
- [ ] `on_notification_log(doc, method)` hooked from `Notification Log` `after_insert`.
- [ ] Resolve recipient(s); check `enabled`, quiet hours, and matching Notify Rule (if `push_all_notification_logs` off).
- [ ] Build `title`, `body`, `link`, `icon` (from the source doc / rule template).
- [ ] Call `push.send_to_user(...)` → relay delivers to *all* the user's registered devices (desktop + mobile) automatically.
- [ ] Write a `Notify Log` row; catch/log errors, never break the source transaction (wrap in try/except, use `frappe.enqueue` for heavy work).

### 6.3 hooks.py
```python
doc_events = {
    "Notification Log": {"after_insert": "notify.dispatcher.on_notification_log"},
}
scheduler_events = {
    "daily": ["notify.api.cleanup_stale_devices"],
}
```

### 6.4 Sound
- [ ] Desktop foreground: in-app `Audio(notify.mp3)` on `onMessage`.
- [ ] Desktop background + mobile: OS/channel default sound (documented limit; per-user toggle honored where possible).

### 6.5 Reliability
- [ ] Dedup (same user + reference within N seconds).
- [ ] Retry/queue via `frappe.enqueue` for sends.
- [ ] Prune tokens the relay reports invalid.

**Exit criteria:** creating any bell notification (assignment, mention, approval, workflow) delivers to the user's desktop toast + phone, subject to their settings, and is logged.

---

## 7. PHASE 4 — Optional native desktop agent  *(~3–5 days, only if required)*

Needed only if toasts must appear when the **browser is fully closed**, or a fully **custom sound** is mandatory on desktop.
- [ ] Small Electron/tray app that holds an FCM token and renders native toasts.
- [ ] Reuses the same relay + `register_device` endpoint (platform `native`).
- [ ] Packaged installer per OS.

---

## 8. Testing matrix

| Case | Desktop Chrome | Desktop Edge | Desktop Firefox | Android PWA | iOS PWA 16.4+ |
|---|---|---|---|---|---|
| Permission grant + token register | ☐ | ☐ | ☐ | ☐ | ☐ |
| Toast, tab focused (+ sound) | ☐ | ☐ | ☐ | ☐ | ☐ |
| Toast, tab unfocused/closed (browser open) | ☐ | ☐ | ☐ | n/a | n/a |
| Lock-screen push, app closed | n/a | n/a | n/a | ☐ | ☐ |
| Click opens correct document | ☐ | ☐ | ☐ | ☐ | ☐ |
| Quiet hours suppress | ☐ | ☐ | ☐ | ☐ | ☐ |
| Stale token cleanup | ☐ | ☐ | ☐ | ☐ | ☐ |

---

## 9. Configuration reference

| Key | Where | Purpose |
|---|---|---|
| `push_relay_server_url` | `common_site_config.json` | Relay endpoint (client of relay). |
| Firebase web config + VAPID | site boot / `firebase-config.js` | Browser FCM init (public). |
| `service-account.json` | relay server only | FCM Admin auth (secret). |
| Enable Push Notification Relay | `Push Notification Settings` (per site) | Turns relay on; auto-registers API key/secret. |
| `Notify Settings` | per site | App master switches, sound, quiet hours, rules. |

---

## 10. Rollout & effort

| Phase | Deliverable | Effort |
|---|---|---|
| 0 | Infra + pipeline proof | 0.5–1 d |
| 1 | Mobile ESS complete | 1–2 d |
| 2 | Desktop Desk web-push | 3–4 d |
| 3 | Dispatcher + doctypes + sound | 3–4 d |
| 4 | (Optional) native agent | 3–5 d |
| QA | Cross-browser/device + docs | 2 d |

**Core (0–3): ~8–11 working days.** Roll out to remaining sites (`kaynes`, `gridcrest`, …) by `bench install-app notify` once the relay is live for the bench.

---

## 11. Task board (execution order)

1. [ ] **P0** Firebase project + service account + VAPID.
2. [ ] **P0** Deploy relay, set `push_relay_server_url`, HTTPS on `primevyuh`.
3. [ ] **P0** Enable Push Notification Settings; prove HRMS push on a phone.
4. [ ] **P1** `push.py` wrapper; verify/broaden mobile events; enrolment docs.
5. [ ] **P2** Service worker + Desk client + permission UI + config injection + hooks.
6. [ ] **P2** Cross-browser desktop toast + sound + click-through.
7. [ ] **P3** Doctypes (Settings, Device, Rule, Log).
8. [ ] **P3** Dispatcher on `Notification Log`; rules; quiet hours; cleanup scheduler.
9. [ ] **QA** Run the testing matrix; write user + admin docs.
10. [ ] **Rollout** Install on remaining sites; monitor `Notify Log`.
11. [ ] **P4** (only if required) native tray agent.
