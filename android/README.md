# CtrlNote for Android (MVP)

A quick-settings tile and a capture screen that save notes and drawings into an Obsidian vault folder on the phone.

## Build

1. Open this `android/` folder in Android Studio (File → Open).
2. Use JDK 17.
3. Copy `local.properties.example` to `local.properties` and set your SDK path.
4. Sync Gradle → Run on a device.

> The Android Gradle Plugin fails on paths with non-ASCII characters. If your checkout lives in such a folder, copy `android/` to a plain path like `C:\CtrlNote\android` first.

## Status

Early MVP: text notes, drawing and a quick-settings tile. The trading journal is desktop-only for now.
