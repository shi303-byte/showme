# ShowMe — Sovereign Vanity & Digital Persona Platform

ShowMe is an open-source, production-ready bio-link hub and Discord vanity routing gateway crafted with high-fidelity dark glassmorphism, responsive ambient backdrops, audio streaming, and upstream Discord telemetry.

---

## Railway Cloud Deployment (One-Click Ready)

This repository includes turnkey Railway deployment files:
1. **`Dockerfile`**: Lightweight Python 3.11 container with automatic SQLite initialization.
2. **`railway.json`**: Railway builder schema setting dynamic `$PORT` binding and auto-restart policies.
3. **`Procfile`**: Native worker process declaration.

### Deploying to Railway:
1. Push this folder to a GitHub repository (or upload the zip directly to Railway).
2. Create a **New Project** on Railway -> **Deploy from GitHub repo**.
3. Railway detects the `Dockerfile` and `railway.json` automatically.
4. Set an optional persistent volume on `/app` if you want SQLite database persistence across redeploys, or simply let it run statelessly.
5. Generate a Domain in Railway Settings (e.g. `showme-production.up.railway.app`).

---

## Routing & Feature Specification

- **`/`**: Public showcase portal with system telemetry (Total Operatives, Active Vanities, Routed Hits) and prominent user listings.
- **`/login`**: Operative session authentication.
- **`/register`**: Self-service username and vanity claim engine.
- **`/dashboard`**: Complete control deck:
  - Visual theme selector (Cyberpunk, Midnight Violet, Terminal Emerald, Bloodline Crimson, Cold Monochrome).
  - Ambient particle engine (Aurora Waves, Stardust, Floating Dust, Minimal Void).
  - Custom font switcher (JetBrains Mono, Syne, Plus Jakarta Sans).
  - Custom MP3 player (up to 4 mins) with autoplay gesture bypass and animated live equalizer bars.
  - Minimalist SVG social vector integration (Discord, X, GitHub, Spotify, Telegram, YouTube, Twitch, Instagram).
  - Vanity Discord routing constructor with expiration limits and telemetry tracking.
  - **Master Owner Command Center** (Privileged access to view user directory, promote co-owners, and verify badges).
- **`/inv/{slug}`**: Vanity forwarder with live Discord API member/online count check and automatic redirection.
- **`/usr/{username}`**: Public high-fidelity profile with glass cards, animated avatars, and music HUD.
- **`/download-source`**: Instant zip download endpoint to export the complete clean codebase directly from the browser.

---

## Default Root Owner Credentials

- **Username**: `owner`
- **Password**: `admin123`
- Preloaded with the golden **ARCHITECT OWNER** badge, `/inv/syndicate` vanity route, and Master Control permissions.
