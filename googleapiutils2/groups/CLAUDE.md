# groups/

Google Groups API wrapper: group and member management.

## File Tree

```
groups/
├── __init__.py          # Exports Groups
├── groups.py            # Groups class (group/member operations)
└── misc.py              # Constants (VERSION, DEFAULT_FIELDS)
```

## Key Classes

### Groups (groups.py)
Inherits `DriveBase` for caching, throttling, retry.

**Group Methods:**
- `get(group_key)` - Get group metadata (cached)
- `list(customer, domain, user_key)` - List groups (generator)
- `create(email, name, description)` - Create group
- `update(group_key, body)` - Update group properties
- `delete(group_key)` - Delete group

**Member Methods:**
- `has_member(group_key, member_key)` - Check membership
- `members_get(group_key, member_key)` - Get member metadata (cached)
- `members_list(group_key)` - List group members (generator)
- `members_insert(group_key, member_key, member)` - Add member
- `members_update(group_key, member_key, body)` - Update member role/properties
- `members_delete(group_key, member_key)` - Remove member

## Constants

### API
- `VERSION = "directory_v1"` - Admin SDK API version
- `DEFAULT_FIELDS = "*"` - Return all fields

### Member Roles
- `OWNER` - Full control
- `MANAGER` - Can add/remove members
- `MEMBER` - Regular member

## Usage Examples

### Create & Manage Groups
```python
from googleapiutils2 import Groups, get_oauth2_creds

# Service account with domain-wide delegation
creds = get_oauth2_creds("auth/service-account.json")
creds = creds.with_subject("admin@domain.com")
groups = Groups(creds=creds)

# Create group
group = groups.create(
    email="team@domain.com",
    name="Engineering Team",
    description="All engineers"
)

# Get group
group = groups.get("team@domain.com")
print(group['name'], group['email'])

# Update group
groups.update("team@domain.com", {
    "description": "Updated description"
})

# Delete group
groups.delete("team@domain.com")
```

### List Groups
```python
# All groups
for group in groups.list(domain="example.com"):
    print(group['name'], group['email'])

# By customer
for group in groups.list(customer="C012345"):
    print(group)

# User's groups
for group in groups.list(user_key="user@domain.com"):
    print(group['email'])
```

### Member Management
```python
# Add member
groups.members_insert(
    group_key="team@domain.com",
    member_key="user@domain.com"
)

# Add with role
groups.members_insert(
    group_key="team@domain.com",
    member={"id": "manager@domain.com", "role": "MANAGER"}
)

# Check membership
is_member = groups.has_member("team@domain.com", "user@domain.com")

# Get member
member = groups.members_get("team@domain.com", "user@domain.com")
print(member['role'])

# List members
for member in groups.members_list("team@domain.com"):
    print(f"{member['email']}: {member['role']}")

# Update role
groups.members_update(
    "team@domain.com",
    "user@domain.com",
    {"role": "MANAGER"}
)

# Remove member
groups.members_delete("team@domain.com", "user@domain.com")
```

## Patterns

### Caching
```python
# get() and members_get() use TTL cache (80s)
group = groups.get("team@domain.com")  # API call
group = groups.get("team@domain.com")  # Cached

# Cache invalidated on mutations
groups.update("team@domain.com", {...})  # Clears cache
```

### Pagination
```python
# Generator pattern with automatic pagination
for group in groups.list(domain="example.com"):
    # Process incrementally
    pass
```

### Member Object
```python
# Minimal
groups.members_insert("group@domain.com", "user@domain.com")

# Full
member = {
    "id": "user@domain.com",
    "role": "MANAGER",
    "type": "USER"
}
groups.members_insert("group@domain.com", member=member)
```

## Dependencies

**External:**
- `google-api-python-client` - DirectoryResource
- `cachetools` - cachedmethod decorator
- `operator` - attrgetter for cache keys

**Internal:**
- `googleapiutils2.utils.DriveBase` - Base class
- `googleapiutils2.utils.ServiceAccountCredentials` - Auth
- `googleapiutils2.utils.EXECUTE_TIME` - Throttling
- `googleapiutils2.utils.THROTTLE_TIME` - Rate limiting
- `googleapiutils2.utils.named_methodkey` - Cache key generator
- `googleapiutils2.drive.misc.create_listing_fields` - Pagination helper
- `googleapiutils2.drive.misc.list_drive_items` - Pagination iterator

## Public API

**Exported from `__init__.py`:**
- `Groups`

## Notes

### Authentication
**Requires:** Service account with domain-wide delegation

**Setup:**
1. Create service account
2. Enable Domain-Wide Delegation
3. Add scope in Workspace Admin: `https://www.googleapis.com/auth/admin.directory.group`
4. Impersonate admin: `creds.with_subject("admin@domain.com")`

### Required Scopes
```python
"https://www.googleapis.com/auth/admin.directory.group"  # Full access
"https://www.googleapis.com/auth/admin.directory.group.readonly"  # Read-only
```

### Member Types
- `USER` - Workspace user
- `GROUP` - Nested group
- `CUSTOMER` - Entire domain

### Group Object Structure
```python
{
    "id": "group_id",
    "email": "team@domain.com",
    "name": "Engineering Team",
    "description": "All engineers",
    "directMembersCount": "50",
    "adminCreated": true,
    # ... additional fields
}
```

### Member Object Structure
```python
{
    "id": "member_id",
    "email": "user@domain.com",
    "role": "MEMBER",
    "type": "USER",
    "status": "ACTIVE",
    # ... additional fields
}
```

### Limitations
- No settings management (delivery preferences, permissions)
- No alias management
- No external member validation
- Uses deprecated Admin SDK (v1) - consider migration to Cloud Identity Groups API

### Refactoring Note
Monolithic class (223 LOC). Planned refactoring:
- Split into `operations/groups.py` + `operations/members.py`
- Reduce main class to ~80 LOC coordinator
- See: `docs/refactoring/groups.md`
