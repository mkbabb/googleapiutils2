"""
Simple example: Create a Google Doc using OAuth2 authentication.

PREREQUISITES:

1. Enable Google Drive API:
   https://console.cloud.google.com/apis/library/drive.googleapis.com

2. Create OAuth 2.0 Client ID:
   https://console.cloud.google.com/apis/credentials/oauthclient
   - Application type: Desktop app
   - Click "CREATE" and download the JSON file
   - Save as: auth/oauth2_credentials.json

3. OAuth Consent Screen (if not configured):
   https://console.cloud.google.com/apis/credentials/consent
   - User type: External (for personal accounts) or Internal (for Workspace)
   - Add your email as a test user

WHAT HAPPENS:
- First run: Opens browser to sign in and authorize the app
- Token saved automatically (auth/token.pickle)
- Future runs: Uses saved token (no browser needed)
- Created files are owned by the authenticated user

NOTE: Service account credentials (credentials.json) don't work for OAuth2.
      You need OAuth2 Client credentials (oauth2_credentials.json).
"""

from pathlib import Path

from googleapiutils2 import Drive, GoogleMimeTypes, get_oauth2_creds

# Get OAuth2 credentials - opens browser on first run
# Token file is created automatically after authorization
creds = get_oauth2_creds(
    client_config=Path("auth/client-credentials.json"),  # OAuth2 Client (NOT service account)
)

# Create Drive instance
drive = Drive(creds=creds)

# Create a Google Doc named "Hey Test"
doc = drive.create(
    name="Hey Test",
    mime_type=GoogleMimeTypes.docs,
)

print(f"Created: {doc['name']}")
print(f"URL: https://docs.google.com/document/d/{doc['id']}/edit")
