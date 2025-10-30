# mail/

Gmail API wrapper: send emails, drafts, labels, message management.

## File Tree

```
mail/
├── __init__.py          # Exports Mail
└── mail.py              # Mail class (send, draft, labels, messages)
```

## Key Classes

### Mail (mail.py)
Inherits `DriveBase` for caching, throttling, retry.

**Message Methods:**
- `send(sender, to, subject, body, html)` - Send email
- `create_draft(sender, to, subject, body, html)` - Create draft
- `list_messages(query, user_id)` - List messages (generator)
- `get_message(message_id, format, user_id)` - Get message
- `modify_message(message_id, add_label_ids, remove_label_ids, user_id)` - Update labels
- `trash_message(message_id, user_id)` - Move to trash
- `untrash_message(message_id, user_id)` - Restore from trash
- `delete_message(message_id, user_id)` - Permanently delete

**Label Methods:**
- `list_labels(user_id)` - List labels (generator)
- `get_label(label_id, user_id)` - Get label
- `create_label(name, label_list_visibility, message_list_visibility, user_id)` - Create label
- `delete_label(label_id, user_id)` - Delete label
- `modify_label(label_id, body, user_id)` - Update label

**Internal Methods:**
- `_create_message(sender, to, subject, body, html)` - Build MIME message

## Constants

### API
- `VERSION = "v1"` - Gmail API version

### Message Formats
- `"full"` - Complete message with headers and body
- `"metadata"` - Headers only
- `"minimal"` - Basic info (id, threadId)

### Label Visibility
- `"labelShow"` - Always show in label list
- `"labelHide"` - Hide from label list
- `"labelShowIfUnread"` - Show if unread messages

### Message Visibility
- `"show"` - Show in message list
- `"hide"` - Hide from message list

## Usage Examples

### Send Email
```python
from googleapiutils2 import Mail, get_oauth2_creds

# Service account with domain-wide delegation
creds = get_oauth2_creds("auth/service-account.json")
creds = creds.with_subject("user@domain.com")
mail = Mail(creds=creds)

# Plain text
mail.send(
    sender="me@example.com",
    to="recipient@example.com",
    subject="Test Email",
    body="This is a test."
)

# HTML
mail.send(
    sender="me@example.com",
    to=["user1@example.com", "user2@example.com"],
    subject="Newsletter",
    body="<h1>Welcome</h1><p>Content here</p>",
    html=True
)
```

### Drafts
```python
# Create draft
draft = mail.create_draft(
    sender="me@example.com",
    to="user@example.com",
    subject="Draft Email",
    body="This is a draft."
)
print(draft['id'])
```

### List & Search Messages
```python
# All messages
for msg in mail.list_messages():
    print(msg['id'], msg['snippet'])

# Query
for msg in mail.list_messages(query="from:user@example.com after:2024/01/01"):
    print(msg)

# Unread messages
for msg in mail.list_messages(query="is:unread"):
    print(msg['snippet'])
```

### Get Message
```python
# Full message
msg = mail.get_message(message_id, format="full")
print(msg['payload']['headers'])
print(msg['payload']['body']['data'])

# Metadata only
msg = mail.get_message(message_id, format="metadata")
headers = {h['name']: h['value'] for h in msg['payload']['headers']}
print(headers['Subject'])
```

### Labels
```python
# List labels
for label in mail.list_labels():
    print(label['name'], label['id'])

# Create label
label = mail.create_label(
    name="Important",
    label_list_visibility="labelShow",
    message_list_visibility="show"
)

# Apply label to message
mail.modify_message(
    message_id,
    add_label_ids=[label['id']]
)

# Remove label
mail.modify_message(
    message_id,
    remove_label_ids=[label['id']]
)

# Delete label
mail.delete_label(label['id'])
```

### Trash Management
```python
# Move to trash
mail.trash_message(message_id)

# Restore from trash
mail.untrash_message(message_id)

# Permanent delete
mail.delete_message(message_id)
```

## Patterns

### User ID
```python
# Default: "me" (authenticated user)
mail.send(sender="me@example.com", to="user@example.com", ...)

# Explicit user (with domain-wide delegation)
mail.send(..., user_id="specific@domain.com")
```

### Multiple Recipients
```python
# String
mail.send(to="user@example.com", ...)

# List
mail.send(to=["user1@example.com", "user2@example.com"], ...)
```

### Message Encoding
```python
# Plain text: MIMEText("body", "plain")
# HTML: MIMEText("body", "html")
# Base64url encoding for transport
```

### Generator Pattern
```python
# Lazy iteration with automatic pagination
for msg in mail.list_messages():
    # Process incrementally
    pass
```

## Dependencies

**External:**
- `google-api-python-client` - GmailResource
- `email.mime.multipart.MIMEMultipart` - Message construction
- `email.mime.text.MIMEText` - Message body
- `base64` - Message encoding

**Internal:**
- `googleapiutils2.utils.DriveBase` - Base class
- `googleapiutils2.utils.ServiceAccountCredentials` - Auth
- `googleapiutils2.utils.EXECUTE_TIME` - Throttling
- `googleapiutils2.utils.THROTTLE_TIME` - Rate limiting

## Public API

**Exported from `__init__.py`:**
- `Mail`

## Notes

### Authentication
- OAuth2 client: User authorization required
- Service account: Domain-wide delegation + `creds.with_subject("user@domain.com")`

### Limitations
- No attachment support (MIME only handles text/html)
- No threading management
- No push notifications
- No history API

### Message Format
```python
# MIMEMultipart structure
message = MIMEMultipart()
message['From'] = sender
message['To'] = ', '.join(to) if isinstance(to, list) else to
message['Subject'] = subject
message.attach(MIMEText(body, 'html' if html else 'plain'))

# Base64url encoding
raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
```

### Query Syntax
Gmail search operators: `from:`, `to:`, `subject:`, `is:`, `has:`, `after:`, `before:`, etc.

```python
mail.list_messages(query="from:user@example.com has:attachment after:2024/01/01")
```
