# Firebase + Oracle alpha deployment

The frontend is hosted on Firebase Hosting Spark. The Python backend runs on an
Oracle Always Free VM behind Caddy. No billing-enabled Firebase backend is used.

## Current status

Deployment is pending Firebase ownership/site-name confirmation and Oracle SSH
details. `brawlbuddy.web.app` already serves a website. Creating project ID
`brawlbuddy` failed because it exists. The currently signed-in account cannot
access it. No Firebase project or Hosting deployment was created by these steps.

## Oracle configuration

1. Inspect the VM OS, architecture, available RAM, disk space, existing services
   and port usage before installing anything or selecting an app directory.
2. Point a user-approved hostname to the VM's reserved public IPv4 address.
3. Allow inbound TCP 80/443 in the OCI security rules and OS firewall. Restrict SSH
   as appropriate. The Compose configuration does not publish Uvicorn port 8000.
4. Install Docker with Compose if supported on the inspected VM.
5. Copy `deploy/production.env.example` to `.env.production` on the VM, fill in the
   API hostname and exact Firebase origins, and secure its permissions. Configure
   a Brawl Stars token authorized for the VM's actual outbound IP. Never upload
   the local development `.env` or SQLite database.
6. Run `docker compose --env-file .env.production up -d --build`. Check both the internal container health
   and `https://API_HOST/api/health` from outside the VM.

SQLite and Caddy certificates live in named volumes. Never use `docker compose
down --volumes` for a routine deployment. Back up SQLite with its backup API and
store a copy outside the VM. Application updates must preserve these volumes.

Public deployments disable unauthenticated resource writes. This is not Firebase
Authentication; user accounts and authenticated saves remain future work. Before
exposing the API widely, complete rate limiting, dynamic HTML escaping, cache
expiry and review of demo analytics labels.

## Firebase configuration

1. Confirm the user's authorized Firebase project and globally unique site ID.
2. Set `app/ui/config.js` to the Oracle **HTTPS origin**, without `/api`:

   ```js
   window.BRAWLBUDDY_CONFIG = { apiBaseUrl: 'https://API_HOST' };
   ```

3. Set the explicit Hosting site ID in `firebase.json` when confirmed. Keep the
   CLI project explicit: `firebase deploy --only hosting --project PROJECT_ID`.
4. Verify page routes, API lookup, allowed/rejected CORS origins, assets and mobile
   layouts on the actual deployed Firebase URL.

The upload directory is `app/ui`, so secrets, Python sources, game-data JSON and
SQLite are outside the Firebase upload. `config.js` and HTML are revalidated;
assets receive a one-hour browser cache. The API address is public configuration,
not a secret. Local development keeps an empty API origin and uses FastAPI for
both the UI and API.

## Verification

Run `python -m pytest -q` and `node --check app/ui/assets/app.js`. Deployment tests
cover missing-token fallback, allowed/rejected cross-origin requests, disabled
resource writes and frontend configuration delivery. Container and public smoke
checks must also pass on the real VM before reporting the app as deployed.
