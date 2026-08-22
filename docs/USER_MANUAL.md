# Notify — User Manual

**Version:** 1.0
**Applies to:** Frappe / ERPNext v15+
**Audience:** System administrators (setup & configuration) and end users (daily use)

---

## Table of contents

1. [What is Notify?](#1-what-is-notify)
2. [How it works](#2-how-it-works)
3. [Before you begin](#3-before-you-begin)
4. [Part A — Create a Firebase project (one-time)](#4-part-a--create-a-firebase-project-one-time)
5. [Part B — Install the app](#5-part-b--install-the-app)
6. [Part C — Configure the settings](#6-part-c--configure-the-settings)
7. [Part D — Turn on desktop notifications](#7-part-d--turn-on-desktop-notifications)
8. [Part E — Turn on mobile (ESS) notifications](#8-part-e--turn-on-mobile-ess-notifications)
9. [Using Notify](#9-using-notify)
10. [Settings reference](#10-settings-reference)
11. [Targeting specific events (Notification Rules)](#11-targeting-specific-events-notification-rules)
12. [Managing devices](#12-managing-devices)
13. [Troubleshooting](#13-troubleshooting)
14. [Frequently asked questions](#14-frequently-asked-questions)
15. [Limits & good to know](#15-limits--good-to-know)

---

## 1. What is Notify?

Notify turns your Frappe/ERPNext **bell notifications** into:

- 🔔 **Desktop pop-ups** — an alert at the top of the screen (like Outlook), with sound, even when the Frappe tab is not in front.
- 📱 **Mobile lock-screen alerts** — pushed to an employee's phone through the Frappe HR (ESS) app.

Whenever something would appear in the bell (a mention, an assignment, an approval, a workflow update), Notify also delivers it to the user's registered desktop browsers and phone. It runs on any Frappe site and works with any app (ERPNext, HR, LMS, custom apps).

---

## 2. How it works

Notify uses **Firebase Cloud Messaging (FCM)** — Google's free push service — to deliver messages to browsers and phones. You create your **own** free Firebase project, paste its credentials into the settings screen, and you're done. There is no third-party relay and no per-message cost.

```
A notification appears in the bell
        │
        ▼
Notify  ──►  Firebase Cloud Messaging (your project)
        │                        │
        │            ┌───────────┴───────────┐
        ▼            ▼                       ▼
   activity log   Desktop browser        Employee's phone
                  → pop-up + sound        → lock-screen alert
```

---

## 3. Before you begin

You will need:

- A Frappe/ERPNext **v15+** site where you are a **System Manager**.
- The site served over **HTTPS** (required by browsers for notifications; `http://localhost` also works for local testing).
- A **Google account** to create a free Firebase project.
- For mobile alerts: the **Frappe HR (HRMS)** app installed on the site.

---

## 4. Part A — Create a Firebase project (one-time)

You only do this once. Everything here is on Firebase's free plan.

### Step 1 — Create the project
1. Go to <https://console.firebase.google.com> and click **Add project**.
2. Give it a name (e.g. *My Company Notifications*) and finish. You can skip Google Analytics.

### Step 2 — Add a Web app (gives you the web config)
1. On the project home, click the **Web** icon `</>`.
2. Register the app (any nickname). You do **not** need Firebase Hosting.
3. Firebase shows a `firebaseConfig = { … }` snippet. **Keep this tab open** — you'll paste it in Part C.

### Step 3 — Generate the VAPID key (Web Push certificate)
1. Click the gear ⚙️ → **Project settings** → **Cloud Messaging** tab.
2. Under **Web configuration → Web Push certificates**, click **Generate key pair**.
3. Copy the key string it produces.

### Step 4 — Download the Service Account (server key)
1. **Project settings** → **Service accounts** tab.
2. Click **Generate new private key** → **Generate key**. A `.json` file downloads.
3. Keep this file safe — it is a **secret**.

---

## 5. Part B — Install the app

On your bench:

```bash
bench get-app notify <repository-url>
bench --site your-site install-app notify
```

The app also needs the `firebase-admin` Python package; it installs automatically with the app. If needed:

```bash
./env/bin/pip install firebase-admin
```

---

## 6. Part C — Configure the settings

Open **Notify Settings** (type it in the Awesomebar / search).

1. **Enable Notify** — leave ticked.
2. **Firebase Web Configuration** — click the **Paste firebaseConfig** button (top-right), paste the `firebaseConfig { … }` snippet from Part A Step 2, and click **Fill Fields**. This fills API Key, Auth Domain, Project ID, Messaging Sender ID and App ID automatically.
3. **VAPID Public Key** — paste the key from Part A Step 3.
4. **Service Account JSON** — open the `.json` file from Part A Step 4 and paste its **entire** contents.
5. Click **Save**.

You should see a green **"Push is configured and ready"** banner. Click **Send Test Notification** to check (first enable notifications in your browser — see Part D).

> All credentials are stored on this site only. The web config values are public identifiers; the Service Account JSON is secret and never leaves your site.

---

## 7. Part D — Turn on desktop notifications

Each user enables notifications **once** per browser:

1. Open the Desk (`/app`). A blue banner appears at the top: **"Turn on notifications…"**.
2. Click **Enable Notifications**.
3. The browser asks for permission — click **Allow**.

That's it. From then on the user receives desktop pop-ups automatically; the device registers itself silently on every login. Each different browser or computer needs its own one-time **Allow**.

> If a user previously **blocked** notifications, the banner tells them how to re-allow: click the lock/tune icon in the browser's address bar → Site settings → set **Notifications** to *Allow*, then reload.

**To enable manually** (e.g. from the console): run `frappe.notify.enable()`.

---

## 8. Part E — Turn on mobile (ESS) notifications

Requires the **Frappe HR** app installed and the site on **HTTPS**.

**Administrator (once):**
1. In **Notify Settings**, tick **Enable Mobile / ESS Push**.
2. Set **Public Site URL** to the HTTPS address employees use (e.g. `https://hr.company.com`), or leave blank to auto-detect.
3. Save.

**Each employee (once, on their phone):**
1. Open the HR app URL in the phone browser.
2. Install it: **Android (Chrome)** → menu → *Add to Home screen*; **iPhone (Safari)** → Share → *Add to Home Screen* (required on iPhone). Open it from the new icon.
3. In the app, go to **Profile → Settings → Enable Push Notifications** → **Allow**.

The phone now receives lock-screen alerts, even when the app is closed.

---

## 9. Using Notify

There is nothing to do day-to-day — it works in the background. A notification is delivered whenever the recipient would get a bell notification, for example:

- Someone **@mentions** you or **assigns** you a document
- A document is **shared** with you
- A **workflow** action needs your approval, or your request is approved/rejected
- HR events (leave, expense, shift approvals) for ESS users

Click a pop-up (desktop or phone) to **open the related document** and act on it.

To send yourself a test at any time, open **Notify Settings** and click **Send Test Notification**.

---

## 10. Settings reference

| Setting | What it does |
|---|---|
| **Enable Notify** | Master on/off switch for all notifications. |
| **Project Name** | Internal label; leave as default. |
| **Firebase Web Configuration** | The five public values that identify your Firebase web app in the browser. |
| **VAPID Public Key** | Lets browsers subscribe to push. |
| **Service Account JSON** | Secret server key used to send. |
| **Enable Mobile / ESS Push** | Turns on phone alerts via the Frappe HR app. |
| **Public Site URL** | The HTTPS address employees use for the HR app. |
| **Push All Bell Notifications** | On: mirror everything in the bell. Off: only events matched by a Notification Rule. |
| **Play Sound** | Play a sound with the desktop pop-up. |
| **Custom Sound** | Upload your own MP3/WAV (foreground desktop). |
| **Default Icon** | Image shown when the item has no icon (e.g. your logo). |
| **Respect Quiet Hours** | Pause alerts during a chosen time window. |
| **Quiet Hours Start / End** | The pause window (supports overnight windows). |
| **Remove Inactive Devices After (days)** | Auto-forget devices unused for this many days. |

---

## 11. Targeting specific events (Notification Rules)

By default **Push All Bell Notifications** is on, so everything is delivered. If you'd rather deliver only certain events:

1. Turn **Push All Bell Notifications** **off**.
2. Create **Notify Rule** records:
   - **Reference DocType** — limit to a doctype (blank = any).
   - **Event** — New, Assignment, Mention, Approval, Workflow, etc.
   - **Title / Body / Link templates** — optional Jinja templates to customise the message. Available context: `note` (the notification), `doc` (the source document), `user`.
   - **Sound** — play a sound for this rule.

Only enabled rules that match will be delivered.

---

## 12. Managing devices

Every browser/phone that enables notifications appears in **Notify Device** (user, platform, last seen). You normally never touch this list — it fills and cleans itself:

- Devices register automatically when a user allows notifications.
- Invalid tokens are removed automatically.
- Devices unused beyond the **Remove Inactive Devices** window are cleared by a daily job.

**Notify Log** records every send (who, what, status) for auditing and troubleshooting.

---

## 13. Troubleshooting

**The green "ready" banner doesn't appear.**
Make sure all Firebase web fields, the VAPID key, and the Service Account JSON are filled, then Save. The Service Account JSON must be the complete file contents.

**A user sees no "Enable" banner.**
They have already granted permission (nothing to do), or the site isn't on HTTPS. Notifications require HTTPS (or `localhost`).

**Notifications were blocked by the user.**
Browsers won't re-ask once blocked. Click the lock/tune icon in the address bar → Site settings → set **Notifications** to *Allow* → reload.

**Pop-ups don't appear even though everything is "ready" (desktop).**
The most common cause on office/corporate networks is a **firewall blocking Google's push connection**. Web push is delivered over a persistent connection to Google on **ports 5228, 5229, 5230**. To confirm, open `chrome://gcm-internals/` and check **Connection State** — if it is not **Connected** (e.g. *"WAITING FOR BACKOFF"*), the network is blocking it.
- Fix: ask IT to allow outbound to Google FCM (`mtalk.google.com`, ports **5228–5230**, plus 443), **or** test on a different network (e.g. a phone hotspot) to confirm.

**Phone gets nothing.**
- iPhone: the app must be **installed to the Home Screen** (iOS 16.4+); web push doesn't work in a plain Safari tab.
- Make sure the phone allows notifications for the app and isn't in Do Not Disturb.
- On office Wi-Fi the same port-5228 block can apply; phones usually work on mobile data.

**No sound.**
Ensure **Play Sound** is on. Custom sound plays for the desktop pop-up while the tab is in front; background and mobile alerts use the device's own notification sound (a browser/OS rule).

---

## 14. Frequently asked questions

**Do I have to register each user's device manually?**
No. Users allow notifications once per browser/phone; devices register themselves automatically after that.

**Can I enable notifications for everyone by default?**
Browsers require each user to allow once — it can't be pre-granted, except by an IT-managed browser policy (Chrome Enterprise / MDM) that auto-allows your site's URL.

**Does it cost anything?**
No. It uses your own free Firebase project and sends directly — no relay, no per-message fee.

**Which apps does it work with?**
Any Frappe app, because it hooks into the standard bell (Notification Log) — ERPNext, HR, LMS, and custom apps.

**Is my data sent anywhere?**
Credentials stay on your site. Notification delivery goes through your own Firebase project (Google), like any push notification.

---

## 15. Limits & good to know

- **Desktop pop-ups** appear when the **browser is running** (the tab may be closed/minimised). A pop-up with no browser open at all requires a native desktop app and is out of scope.
- **iPhone** web push requires the app installed to the Home Screen (iOS 16.4+).
- **Custom sound** applies to the desktop foreground pop-up; background and mobile alerts use the device's default notification sound.
- **HTTPS is required** for notifications on real devices.
- Corporate networks that block Google's push ports (5228–5230) will prevent delivery on that network; use an allowed network or ask IT to open those ports.

---

*Notify — desktop & mobile push for Frappe/ERPNext. For setup help see the README; for issues, check **Notify Log** and the troubleshooting section above.*
