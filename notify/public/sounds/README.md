# Notification sound

Place a short notification sound here named **`notify.mp3`** (≈0.5–2 s, small file).

The Desk client (`public/js/notify_desk.js`) plays this file when a
message arrives while the tab is focused. Background/OS toasts and mobile pushes
use the operating-system default sound (browsers/OS do not allow a fully custom
sound for background web-push notifications).

If `notify.mp3` is absent, the code fails silently (no sound) — it will not error.
