# NaSCon League — Android app

Flutter app for players, club managers, league organizers and viewers (spec Section 8).

- Installable APK: `release/app-release.apk` (Android 10 / API 29+)
- Source: `lib/`

## Run it against the backend

1. Start the backend on the laptop: `docker compose up -d --build` (API on port 8080).
2. Put the phone and laptop on the same Wi-Fi or hotspot.
3. Install `release/app-release.apk` on the phone.
4. On the sign-in screen, tap the gear icon → **Server URL** → `http://<laptop LAN IP>:8080`
   (emulator: `http://10.0.2.2:8080`) → **Test connection** → **Save**.
5. Sign in with a **Quick login** chip (all passwords `Nascon@26`):

| Role | Email |
|---|---|
| Platform Super-Admin | admin@nascon.test |
| League Organizer | organizer@nascon.test |
| Club Manager | manager@nascon.test |
| Player | player@nascon.test |
| General Viewer | viewer@nascon.test |

**Demo data:** Settings → *Use demo data (no server)* runs the app on built-in sample data that
mirrors the API, including offline behaviour. Useful if the backend is not reachable.

## Screens (spec 8.2)

| Screen | Where |
|---|---|
| Login (role-aware home) | `lib/ui/screens/login.dart`, `lib/ui/shell.dart` |
| Fixtures | Matches tab — `lib/ui/screens/fixtures.dart` |
| Match detail (live via SSE, timeline, pinned product) | `lib/ui/screens/match.dart`, `lib/data/live/sse_client.dart` |
| Standings (qualification status) | Standings tab — `lib/ui/screens/standings.dart` |
| Club profile (info, roster, staff, venue, history) | Club tab — `lib/ui/screens/club.dart` |
| Store, variant picker, cart, checkout, receipt PDF | `store.dart`, `product.dart`, `checkout.dart`, `receipt.dart` |
| Roster management (add / transfer / loan / release) | `lib/ui/screens/roster_sheet.dart` |
| Scoring entry (score, tie-break, compensation) | `lib/ui/screens/scoring.dart` |
| Sync status + pending queue | network chip on every screen, `lib/ui/screens/outbox.dart` |

## Offline (NFR-4, spec 8.4)

- Fixtures, standings, clubs, matches, sports and products are cached in SQLite
  (`lib/core/db.dart`, `lib/data/repository.dart`) and shown with "Offline · showing data from HH:MM".
- Scoring and roster actions made offline go to a persistent SQLite outbox in the exact
  Section 5.14 format (`lib/data/sync/outbox.dart`) and survive force-close.
- When the network returns the app syncs automatically (`lib/data/app_state.dart`, `syncNow`);
  Outbox → **Sync now** does the same. Per-action results (applied / already synced / rejected
  with a plain-language reason) are shown and kept in the Outbox history.

## Security

JWT stored only in Android Keystore-backed `flutter_secure_storage` (`lib/core/secure_store.dart`).
On 401 the token is cleared and the user is sent to sign-in.

## Build

```
flutter build apk --release
copy build\app\outputs\flutter-apk\app-release.apk release\app-release.apk
```
