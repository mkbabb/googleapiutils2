# Admin Module Refactoring Specification

**Module:** `googleapiutils2/admin/`
**Current Size:** 380 LOC
**Target Size:** ~280 LOC (distributed across 1 operation file)
**Complexity:** ★★★ (Medium)

---

## Current Structure (BEFORE)

```
admin/
├── __init__.py                    # Exports: Admin
├── admin.py                       # 380 LOC - Admin class (monolithic)
└── misc.py                        # Constants (unchanged)
```

**Problems:**
- All user operations in single class
- Medium complexity but could benefit from extraction

---

## Proposed Structure (AFTER)

```
admin/
├── __init__.py                    # Exports: Admin (unchanged)
├── admin.py                       # Admin class - coordinator (~100 LOC)
├── types.py                       # TYPE_CHECKING imports (~20 LOC)
├── operations/
│   ├── __init__.py
│   └── users.py                  # All user operations (~280 LOC)
└── misc.py                        # Constants (unchanged)
```

**Benefits:**
- Admin class reduced 380 → 100 LOC (74% reduction)
- All user operations consolidated in one module
- Pure functions testable without Workspace account

---

## Operation Module Breakdown

### 1. `operations/users.py` (~280 LOC)

**Responsibility:** Google Workspace user management

**Functions:**
- `get_user()` - Get user by email/ID
- `list_users()` - List users with query
- `find_users_by_name()` - Search by given/family name
- `create_user()` - Create new user
- `delete_user()` - Delete user
- `undelete_user()` - Restore deleted user
- `update_user()` - Update user fields
- `suspend_user()` - Suspend account
- `unsuspend_user()` - Restore suspended account
- `update_password()` - Change password
- `make_admin()` - Grant super admin
- `revoke_admin()` - Revoke admin
- `update_name()` - Update given/family name

---

## Code Examples: BEFORE → AFTER

### BEFORE (Monolithic)

```python
# admin/admin.py (380 LOC total)

class Admin(DriveBase):
    def __init__(self, creds, execute_time, throttle_time, customer_id="my_customer"):
        super().__init__(creds, execute_time, throttle_time)
        self.service = discovery.build("admin", "directory_v1", credentials=self.creds)
        self.customer_id = customer_id

    def get_user(self, user_key, projection="full", view_type="admin_view"):
        """Get user by email or ID."""
        # ... 15 lines

    def list_users(self, customer=None, query=None, max_results=500, ...):
        """List users with query."""
        # ... 40 lines

    def find_users_by_name(self, given_name=None, family_name=None):
        """Find users by name."""
        # ... 20 lines

    def create_user(self, email, given_name, family_name, password, ...):
        """Create new Workspace user."""
        # ... 30 lines

    def delete_user(self, user_key):
        """Delete user account."""
        # ... 10 lines

    def undelete_user(self, user_key):
        """Restore deleted user."""
        # ... 15 lines

    def update_user(self, user_key, body):
        """Update user fields."""
        # ... 15 lines

    def suspend_user(self, user_key):
        """Suspend account."""
        # ... 15 lines

    def unsuspend_user(self, user_key):
        """Restore suspended account."""
        # ... 15 lines

    def update_password(self, user_key, password):
        """Change password."""
        # ... 15 lines

    def make_admin(self, user_key):
        """Grant super admin."""
        # ... 20 lines

    def revoke_admin(self, user_key):
        """Revoke admin status."""
        # ... 15 lines

    def update_name(self, user_key, given_name, family_name):
        """Update name."""
        # ... 20 lines
```

### AFTER (Modular)

**Main Class:**

```python
# admin/admin.py (~100 LOC total)

from googleapiutils2.utils import DriveBase
from google.oauth2.credentials import Credentials
from googleapiclient import discovery
from .operations import users as users_ops

class Admin(DriveBase):
    """Wrapper around Google Admin SDK for Workspace user management.

    Requires service account with domain-wide delegation and
    https://www.googleapis.com/auth/admin.directory.user scope.

    Args:
        creds: Service Account credentials with domain delegation
        execute_time: Throttle between requests (default: 0.1)
        throttle_time: Rate limit delay (default: 30)
        customer_id: Domain identifier (default: "my_customer")
    """

    def __init__(
        self,
        creds: Credentials | None = None,
        execute_time: float = 0.1,
        throttle_time: float = 30,
        customer_id: str = "my_customer",
    ):
        super().__init__(creds, execute_time, throttle_time)
        self.service = discovery.build("admin", "directory_v1", credentials=self.creds)
        self.customer_id = customer_id

    # USER RETRIEVAL

    def get_user(
        self,
        user_key: str,
        projection: str = "full",
        view_type: str = "admin_view",
    ):
        """Get user (delegates to operation)."""
        return users_ops.get_user(
            service=self.service,
            user_key=user_key,
            projection=projection,
            view_type=view_type,
        )

    def list_users(
        self,
        customer: str | None = None,
        query: str | None = None,
        max_results: int = 500,
        projection: str = "full",
        **kwargs,
    ):
        """List users (delegates to operation)."""
        return users_ops.list_users(
            service=self.service,
            customer=customer or self.customer_id,
            query=query,
            max_results=max_results,
            projection=projection,
            **kwargs,
        )

    def find_users_by_name(
        self,
        given_name: str | None = None,
        family_name: str | None = None,
    ):
        """Find users by name (delegates to operation)."""
        return users_ops.find_users_by_name(
            service=self.service,
            customer=self.customer_id,
            given_name=given_name,
            family_name=family_name,
        )

    # USER LIFECYCLE

    def create_user(
        self,
        email: str,
        given_name: str,
        family_name: str,
        password: str,
        **kwargs,
    ):
        """Create user (delegates to operation)."""
        return users_ops.create_user(
            service=self.service,
            email=email,
            given_name=given_name,
            family_name=family_name,
            password=password,
            **kwargs,
        )

    def delete_user(self, user_key: str):
        """Delete user (delegates to operation)."""
        return users_ops.delete_user(service=self.service, user_key=user_key)

    def undelete_user(self, user_key: str):
        """Undelete user (delegates to operation)."""
        return users_ops.undelete_user(service=self.service, user_key=user_key)

    # USER STATUS

    def suspend_user(self, user_key: str):
        """Suspend user (delegates to operation)."""
        return users_ops.suspend_user(service=self.service, user_key=user_key)

    def unsuspend_user(self, user_key: str):
        """Unsuspend user (delegates to operation)."""
        return users_ops.unsuspend_user(service=self.service, user_key=user_key)

    def update_password(self, user_key: str, password: str):
        """Update password (delegates to operation)."""
        return users_ops.update_password(service=self.service, user_key=user_key, password=password)

    # USER PERMISSIONS

    def make_admin(self, user_key: str):
        """Make admin (delegates to operation)."""
        return users_ops.make_admin(service=self.service, user_key=user_key)

    def revoke_admin(self, user_key: str):
        """Revoke admin (delegates to operation)."""
        return users_ops.revoke_admin(service=self.service, user_key=user_key)

    # USER METADATA

    def update_user(self, user_key: str, body: dict):
        """Update user (delegates to operation)."""
        return users_ops.update_user(service=self.service, user_key=user_key, body=body)

    def update_name(self, user_key: str, given_name: str, family_name: str):
        """Update name (delegates to operation)."""
        return users_ops.update_name(
            service=self.service,
            user_key=user_key,
            given_name=given_name,
            family_name=family_name,
        )
```

**Users Operations:**

```python
# admin/operations/users.py (~280 LOC total)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from googleapiclient._apis.admin.directory_v1.resources import DirectoryResource

def get_user(
    service: "DirectoryResource",
    user_key: str,
    projection: str = "full",
    view_type: str = "admin_view",
) -> dict:
    """Pure function: Get user by email or ID.

    Args:
        service: Admin SDK service
        user_key: User email or ID
        projection: Detail level (basic, full, custom)
        view_type: Access level (admin_view, domain_public)

    Returns:
        User dict
    """
    return service.users().get(
        userKey=user_key,
        projection=projection,
        viewType=view_type,
    ).execute()


def list_users(
    service: "DirectoryResource",
    customer: str,
    query: str | None = None,
    max_results: int = 500,
    projection: str = "full",
    order_by: str | None = None,
    view_type: str = "admin_view",
) -> list[dict]:
    """Pure function: List users with query filtering.

    Args:
        service: Admin SDK service
        customer: Domain identifier
        query: LDAP query (e.g., "givenName:John familyName:Doe")
        max_results: Max users per page
        projection: Detail level
        order_by: Sort field
        view_type: Access level

    Yields:
        User dicts
    """
    kwargs = {
        "customer": customer,
        "maxResults": max_results,
        "projection": projection,
        "viewType": view_type,
    }
    if query:
        kwargs["query"] = query
    if order_by:
        kwargs["orderBy"] = order_by

    page_token = None
    while True:
        if page_token:
            kwargs["pageToken"] = page_token

        result = service.users().list(**kwargs).execute()
        yield from result.get("users", [])

        page_token = result.get("nextPageToken")
        if not page_token:
            break


def find_users_by_name(
    service: "DirectoryResource",
    customer: str,
    given_name: str | None = None,
    family_name: str | None = None,
) -> list[dict]:
    """Pure function: Find users by given/family name.

    Args:
        service: Admin SDK service
        customer: Domain identifier
        given_name: Given name
        family_name: Family name

    Returns:
        List of user dicts
    """
    queries = []
    if given_name:
        queries.append(f"givenName:{given_name}")
    if family_name:
        queries.append(f"familyName:{family_name}")

    query = " ".join(queries) if queries else None
    return list(list_users(service, customer, query=query))


def create_user(
    service: "DirectoryResource",
    email: str,
    given_name: str,
    family_name: str,
    password: str,
    org_unit_path: str = "/",
    change_password_at_next_login: bool = False,
    **kwargs,
) -> dict:
    """Pure function: Create new Workspace user.

    Args:
        service: Admin SDK service
        email: User email address
        given_name: Given name
        family_name: Family name
        password: Initial password
        org_unit_path: Organizational unit
        change_password_at_next_login: Force password change

    Returns:
        Created user dict
    """
    body = {
        "primaryEmail": email,
        "name": {
            "givenName": given_name,
            "familyName": family_name,
        },
        "password": password,
        "orgUnitPath": org_unit_path,
        "changePasswordAtNextLogin": change_password_at_next_login,
        **kwargs,
    }

    return service.users().insert(body=body).execute()


def delete_user(service: "DirectoryResource", user_key: str) -> None:
    """Pure function: Delete user account.

    Args:
        service: Admin SDK service
        user_key: User email or ID
    """
    service.users().delete(userKey=user_key).execute()


def undelete_user(service: "DirectoryResource", user_key: str) -> dict:
    """Pure function: Restore deleted user.

    Args:
        service: Admin SDK service
        user_key: User email or ID

    Returns:
        Restored user dict
    """
    return service.users().undelete(userKey=user_key).execute()


def update_user(
    service: "DirectoryResource",
    user_key: str,
    body: dict,
) -> dict:
    """Pure function: Update user fields.

    Args:
        service: Admin SDK service
        user_key: User email or ID
        body: User fields to update

    Returns:
        Updated user dict
    """
    return service.users().update(userKey=user_key, body=body).execute()


def suspend_user(service: "DirectoryResource", user_key: str) -> dict:
    """Pure function: Suspend user account.

    Args:
        service: Admin SDK service
        user_key: User email or ID

    Returns:
        Updated user dict
    """
    return update_user(service, user_key, {"suspended": True})


def unsuspend_user(service: "DirectoryResource", user_key: str) -> dict:
    """Pure function: Restore suspended account.

    Args:
        service: Admin SDK service
        user_key: User email or ID

    Returns:
        Updated user dict
    """
    return update_user(service, user_key, {"suspended": False})


def update_password(
    service: "DirectoryResource",
    user_key: str,
    password: str,
    change_password_at_next_login: bool = False,
) -> dict:
    """Pure function: Change user password.

    Args:
        service: Admin SDK service
        user_key: User email or ID
        password: New password
        change_password_at_next_login: Force password change

    Returns:
        Updated user dict
    """
    body = {
        "password": password,
        "changePasswordAtNextLogin": change_password_at_next_login,
    }
    return update_user(service, user_key, body)


def make_admin(service: "DirectoryResource", user_key: str) -> dict:
    """Pure function: Grant super admin privileges.

    Args:
        service: Admin SDK service
        user_key: User email or ID

    Returns:
        Updated user dict
    """
    return update_user(service, user_key, {"isAdmin": True})


def revoke_admin(service: "DirectoryResource", user_key: str) -> dict:
    """Pure function: Revoke admin status.

    Args:
        service: Admin SDK service
        user_key: User email or ID

    Returns:
        Updated user dict
    """
    return update_user(service, user_key, {"isAdmin": False})


def update_name(
    service: "DirectoryResource",
    user_key: str,
    given_name: str,
    family_name: str,
) -> dict:
    """Pure function: Update user's given/family name.

    Args:
        service: Admin SDK service
        user_key: User email or ID
        given_name: New given name
        family_name: New family name

    Returns:
        Updated user dict
    """
    body = {
        "name": {
            "givenName": given_name,
            "familyName": family_name,
        }
    }
    return update_user(service, user_key, body)
```

---

## Migration Strategy

1. Create `admin/operations/` directory
2. Create `admin/types.py`
3. Extract functions to `users.py`
4. Update Admin class to delegate
5. Run tests

---

## File Size Comparison

| File | Before (LOC) | After (LOC) | Reduction |
|------|--------------|-------------|-----------|
| `admin.py` | 380 | ~100 | -74% |
| `operations/users.py` | - | ~280 | NEW |
| **Total** | **380** | **~380** | stable |

---

## Benefits

- **Clarity:** Admin class now just coordinates
- **Testability:** Pure user operations
- **AI-Friendly:** Max file ~280 LOC (was 380)
