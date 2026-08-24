## Notify

Outlook-style **desktop pop-ups** and **mobile lock-screen push** for any Frappe/ERPNext
site — driven by the standard bell notifications. Every Notification Log (mentions,
assignments, approvals, workflow actions) is delivered to the user's registered
desktop browsers and, on Frappe HR (HRMS), to their phone's lock screen. All powered by
your own Firebase project; no external relay, no per-message cost.

- 🔔 Desktop toast at the top of the screen, even when the tab is unfocused, with sound
- 📱 Mobile lock-screen push through the Frappe HR (ESS) app
- ⚙️ Everything configured from the UI — paste your Firebase credentials, done
- 🔊 Custom notification sound, quiet hours, per-event rules, device registry
- 🧩 Works on any Frappe app (ERPNext, LMS, HR, custom apps)

### Install

```bash
bench get-app https://github.com/Finstein-Advizory/Notify.git
bench --site <site> install-app notify
```

Requires the site to be served over **HTTPS** (Web Push requirement; `localhost` is fine
for local testing).

### Configure (all from the UI)

Open **Notify Settings** (Awesomebar → "Notify Settings").

**1. Create a Firebase project** (free) at <https://console.firebase.google.com>.

**2. Web config** — Project Settings → General → *Your apps* → add a **Web app** →
*SDK setup and configuration → Config*. Copy the `firebaseConfig` object and use the
**Paste firebaseConfig** button on the settings form to fill the fields, or enter:
`API Key`, `Auth Domain`, `Project ID`, `Messaging Sender ID`, `App ID`.

**3. VAPID key** — Project Settings → **Cloud Messaging** → *Web configuration* →
*Web Push certificates* → **Generate key pair** → paste into **VAPID Public Key**.

**4. Service account** — Project Settings → **Service accounts** →
**Generate new private key** → paste the whole JSON into **Service Account JSON**.

**5. Save.** The form shows a green *"Push is configured and ready"* banner. Use
**Send Test Notification** to verify.

### Enable desktop notifications

Each user opens the Desk; a prompt offers to **Enable desktop notifications** (or run
`frappe.notify.enable()` in the console). After allowing, their browser is
registered and receives pop-ups.

### Enable mobile (Frappe HR / ESS)

Requires **HRMS** installed. In settings, turn on **Enable Mobile / ESS Push** and set the
**Public Site URL** (the HTTPS URL employees use). Employees open the Frappe HR app,
install it to the home screen, and toggle **Settings → Enable Push Notifications**.

### Settings

- **Push All Bell Notifications** — mirror every Notification Log, or use **Fin
  Notification Rule** to target specific doctypes/events with Jinja templates.
- **Custom Sound** — upload an mp3/wav played on the desktop pop-up (foreground).
- **Quiet Hours** — suppress push during a window.
- **Remove Stale Devices After** — daily cleanup of unused tokens.

### Notes & limits

- Desktop pop-ups appear when the **browser is running** (tab may be closed). A toast with
  no browser at all needs a native tray agent (out of scope).
- iOS web push requires the PWA **installed to the home screen** (iOS 16.4+).
- Custom sound applies to the desktop foreground toast; background/mobile use the OS
  notification sound (a browser limitation).

### License

MIT
