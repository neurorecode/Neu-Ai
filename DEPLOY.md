# Deploying Neu AI to your VPS (Hostinger / any Ubuntu server)

Everything runs under Docker Compose: Caddy (auto-HTTPS) + FastAPI backend +
Postgres 16. Total setup time: ~15 minutes.

## 0. Prerequisites

- Ubuntu VPS (2 vCPU / 4 GB RAM is plenty; Sarvam & Claude do the heavy lifting)
- A domain/subdomain **A record** pointed at the VPS IP, e.g. `neu.neurorecode.in → 1.2.3.4`
  (Add it wherever the `neurorecode.in` DNS is managed. Wait until
  `ping neu.neurorecode.in` resolves to the VPS.)
- Your Google OAuth Client ID + Secret, Sarvam API key, Anthropic API key

## 1. Install Docker (once)

```bash
ssh root@YOUR_VPS_IP
curl -fsSL https://get.docker.com | sh
```

## 2. Get the code

```bash
git clone https://github.com/neurorecode/Neu-Ai.git
cd Neu-Ai/deploy
```

## 3. Configure

```bash
cp .env.example .env
nano .env
```

Fill in every value:

- `DOMAIN` — your subdomain (no `https://`)
- `POSTGRES_PASSWORD` — run `openssl rand -hex 16`
- `SECRET_KEY` — run `openssl rand -hex 32`
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`
- `ANTHROPIC_API_KEY`, `SARVAM_API_KEY`

Then add the production redirect URI to Google:
**console.cloud.google.com → your project → Clients → your web client →
Authorized redirect URIs → add** `https://YOUR-DOMAIN/api/auth/google/callback`

## 4. Launch

```bash
docker compose up -d --build
```

First start takes a few minutes (image builds + Caddy fetching the TLS
certificate). Then open `https://YOUR-DOMAIN` — you should see the Neu AI
sign-in page. Sign in with your Google Workspace account.

## 5. Backups (recommended)

```bash
chmod +x backup.sh
crontab -e
# add:
0 3 * * * /root/Neu-Ai/deploy/backup.sh >> /var/log/neu-backup.log 2>&1
```

Nightly `pg_dump` with 14-day rotation into `deploy/backups/`. For off-site
copies, configure `rclone` and uncomment the last line of `backup.sh`.

## Day-2 operations

| Task | Command (from `Neu-Ai/deploy`) |
|---|---|
| Update to latest code | `git pull && docker compose up -d --build` |
| View logs | `docker compose logs -f backend` |
| Restart | `docker compose restart` |
| Database shell | `docker compose exec db psql -U neu neu` |
| Manual backup | `./backup.sh` |
| Restore a backup | `gunzip -c backups/neu-....sql.gz \| docker compose exec -T db psql -U neu neu` |

Database migrations run automatically on every backend start
(`alembic upgrade head`), so `git pull && up --build` is the whole upgrade story.

## Troubleshooting

- **Browser shows certificate error** — DNS hasn't propagated yet or port
  80/443 is blocked. Check `docker compose logs web`, and Hostinger's firewall
  panel (allow 80 + 443).
- **Google login redirects to an error** — the production redirect URI is
  missing in the Google client, or `DOMAIN`/`BACKEND_URL` mismatch. It must be
  exactly `https://YOUR-DOMAIN/api/auth/google/callback`.
- **"Sign-ins from your email domain are not allowed"** — unset
  `AUTH_ALLOWED_EMAIL_DOMAINS` or include your domain in it.
- **Uploads fail with unsupported type** — check the file extension is one of
  wav/mp3/m4a/mp4/webm/ogg/flac/aac.
