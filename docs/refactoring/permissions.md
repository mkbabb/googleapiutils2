# Permissions Module Refactoring Specification

**Module:** `googleapiutils2/drive/permissions/`
**Current Size:** 158 LOC (inside drive.py)
**Target Size:** ~160 LOC (distributed across 2 files)
**Complexity:** ★★ (Medium)

---

## Current Structure (BEFORE)

```
drive/
├── drive.py                       # Lines 1066-1223: Permissions class (158 LOC)
```

**Problems:**
- Embedded in drive.py (unrelated to Drive class)
- No logical separation from file operations

---

## Proposed Structure (AFTER)

```
drive/permissions/
├── __init__.py                    # Export Permissions class
├── permissions.py                 # Permissions class - coordinator (~80 LOC)
└── operations.py                  # Permission CRUD operations (~80 LOC)
```

**Benefits:**
- Clean extraction from Drive module
- Logical grouping of permission operations
- Can be imported separately: `from googleapiutils2.drive.permissions import Permissions`

---

## Code Examples: BEFORE → AFTER

### BEFORE (Embedded in Drive)

```python
# drive/drive.py (lines 1066-1223)

class Permissions:
    """Helper class for managing Drive file permissions."""

    def __init__(self, drive: Drive):
        self.drive = drive
        self.service = drive.service
        self.files = drive.files

    def get(self, file_id, permission_id, **kwargs):
        """Get a specific permission."""
        # ... 10 lines

    def list(self, file_id, fields="*", **kwargs):
        """List all permissions for a file."""
        # ... 15 lines

    def create(self, file_id, email_address, permission=None, ...):
        """Create permission(s) for user(s)."""
        # ... 60+ lines
        # - Batch creation support
        # - Existence checking
        # - Update if exists logic

    def update(self, file_id, permission_id, permission, **kwargs):
        """Update an existing permission."""
        # ... 20 lines

    def delete(self, file_id, permission_id, **kwargs):
        """Delete a permission."""
        # ... 10 lines

    def _permission_get_if_exists(self, file_id, email_address):
        """Check if permission exists for email."""
        # ... 15 lines

    @staticmethod
    def _sanitize_update_permission(permission):
        """Filter to only allowed update fields."""
        # ... 10 lines
```

### AFTER (Extracted Module)

**Permissions Class:**

```python
# drive/permissions/permissions.py (~80 LOC)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from googleapiutils2.drive import Drive
    from googleapiclient._apis.drive.v3.resources import Permission

from . import operations as ops


class Permissions:
    """Helper class for managing Google Drive file permissions.

    Provides CRUD operations for file sharing and access control.

    Args:
        drive: Drive instance to use for API calls
    """

    def __init__(self, drive: "Drive"):
        self.drive = drive
        self.service = drive.service
        self.files = drive.files

    def get(
        self,
        file_id: str,
        permission_id: str,
        **kwargs,
    ) -> "Permission":
        """Get a specific permission by ID."""
        return ops.get_permission(
            service=self.service,
            file_id=file_id,
            permission_id=permission_id,
            **kwargs,
        )

    def list(
        self,
        file_id: str,
        fields: str = "*",
        **kwargs,
    ) -> list["Permission"]:
        """List all permissions for a file."""
        return ops.list_permissions(
            service=self.service,
            file_id=file_id,
            fields=fields,
            **kwargs,
        )

    def create(
        self,
        file_id: str,
        email_address: str | list[str],
        permission: "Permission | None" = None,
        send_notification_email: bool = True,
        get_extant: bool = False,
        update: bool = False,
        **kwargs,
    ) -> "Permission" | list["Permission"]:
        """Create permission(s) for user(s).

        Args:
            file_id: Target file ID
            email_address: User email(s) - string or list
            permission: Custom permission dict (defaults to reader)
            send_notification_email: Email user about access
            get_extant: Return existing if already has permission
            update: Update existing permission instead of error

        Returns:
            Permission dict or list of dicts if multiple emails
        """
        return ops.create_permissions(
            service=self.service,
            file_id=file_id,
            email_address=email_address,
            permission=permission,
            send_notification_email=send_notification_email,
            get_extant=get_extant,
            update=update,
            get_if_exists_fn=lambda e: self._permission_get_if_exists(file_id, e),
            update_fn=lambda pid, perm: self.update(file_id, pid, perm),
            **kwargs,
        )

    def update(
        self,
        file_id: str,
        permission_id: str,
        permission: "Permission",
        **kwargs,
    ) -> "Permission":
        """Update an existing permission."""
        return ops.update_permission(
            service=self.service,
            file_id=file_id,
            permission_id=permission_id,
            permission=permission,
            **kwargs,
        )

    def delete(
        self,
        file_id: str,
        permission_id: str,
        **kwargs,
    ) -> None:
        """Delete a permission."""
        ops.delete_permission(
            service=self.service,
            file_id=file_id,
            permission_id=permission_id,
            **kwargs,
        )

    def _permission_get_if_exists(
        self,
        file_id: str,
        email_address: str,
    ) -> "Permission | None":
        """Internal: Check if permission exists for email."""
        return ops.get_permission_if_exists(
            service=self.service,
            file_id=file_id,
            email_address=email_address,
        )
```

**Pure Functions:**

```python
# drive/permissions/operations.py (~80 LOC)

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import DriveResource, Permission

def get_permission(
    service: "DriveResource",
    file_id: str,
    permission_id: str,
    **kwargs,
) -> dict:
    """Pure function: Get a specific permission.

    Args:
        service: Drive API service
        file_id: File ID
        permission_id: Permission ID

    Returns:
        Permission dict
    """
    from googleapiutils2.utils import parse_file_id

    file_id = parse_file_id(file_id)
    return service.permissions().get(
        fileId=file_id,
        permissionId=permission_id,
        fields="*",
        **kwargs,
    ).execute()


def list_permissions(
    service: "DriveResource",
    file_id: str,
    fields: str = "*",
    **kwargs,
) -> list[dict]:
    """Pure function: List all permissions for a file.

    Args:
        service: Drive API service
        file_id: File ID
        fields: Fields to return

    Returns:
        List of Permission dicts
    """
    from googleapiutils2.utils import parse_file_id

    file_id = parse_file_id(file_id)
    result = service.permissions().list(
        fileId=file_id,
        fields=f"permissions({fields})" if fields != "*" else "*",
        **kwargs,
    ).execute()
    return result.get("permissions", [])


def create_permissions(
    service: "DriveResource",
    file_id: str,
    email_address: str | list[str],
    permission: dict | None = None,
    send_notification_email: bool = True,
    get_extant: bool = False,
    update: bool = False,
    get_if_exists_fn: Callable[[str], dict | None] | None = None,
    update_fn: Callable[[str, dict], dict] | None = None,
    **kwargs,
) -> dict | list[dict]:
    """Pure function: Create permission(s) for user(s).

    Supports batch creation for multiple email addresses.

    Args:
        service: Drive API service
        file_id: Target file ID
        email_address: User email or list of emails
        permission: Custom permission dict (defaults to reader)
        send_notification_email: Email users about access
        get_extant: Return existing if found
        update: Update existing instead of error
        get_if_exists_fn: Callback to check existence
        update_fn: Callback to update permission

    Returns:
        Permission dict or list of dicts
    """
    from googleapiutils2.utils import parse_file_id

    file_id = parse_file_id(file_id)

    # Default permission: reader
    default_permission = {
        "type": "user",
        "role": "reader",
    }

    # Handle batch creation
    if isinstance(email_address, list):
        results = []
        for email in email_address:
            result = create_permissions(
                service=service,
                file_id=file_id,
                email_address=email,
                permission=permission,
                send_notification_email=send_notification_email,
                get_extant=get_extant,
                update=update,
                get_if_exists_fn=get_if_exists_fn,
                update_fn=update_fn,
                **kwargs,
            )
            results.append(result)
        return results

    # Single email creation
    perm_body = permission or default_permission.copy()
    perm_body["emailAddress"] = email_address

    # Check if permission exists
    if get_extant or update:
        existing = get_if_exists_fn(email_address) if get_if_exists_fn else None
        if existing:
            if get_extant:
                return existing
            if update and update_fn:
                sanitized = sanitize_update_permission(perm_body)
                return update_fn(existing["id"], sanitized)

    # Create new permission
    return service.permissions().create(
        fileId=file_id,
        body=perm_body,
        sendNotificationEmail=send_notification_email,
        fields="*",
        **kwargs,
    ).execute()


def update_permission(
    service: "DriveResource",
    file_id: str,
    permission_id: str,
    permission: dict,
    **kwargs,
) -> dict:
    """Pure function: Update an existing permission.

    Only specific fields can be updated: role, allowFileDiscovery, expirationTime.

    Args:
        service: Drive API service
        file_id: File ID
        permission_id: Permission ID
        permission: Permission dict with updates

    Returns:
        Updated Permission dict
    """
    from googleapiutils2.utils import parse_file_id

    file_id = parse_file_id(file_id)
    sanitized = sanitize_update_permission(permission)

    return service.permissions().update(
        fileId=file_id,
        permissionId=permission_id,
        body=sanitized,
        fields="*",
        **kwargs,
    ).execute()


def delete_permission(
    service: "DriveResource",
    file_id: str,
    permission_id: str,
    **kwargs,
) -> None:
    """Pure function: Delete a permission.

    Args:
        service: Drive API service
        file_id: File ID
        permission_id: Permission ID
    """
    from googleapiutils2.utils import parse_file_id

    file_id = parse_file_id(file_id)
    service.permissions().delete(
        fileId=file_id,
        permissionId=permission_id,
        **kwargs,
    ).execute()


def get_permission_if_exists(
    service: "DriveResource",
    file_id: str,
    email_address: str,
) -> dict | None:
    """Pure function: Check if permission exists for email.

    Args:
        service: Drive API service
        file_id: File ID
        email_address: User email

    Returns:
        Permission dict or None if not found
    """
    permissions = list_permissions(service, file_id)
    for perm in permissions:
        if perm.get("emailAddress") == email_address:
            return perm
    return None


def sanitize_update_permission(permission: dict) -> dict:
    """Pure function: Filter permission dict to only allowed update fields.

    Only these fields can be updated:
    - role
    - allowFileDiscovery
    - expirationTime

    Args:
        permission: Permission dict

    Returns:
        Sanitized permission dict
    """
    allowed_fields = {"role", "allowFileDiscovery", "expirationTime"}
    return {k: v for k, v in permission.items() if k in allowed_fields}
```

---

## Migration Strategy

1. Create `drive/permissions/` directory
2. Move Permissions class to `permissions/permissions.py`
3. Extract operations to `permissions/operations.py`
4. Update `drive/__init__.py` to export from new location
5. Run tests

---

## File Size Comparison

| File | Before (LOC) | After (LOC) |
|------|--------------|-------------|
| `drive/drive.py` (Permissions part) | 158 | 0 (moved) |
| `permissions/permissions.py` | - | ~80 |
| `permissions/operations.py` | - | ~80 |
| **Total** | **158** | **~160** |

---

## Benefits

- **Extraction:** Permissions no longer embedded in Drive
- **Modularity:** Can import separately
- **Clarity:** Clear permission-specific namespace
- **Testability:** Pure CRUD operations
