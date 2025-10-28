# Groups Module Refactoring Specification

**Module:** `googleapiutils2/groups/`
**Current Size:** 222 LOC
**Target Size:** ~180 LOC (distributed across 2 operation files)
**Complexity:** ★★ (Low-Medium)

---

## Current Structure (BEFORE)

```
groups/
├── __init__.py                    # Exports: Groups
├── groups.py                      # 222 LOC - Groups class (monolithic)
└── misc.py                        # 12 LOC - Constants (unchanged)
```

**Problems:**
- Mixed concerns: group operations vs member operations

---

## Proposed Structure (AFTER)

```
groups/
├── __init__.py                    # Exports: Groups (unchanged)
├── groups.py                      # Groups class - coordinator (~80 LOC)
├── types.py                       # TYPE_CHECKING imports (~20 LOC)
├── operations/
│   ├── __init__.py
│   ├── groups.py                 # Group operations (~80 LOC)
│   └── members.py                # Member operations (~90 LOC)
└── misc.py                        # Constants (unchanged)
```

**Benefits:**
- Clear separation: groups vs members
- Groups class reduced 222 → 80 LOC (64% reduction)

---

## Operation Module Breakdown

### 1. `operations/groups.py` (~80 LOC)

**Responsibility:** Group management

**Functions:**
- `get_group()` - Get group metadata
- `list_groups()` - List groups
- `create_group()` - Create new group
- `update_group()` - Update group properties
- `delete_group()` - Delete group

---

### 2. `operations/members.py` (~90 LOC)

**Responsibility:** Group membership

**Functions:**
- `list_members()` - List group members
- `get_member()` - Get member metadata
- `insert_member()` - Add member to group
- `update_member()` - Update member properties
- `delete_member()` - Remove member from group
- `has_member()` - Check membership

---

## Code Examples: BEFORE → AFTER

### BEFORE (Monolithic)

```python
# groups/groups.py (222 LOC total)

class Groups(DriveBase):
    def __init__(self, creds, execute_time, throttle_time):
        super().__init__(creds, execute_time, throttle_time)
        self.service = discovery.build("admin", "directory_v1", credentials=self.creds)

    @cachedmethod(...)
    def get(self, group_key):
        """Get group metadata."""
        # ... 15 lines

    def list(self, customer=None, domain=None, max_results=200):
        """List groups."""
        # ... 30 lines

    def create(self, email, name, description=""):
        """Create new group."""
        # ... 20 lines

    def update(self, group_key, body):
        """Update group properties."""
        # ... 15 lines

    def delete(self, group_key):
        """Delete group."""
        # ... 10 lines

    def members_list(self, group_key, max_results=200):
        """List group members."""
        # ... 25 lines

    @cachedmethod(...)
    def members_get(self, group_key, member_key):
        """Get member metadata."""
        # ... 15 lines

    def members_insert(self, group_key, email, role="MEMBER"):
        """Add member to group."""
        # ... 20 lines

    def members_update(self, group_key, member_key, body):
        """Update member properties."""
        # ... 15 lines

    def members_delete(self, group_key, member_key):
        """Remove member from group."""
        # ... 10 lines

    def has_member(self, group_key, member_key):
        """Check membership."""
        # ... 15 lines
```

### AFTER (Modular)

**Main Class:**

```python
# groups/groups.py (~80 LOC total)

from googleapiutils2.utils import DriveBase
from cachetools import cachedmethod
import operator
from .operations import groups as groups_ops, members as members_ops

class Groups(DriveBase):
    """Wrapper around Google Admin SDK Groups API.

    Requires service account with domain-wide delegation and
    https://www.googleapis.com/auth/admin.directory.group scope.

    Args:
        creds: Service Account credentials
        execute_time: Throttle between requests
        throttle_time: Rate limit delay
    """

    def __init__(
        self,
        creds=None,
        execute_time=0.1,
        throttle_time=30,
    ):
        super().__init__(creds, execute_time, throttle_time)
        self.service = discovery.build("admin", "directory_v1", credentials=self.creds)

    # GROUP OPERATIONS

    @cachedmethod(operator.attrgetter("_cache"))
    def get(self, group_key: str):
        """Get group (cached, delegates to operation)."""
        return groups_ops.get_group(service=self.service, group_key=group_key)

    def list(self, customer: str | None = None, domain: str | None = None, max_results: int = 200):
        """List groups (delegates to operation)."""
        return groups_ops.list_groups(
            service=self.service,
            customer=customer,
            domain=domain,
            max_results=max_results,
        )

    def create(self, email: str, name: str, description: str = ""):
        """Create group (delegates to operation)."""
        return groups_ops.create_group(
            service=self.service,
            email=email,
            name=name,
            description=description,
        )

    def update(self, group_key: str, body: dict):
        """Update group (delegates to operation)."""
        return groups_ops.update_group(service=self.service, group_key=group_key, body=body)

    def delete(self, group_key: str):
        """Delete group (delegates to operation)."""
        return groups_ops.delete_group(service=self.service, group_key=group_key)

    # MEMBER OPERATIONS

    def members_list(self, group_key: str, max_results: int = 200):
        """List members (delegates to operation)."""
        return members_ops.list_members(
            service=self.service,
            group_key=group_key,
            max_results=max_results,
        )

    @cachedmethod(operator.attrgetter("_cache"))
    def members_get(self, group_key: str, member_key: str):
        """Get member (cached, delegates to operation)."""
        return members_ops.get_member(
            service=self.service,
            group_key=group_key,
            member_key=member_key,
        )

    def members_insert(self, group_key: str, email: str, role: str = "MEMBER"):
        """Insert member (delegates to operation)."""
        return members_ops.insert_member(
            service=self.service,
            group_key=group_key,
            email=email,
            role=role,
        )

    def members_update(self, group_key: str, member_key: str, body: dict):
        """Update member (delegates to operation)."""
        return members_ops.update_member(
            service=self.service,
            group_key=group_key,
            member_key=member_key,
            body=body,
        )

    def members_delete(self, group_key: str, member_key: str):
        """Delete member (delegates to operation)."""
        return members_ops.delete_member(
            service=self.service,
            group_key=group_key,
            member_key=member_key,
        )

    def has_member(self, group_key: str, member_key: str):
        """Check membership (delegates to operation)."""
        return members_ops.has_member(
            service=self.service,
            group_key=group_key,
            member_key=member_key,
        )
```

**Groups Operations:**

```python
# groups/operations/groups.py (~80 LOC total)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from googleapiclient._apis.admin.directory_v1.resources import DirectoryResource

def get_group(service: "DirectoryResource", group_key: str) -> dict:
    """Pure function: Get group metadata."""
    return service.groups().get(groupKey=group_key).execute()


def list_groups(
    service: "DirectoryResource",
    customer: str | None = None,
    domain: str | None = None,
    max_results: int = 200,
) -> list[dict]:
    """Pure function: List groups."""
    kwargs = {"maxResults": max_results}
    if customer:
        kwargs["customer"] = customer
    if domain:
        kwargs["domain"] = domain

    page_token = None
    while True:
        if page_token:
            kwargs["pageToken"] = page_token

        result = service.groups().list(**kwargs).execute()
        yield from result.get("groups", [])

        page_token = result.get("nextPageToken")
        if not page_token:
            break


def create_group(
    service: "DirectoryResource",
    email: str,
    name: str,
    description: str = "",
) -> dict:
    """Pure function: Create new group."""
    body = {
        "email": email,
        "name": name,
        "description": description,
    }
    return service.groups().insert(body=body).execute()


def update_group(service: "DirectoryResource", group_key: str, body: dict) -> dict:
    """Pure function: Update group properties."""
    return service.groups().update(groupKey=group_key, body=body).execute()


def delete_group(service: "DirectoryResource", group_key: str) -> None:
    """Pure function: Delete group."""
    service.groups().delete(groupKey=group_key).execute()
```

**Members Operations:**

```python
# groups/operations/members.py (~90 LOC total)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from googleapiclient._apis.admin.directory_v1.resources import DirectoryResource

def list_members(
    service: "DirectoryResource",
    group_key: str,
    max_results: int = 200,
    include_derived: bool = False,
) -> list[dict]:
    """Pure function: List group members."""
    kwargs = {
        "groupKey": group_key,
        "maxResults": max_results,
        "includeDerivedMembership": include_derived,
    }

    page_token = None
    while True:
        if page_token:
            kwargs["pageToken"] = page_token

        result = service.members().list(**kwargs).execute()
        yield from result.get("members", [])

        page_token = result.get("nextPageToken")
        if not page_token:
            break


def get_member(
    service: "DirectoryResource",
    group_key: str,
    member_key: str,
) -> dict:
    """Pure function: Get member metadata."""
    return service.members().get(
        groupKey=group_key,
        memberKey=member_key,
    ).execute()


def insert_member(
    service: "DirectoryResource",
    group_key: str,
    email: str,
    role: str = "MEMBER",
) -> dict:
    """Pure function: Add member to group.

    Args:
        service: Admin SDK service
        group_key: Group email or ID
        email: Member email
        role: Member role (OWNER, MANAGER, MEMBER)
    """
    body = {
        "email": email,
        "role": role,
    }
    return service.members().insert(
        groupKey=group_key,
        body=body,
    ).execute()


def update_member(
    service: "DirectoryResource",
    group_key: str,
    member_key: str,
    body: dict,
) -> dict:
    """Pure function: Update member properties."""
    return service.members().update(
        groupKey=group_key,
        memberKey=member_key,
        body=body,
    ).execute()


def delete_member(
    service: "DirectoryResource",
    group_key: str,
    member_key: str,
) -> None:
    """Pure function: Remove member from group."""
    service.members().delete(
        groupKey=group_key,
        memberKey=member_key,
    ).execute()


def has_member(
    service: "DirectoryResource",
    group_key: str,
    member_key: str,
) -> bool:
    """Pure function: Check if user is member of group."""
    try:
        service.members().hasMember(
            groupKey=group_key,
            memberKey=member_key,
        ).execute()
        return True
    except Exception:
        return False
```

---

## Migration Strategy

1. Create `groups/operations/` directory
2. Create `groups/types.py`
3. Extract functions to `groups.py` and `members.py`
4. Update Groups class to delegate
5. Preserve caching decorators
6. Run tests

---

## File Size Comparison

| File | Before (LOC) | After (LOC) | Reduction |
|------|--------------|-------------|-----------|
| `groups.py` | 222 | ~80 | -64% |
| `operations/groups.py` | - | ~80 | NEW |
| `operations/members.py` | - | ~90 | NEW |
| **Total** | **222** | **~250** | +13% |

---

## Benefits

- **Clarity:** Groups vs members clearly separated
- **Testability:** Pure operations testable
- **Caching:** Preserved on main class methods
- **AI-Friendly:** Max file ~90 LOC (was 222)
