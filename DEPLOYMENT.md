# Shared authentication deployment

Set `VIPER_JWT_SECRET` to a persistent random secret of at least 64 characters in a root-owned environment file with mode `0600`. Load that file with `EnvironmentFile=` in the service unit. Never place a production secret in this repository. Startup fails if the setting is absent or too short. `HOST` and `PORT` can be set separately; defaults remain `0.0.0.0` and `8080`.

When replacing the former embedded signing key, existing sessions must sign in again. Preserve `data/users.json` byte-for-byte: no password reset, rehash, or account migration is required. Back up the source, runtime, service configuration, and data before changing the service. Compare user-data checksums before and after restart.

Login and playlist listing never transfer ownership of guest/device playlists. Existing owners remain unchanged. Mutations require the matching authenticated user or the same private device identifier. The shared `guest_user` and `public` collections are read-only. No automatic ownership claim is provided.

Authenticated requests enforce a valid Bearer token, expiry and an existing account. New tokens use integer expiry timestamps. `/api/auth/me` reports the stored email-verification flag without modifying old account records or assuming unverified emails are verified.

Use the NextViper parser fix for dedented `else`/`elif` binding when building the runtime. Do not change password hashing or its stored format as part of this deployment.

Run the isolated HTTP regressions with:

```sh
NEXTVIPER_BIN=/path/to/nextviper python3 tests/test_auth_security.py
```

The tests generate their own synthetic accounts and temporary data directory. They verify successful existing-password login, unchanged user and playlist data during login/listing, expired and forged token rejection, ownership checks, and refusal to start without the signing secret.
