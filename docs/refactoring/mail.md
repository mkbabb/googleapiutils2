# Mail Module Refactoring Specification

**Module:** `googleapiutils2/mail/`
**Current Size:** 358 LOC
**Target Size:** ~260 LOC (distributed across 2 operation files)
**Complexity:** ★★★ (Medium)

---

## Current Structure (BEFORE)

```
mail/
├── __init__.py                    # Exports: Mail
├── mail.py                        # 358 LOC - Mail class (monolithic)
└── misc.py                        # Constants (unchanged)
```

**Problems:**
- Single file with mixed concerns (messages vs labels)
- Message operations and label operations interleaved

---

## Proposed Structure (AFTER)

```
mail/
├── __init__.py                    # Exports: Mail (unchanged)
├── mail.py                        # Mail class - coordinator (~120 LOC)
├── types.py                       # TYPE_CHECKING imports (~20 LOC)
├── operations/
│   ├── __init__.py
│   ├── messages.py               # Message operations (~150 LOC)
│   └── labels.py                 # Label operations (~90 LOC)
└── misc.py                        # Constants (unchanged)
```

**Benefits:**
- Clear separation: messages vs labels
- Mail class reduced 358 → 120 LOC (66% reduction)
- Easy to locate message/label functionality

---

## Operation Module Breakdown

### 1. `operations/messages.py` (~150 LOC)

**Responsibility:** Email message operations

**Functions:**
- `send_message()` - Send email
- `create_draft()` - Create draft
- `list_messages()` - List messages with query/label filtering
- `get_message()` - Get full message
- `modify_message()` - Add/remove labels
- `trash_message()` - Move to trash
- `untrash_message()` - Restore from trash
- `delete_message()` - Permanently delete
- `create_mime_message()` - Build MIME message

---

### 2. `operations/labels.py` (~90 LOC)

**Responsibility:** Label management

**Functions:**
- `list_labels()` - List all labels
- `get_label()` - Get label by ID
- `create_label()` - Create custom label
- `delete_label()` - Delete label
- `modify_label()` - Update label properties

---

## Code Examples: BEFORE → AFTER

### BEFORE (Monolithic)

```python
# mail/mail.py (358 LOC total)

class Mail(DriveBase):
    def __init__(self, creds, execute_time, throttle_time, user_id="me"):
        super().__init__(creds, execute_time, throttle_time)
        self.service = discovery.build("gmail", "v1", credentials=self.creds)
        self.user_id = user_id

    def send(self, to, subject, body, from_=None):
        """Send email message."""
        # ... 30 lines

    def create_draft(self, to, subject, body, from_=None):
        """Create email draft."""
        # ... 20 lines

    def list_messages(self, query=None, label_ids=None, max_results=None):
        """List messages with query/label filtering."""
        # ... 40 lines

    def get_message(self, msg_id, format="full"):
        """Get full message by ID."""
        # ... 15 lines

    def modify_message(self, msg_id, add_labels=None, remove_labels=None):
        """Add/remove labels from message."""
        # ... 20 lines

    def trash_message(self, msg_id):
        """Move message to trash."""
        # ... 10 lines

    def untrash_message(self, msg_id):
        """Restore message from trash."""
        # ... 10 lines

    def delete_message(self, msg_id):
        """Permanently delete message."""
        # ... 10 lines

    def _create_message(self, to, subject, body, from_=None):
        """Build MIME message."""
        # ... 40 lines

    def list_labels(self):
        """List all labels."""
        # ... 15 lines

    def get_label(self, label_id):
        """Get label by ID."""
        # ... 10 lines

    def create_label(self, name, **kwargs):
        """Create custom label."""
        # ... 20 lines

    def delete_label(self, label_id):
        """Delete label."""
        # ... 10 lines

    def modify_label(self, label_id, **kwargs):
        """Update label properties."""
        # ... 15 lines
```

### AFTER (Modular)

**Main Class:**

```python
# mail/mail.py (~120 LOC total)

from googleapiutils2.utils import DriveBase
from google.oauth2.credentials import Credentials
from googleapiclient import discovery
from .operations import messages as msg_ops, labels as label_ops

class Mail(DriveBase):
    """Wrapper around Gmail API for email operations.

    Args:
        creds: OAuth2 or Service Account credentials
        execute_time: Throttle between requests (default: 0.1)
        throttle_time: Rate limit delay (default: 30)
        user_id: Target user (default: "me" = authenticated user)
    """

    def __init__(
        self,
        creds: Credentials | None = None,
        execute_time: float = 0.1,
        throttle_time: float = 30,
        user_id: str = "me",
    ):
        super().__init__(creds, execute_time, throttle_time)
        self.service = discovery.build("gmail", "v1", credentials=self.creds)
        self.user_id = user_id

    # MESSAGE OPERATIONS

    def send(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        from_: str | None = None,
    ):
        """Send email message (delegates to operation)."""
        return msg_ops.send_message(
            service=self.service,
            user_id=self.user_id,
            to=to,
            subject=subject,
            body=body,
            from_=from_,
        )

    def create_draft(
        self,
        to: str | list[str],
        subject: str,
        body: str,
        from_: str | None = None,
    ):
        """Create email draft (delegates to operation)."""
        return msg_ops.create_draft(
            service=self.service,
            user_id=self.user_id,
            to=to,
            subject=subject,
            body=body,
            from_=from_,
        )

    def list_messages(
        self,
        query: str | None = None,
        label_ids: list[str] | None = None,
        max_results: int | None = None,
    ):
        """List messages (delegates to operation)."""
        return msg_ops.list_messages(
            service=self.service,
            user_id=self.user_id,
            query=query,
            label_ids=label_ids,
            max_results=max_results,
            get_message_fn=self.get_message,
        )

    def get_message(self, msg_id: str, format: str = "full"):
        """Get message (delegates to operation)."""
        return msg_ops.get_message(
            service=self.service,
            user_id=self.user_id,
            msg_id=msg_id,
            format=format,
        )

    def modify_message(
        self,
        msg_id: str,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ):
        """Modify message labels (delegates to operation)."""
        return msg_ops.modify_message(
            service=self.service,
            user_id=self.user_id,
            msg_id=msg_id,
            add_labels=add_labels,
            remove_labels=remove_labels,
        )

    def trash_message(self, msg_id: str):
        """Trash message (delegates to operation)."""
        return msg_ops.trash_message(service=self.service, user_id=self.user_id, msg_id=msg_id)

    def untrash_message(self, msg_id: str):
        """Untrash message (delegates to operation)."""
        return msg_ops.untrash_message(service=self.service, user_id=self.user_id, msg_id=msg_id)

    def delete_message(self, msg_id: str):
        """Delete message (delegates to operation)."""
        return msg_ops.delete_message(service=self.service, user_id=self.user_id, msg_id=msg_id)

    # LABEL OPERATIONS

    def list_labels(self):
        """List labels (delegates to operation)."""
        return label_ops.list_labels(service=self.service, user_id=self.user_id)

    def get_label(self, label_id: str):
        """Get label (delegates to operation)."""
        return label_ops.get_label(service=self.service, user_id=self.user_id, label_id=label_id)

    def create_label(self, name: str, **kwargs):
        """Create label (delegates to operation)."""
        return label_ops.create_label(
            service=self.service, user_id=self.user_id, name=name, **kwargs
        )

    def delete_label(self, label_id: str):
        """Delete label (delegates to operation)."""
        return label_ops.delete_label(service=self.service, user_id=self.user_id, label_id=label_id)

    def modify_label(self, label_id: str, **kwargs):
        """Modify label (delegates to operation)."""
        return label_ops.modify_label(
            service=self.service, user_id=self.user_id, label_id=label_id, **kwargs
        )
```

**Messages Operations:**

```python
# mail/operations/messages.py (~150 LOC total)

from typing import TYPE_CHECKING, Callable
import base64
from email.mime.text import MIMEText

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1.resources import GmailResource

def send_message(
    service: "GmailResource",
    user_id: str,
    to: str | list[str],
    subject: str,
    body: str,
    from_: str | None = None,
) -> dict:
    """Pure function: Send email message.

    Args:
        service: Gmail API service
        user_id: User ID (usually "me")
        to: Recipient email(s)
        subject: Email subject
        body: Email body (plain text or HTML)
        from_: Sender email (optional)

    Returns:
        Message dict with id and threadId
    """
    message = create_mime_message(to, subject, body, from_)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    return service.users().messages().send(
        userId=user_id,
        body={"raw": raw},
    ).execute()


def create_draft(
    service: "GmailResource",
    user_id: str,
    to: str | list[str],
    subject: str,
    body: str,
    from_: str | None = None,
) -> dict:
    """Pure function: Create email draft."""
    message = create_mime_message(to, subject, body, from_)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    return service.users().drafts().create(
        userId=user_id,
        body={"message": {"raw": raw}},
    ).execute()


def list_messages(
    service: "GmailResource",
    user_id: str,
    query: str | None = None,
    label_ids: list[str] | None = None,
    max_results: int | None = None,
    get_message_fn: Callable[[str], dict] | None = None,
) -> list[dict]:
    """Pure function: List messages with query/label filtering.

    Args:
        service: Gmail API service
        user_id: User ID
        query: Gmail search query (e.g., "from:user@example.com after:2024-01-01")
        label_ids: Filter by label IDs
        max_results: Max messages to return
        get_message_fn: Callback to fetch full message

    Yields:
        Message dicts (full messages if get_message_fn provided)
    """
    kwargs = {}
    if query:
        kwargs["q"] = query
    if label_ids:
        kwargs["labelIds"] = label_ids
    if max_results:
        kwargs["maxResults"] = max_results

    results = service.users().messages().list(userId=user_id, **kwargs).execute()
    messages = results.get("messages", [])

    # Fetch full messages if callback provided
    if get_message_fn:
        for msg in messages:
            yield get_message_fn(msg["id"])
    else:
        yield from messages


def get_message(
    service: "GmailResource",
    user_id: str,
    msg_id: str,
    format: str = "full",
) -> dict:
    """Pure function: Get full message by ID.

    Args:
        service: Gmail API service
        user_id: User ID
        msg_id: Message ID
        format: Response format (full, metadata, minimal, raw)

    Returns:
        Message dict
    """
    return service.users().messages().get(
        userId=user_id,
        id=msg_id,
        format=format,
    ).execute()


def modify_message(
    service: "GmailResource",
    user_id: str,
    msg_id: str,
    add_labels: list[str] | None = None,
    remove_labels: list[str] | None = None,
) -> dict:
    """Pure function: Add/remove labels from message."""
    body = {}
    if add_labels:
        body["addLabelIds"] = add_labels
    if remove_labels:
        body["removeLabelIds"] = remove_labels

    return service.users().messages().modify(
        userId=user_id,
        id=msg_id,
        body=body,
    ).execute()


def trash_message(service: "GmailResource", user_id: str, msg_id: str) -> dict:
    """Pure function: Move message to trash."""
    return service.users().messages().trash(userId=user_id, id=msg_id).execute()


def untrash_message(service: "GmailResource", user_id: str, msg_id: str) -> dict:
    """Pure function: Restore message from trash."""
    return service.users().messages().untrash(userId=user_id, id=msg_id).execute()


def delete_message(service: "GmailResource", user_id: str, msg_id: str) -> None:
    """Pure function: Permanently delete message."""
    service.users().messages().delete(userId=user_id, id=msg_id).execute()


def create_mime_message(
    to: str | list[str],
    subject: str,
    body: str,
    from_: str | None = None,
) -> MIMEText:
    """Pure function: Build MIME message.

    Args:
        to: Recipient email(s)
        subject: Email subject
        body: Email body
        from_: Sender email

    Returns:
        MIMEText message
    """
    message = MIMEText(body)
    message["to"] = to if isinstance(to, str) else ", ".join(to)
    message["subject"] = subject
    if from_:
        message["from"] = from_

    return message
```

**Labels Operations:**

```python
# mail/operations/labels.py (~90 LOC total)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1.resources import GmailResource

def list_labels(service: "GmailResource", user_id: str) -> list[dict]:
    """Pure function: List all labels.

    Args:
        service: Gmail API service
        user_id: User ID

    Returns:
        List of label dicts
    """
    results = service.users().labels().list(userId=user_id).execute()
    return results.get("labels", [])


def get_label(service: "GmailResource", user_id: str, label_id: str) -> dict:
    """Pure function: Get label by ID.

    Args:
        service: Gmail API service
        user_id: User ID
        label_id: Label ID

    Returns:
        Label dict
    """
    return service.users().labels().get(userId=user_id, id=label_id).execute()


def create_label(
    service: "GmailResource",
    user_id: str,
    name: str,
    label_list_visibility: str = "labelShow",
    message_list_visibility: str = "show",
    **kwargs,
) -> dict:
    """Pure function: Create custom label.

    Args:
        service: Gmail API service
        user_id: User ID
        name: Label name
        label_list_visibility: Show in label list (labelShow, labelHide)
        message_list_visibility: Show in message list (show, hide)

    Returns:
        Created label dict
    """
    body = {
        "name": name,
        "labelListVisibility": label_list_visibility,
        "messageListVisibility": message_list_visibility,
        **kwargs,
    }

    return service.users().labels().create(userId=user_id, body=body).execute()


def delete_label(service: "GmailResource", user_id: str, label_id: str) -> None:
    """Pure function: Delete label.

    Args:
        service: Gmail API service
        user_id: User ID
        label_id: Label ID
    """
    service.users().labels().delete(userId=user_id, id=label_id).execute()


def modify_label(
    service: "GmailResource",
    user_id: str,
    label_id: str,
    **kwargs,
) -> dict:
    """Pure function: Update label properties.

    Args:
        service: Gmail API service
        user_id: User ID
        label_id: Label ID
        **kwargs: Label properties to update

    Returns:
        Updated label dict
    """
    return service.users().labels().patch(
        userId=user_id,
        id=label_id,
        body=kwargs,
    ).execute()
```

---

## Migration Strategy

1. Create `mail/operations/` directory
2. Create `mail/types.py`
3. Extract functions to `messages.py` and `labels.py`
4. Update Mail class to delegate
5. Run tests

---

## File Size Comparison

| File | Before (LOC) | After (LOC) | Reduction |
|------|--------------|-------------|-----------|
| `mail.py` | 358 | ~120 | -66% |
| `operations/messages.py` | - | ~150 | NEW |
| `operations/labels.py` | - | ~90 | NEW |
| **Total** | **358** | **~360** | stable |

---

## Benefits

- **Clarity:** Messages vs labels clearly separated
- **Navigation:** Easy to find email vs label ops
- **Testability:** Pure functions for send/draft/list
- **AI-Friendly:** Max file ~150 LOC (was 358)
