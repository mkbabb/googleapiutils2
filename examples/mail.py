from googleapiutils2 import Mail, get_oauth2_creds, ServiceAccountCredentials

creds: ServiceAccountCredentials = get_oauth2_creds(
    client_config="auth/credentials.fortinbras.json"
) # type: ignore

creds = creds.with_subject("mbabb@ridgemontcharter.org")

mail = Mail(creds=creds)

mail.send(
    sender=creds.signer_email,
    to="mbabb@ncsu.edu",
    subject="Test email from Friday Institute",
    body="This is a test email from Friday Institute using Google API.",
    user_id="me",
)
