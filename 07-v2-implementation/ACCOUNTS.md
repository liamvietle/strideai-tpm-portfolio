# Account login rollout

Account mode is opt-in with `STRIDEAI_ACCOUNT_AUTH=true`. Deploy code first, keep
`STRIDEAI_APP_KEY` configured, then enable account mode. Visit `/app`; it redirects
to `/login`. The first owner creates a username and password and enters the
existing app key on that page. The key is checked once to claim the `viet` athlete
records. Profiles, runs, race plans, Strava credentials and Apple Health history
stay in place. No password should be supplied in chat or a deployment variable.

After owner setup, the old app key cannot authenticate browser APIs. Additional
accounts require a one-use invitation generated under You (expires after 24 hours).
New accounts receive a random athlete ID, never a caller-selected ID. Each account
connects its own Strava. Sessions expire after seven days and can be logged out.
Changing a password revokes all sessions and device keys, then signs the current
browser back in. The UI clears the old browser-local access key when signing in.

Apple Health companion users must replace their old access key with a scoped
key created under You. The companion can keep using X-StrideAI-Key; that token
is accepted only for POST /app/api/apple-health/sync, mapped to its account.
Keys expire after 90 days. Creating a replacement revokes the previous key.
The shared app key is never an account-mode fallback.

`STRIDEAI_COOKIE_SECURE` defaults to true and must remain true on production
HTTPS. False is only for isolated localhost HTTP browser tests. Cookies are
HttpOnly and SameSite=Lax; CSRF tokens protect authenticated writes. Origin
checks reject cross-origin writes. TLS/proxy forwarding must preserve the public
request scheme and host (Railway's normal HTTPS proxy configuration).

Five additive tables: accounts, account_sessions, account_invites,
account_devices and account_attempts. Passwords use salted scrypt (N=32768,r=8,p=3),
one of the configurations in the OWASP Password Storage Cheat Sheet:
https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
Session, invitation and device tokens are stored as SHA-256 digests. Login
attempts are rate limited by username and source address with SQLite-backed windows.

Central account middleware derives every existing API's athlete_id from the
session, replacing client-supplied query/body values. Recommendation outcome
writes also verify ownership. Athlete/workout endpoints retain their own
ownership checks. Historical-case retrieval filters by the signed-in athlete.
Any new body-based route that accepts athlete_id must be added to BODY_IDENTITY
(or, preferably, explicitly use request.state.account) and isolation tests.

Password recovery currently requires a trusted server operator:
`python -m app.account_admin USERNAME` with the production STRIDEAI_DB_PATH.
The command prompts without echo, updates only the existing account, and revokes
its sessions and device keys. Email reset, MFA/passkeys, account deletion/export
and a public signup/consent flow remain later work. This is invitation-only access,
not a completed public commercial account system. Do not disable account mode
as an ordinary rollback after inviting users; restore code while keeping account
protection in place and preserving the SQLite volume.
