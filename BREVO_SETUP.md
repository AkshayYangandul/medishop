# Brevo transactional email setup

## Configure credentials

Set these in `backend/.env` (keep the API key private):

```env
BREVO_API_KEY=your_brevo_transactional_api_key
```

MediShop sends transactional messages through Brevo's `POST https://api.brevo.com/v3/smtp/email` endpoint with the `api-key` header. Brevo is MediShop's only transactional email provider. A successful API response means Brevo accepted the request; it does not prove delivery to the recipient's inbox. There is no SMTP or Gmail fallback.

## Apply the database migration

Back up the database, then run this additive migration against the MediShop database:

```sh
mysql -u <database-user> -p medishop < backend/migrate_brevo_sender_identities.sql
```

It creates `email_sender_identities`. The legacy `smtp_settings` table is no longer used; this migration does not alter or remove that table or its data.

## Verify and select senders

In Brevo, add the sender or authenticate the sending domain and complete Brevo's verification process. Then open Admin → Settings → Mail Settings, add the matching sender email, display name, and optional Reply-To address. Use **Check Brevo verification** to query `GET /v3/senders`. MediShop only marks a sender verified when Brevo reports that sender active. If the endpoint is unavailable or lacks permission, MediShop returns an error and leaves the sender inactive; configure an API key with sender-read access and retry. Multiple identities can be stored; only one is active. Locally disabled identities can be re-enabled after a fresh Brevo status check confirms the sender is active and verified. Editing the sender address clears its verification and active state, so verify and activate the new address again.

Send a test email to a controlled recipient from the same screen. MediShop reports Brevo acceptance or rejection and never reports inbox delivery based only on API acceptance. Sender addresses must be verified and authorized in the Brevo account; arbitrary Gmail addresses are not assumed to be authorized.

## Troubleshooting

- `BREVO_API_KEY` missing: set the key in the backend environment and restart FastAPI so the process receives it.
- No active verified sender: add a sender, verify/activate it in Brevo, use **Check Brevo verification**, and then activate it in MediShop.
- Brevo sender check unavailable: ensure the API key can read sender configuration through `GET /v3/senders`; MediShop intentionally will not allow manual activation as a fallback.
- Brevo HTTP rejection: check the response status in backend logs (credentials and response bodies are not logged), API key permissions, account sending status, and sender authorization in Brevo.
- Connection timeout: check outbound network access to `api.brevo.com`; the message will fail and will not switch providers.
- Existing `.env` SMTP variables and any `smtp_settings` table data are not read or modified by this release. Remove them manually only after your own retention review; MediShop will not access them.
