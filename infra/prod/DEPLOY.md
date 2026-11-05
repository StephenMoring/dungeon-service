# Deploying to a server

One small Linux server (a VPS such as a DigitalOcean droplet) runs everything with
Docker Compose:

- **web**: Caddy, the only thing reachable from the internet (ports 80 and 443). It
  gets and renews the HTTPS certificate, serves the built frontend, and forwards
  `/api` to the API. Built from `dungeon-web` (its `Dockerfile` and `Caddyfile`).
- **api**: dungeon-service. No published port: only Caddy can reach it.
- **db**: Postgres with pgvector. No published port: only the API and Flyway can reach it.
- **flyway**: applies `db/migrations` on every start, then exits. The local seed data
  (test users and characters) is never loaded.

Players see one site (`https://your-domain`), so the session cookie and the CSRF
check work exactly as in development.

## 1. Domain and server

1. Buy a domain from any registrar.
2. Create the server: Ubuntu 24.04 LTS, 1 GB RAM or more (2 GB is comfortable for
   building the images). Choose **SSH key** login, not a password.
3. In the registrar's DNS settings, add an **A record** for the name players will use
   (e.g. `play`, or `@` for the bare domain) pointing at the server's IP address.
   Caddy can only get a certificate once this resolves.

## 2. Harden the server

Log in as root once, create a normal user, then never log in as root again:

```bash
adduser deploy
usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
```

Turn off password and root login over SSH. In `/etc/ssh/sshd_config` set
`PasswordAuthentication no` and `PermitRootLogin no`, then:

```bash
systemctl restart ssh
```

Firewall (SSH, HTTP, HTTPS only). Docker's own port rules bypass ufw, which is why the
Compose file publishes nothing but Caddy's ports:

```bash
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp && ufw enable
```

Automatic security updates:

```bash
apt update && apt install -y unattended-upgrades && dpkg-reconfigure -plow unattended-upgrades
```

Install Docker (the official convenience script), and let `deploy` use it:

```bash
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy
```

Log out and back in as `deploy` from here on.

## 3. Get the code and settings

Clone both repositories side by side (the Compose file builds `../../../dungeon-web`):

```bash
cd ~
git clone https://github.com/StephenMoring/dungeon-service.git
git clone https://github.com/StephenMoring/dungeon-web.git
cd dungeon-service/infra/prod
cp .env.example .env
chmod 600 .env
nano .env
```

Fill in every value. Generate fresh secrets here; don't reuse the development ones:

```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

Run it once for `SECRET_KEY` and once for `POSTGRES_PASSWORD`.

In the **Discord developer portal** (your application > OAuth2 > Redirects), add
`https://your-domain/auth/callback`, matching `SITE_ADDRESS` in `.env`.

## 4. Start it

```bash
cd ~/dungeon-service/infra/prod
docker compose up -d --build
docker compose ps
```

`flyway` should show `Exited (0)`; `db` and `api` should be `healthy`; `web` `Up`.
Open `https://your-domain`. The first visit can take a few seconds while Caddy gets
the certificate. If it doesn't come up:

```bash
docker compose logs web
```

The usual cause is DNS not resolving to this server yet.

Sign in with Discord and create a character to check the whole path.

## 5. Before inviting players

- **Spend limits**: set a monthly limit in the Anthropic console and the Voyage
  dashboard. The app's own caps (`src/services/usage_service.py:LIMITS`) bound daily
  use; the console limits are the backstop.
- **Voyage payment method**: without one, Voyage allows 3 requests a minute. Each
  turn makes two, so with more than one active player memories start failing (the
  turn still works, but the DM forgets). Adding a card keeps the free tokens.
- **Backups**: schedule the nightly dump (keeps 7 days in `infra/prod/backups/`):

  ```bash
  crontab -e
  ```

  Add this line:

  ```
  15 3 * * * /home/deploy/dungeon-service/infra/prod/backup.sh >> /home/deploy/backup.log 2>&1
  ```

  Then copy the backups off the server too, e.g. turn on the provider's weekly
  snapshots, or `rsync` the `backups/` folder to your own machine or object storage.
  A backup on the same disk doesn't survive losing the server.
- **Uptime monitor**: point a free monitor (e.g. UptimeRobot) at
  `https://your-domain/api/health`.
- **Optional, Cloudflare**: putting the domain behind Cloudflare's free proxy absorbs
  floods of traffic a single small server can't. Set its SSL mode to "Full (strict)".

## Updating

```bash
cd ~/dungeon-service && git pull
cd ~/dungeon-web && git pull
cd ~/dungeon-service/infra/prod && docker compose up -d --build
```

Flyway applies any new migrations before the API starts. Clean up old image layers
occasionally:

```bash
docker image prune -f
```

## Restoring a backup

Stop the API, load a dump into the database, and start again:

```bash
cd ~/dungeon-service/infra/prod
docker compose stop api web
gunzip -c backups/dungeon-YYYY-MM-DD.sql.gz | docker compose exec -T db psql -U dungeon -d dungeon
docker compose start api web
```

`dungeon` is the `POSTGRES_USER` from `.env`. To restore into a database that already
has data, recreate it first: `docker compose down`, remove the `dungeon_pgdata` volume
with `docker volume rm dungeon_pgdata`, then `docker compose up -d db`, restore, and
`docker compose up -d`.

## Looking at things

```bash
docker compose logs -f api
docker compose exec db psql -U dungeon -d dungeon
```

The first follows the API logs, including which memories each turn recalled and any
failed Voyage or Claude calls. The second opens a database shell (nothing outside the
server can reach the database). To use a database tool from your own computer, tunnel
over SSH instead of publishing the port:

```bash
ssh -L 5433:<db container IP>:5432 deploy@your-server
```

Find the container IP with `docker inspect dungeon-db-1`.
