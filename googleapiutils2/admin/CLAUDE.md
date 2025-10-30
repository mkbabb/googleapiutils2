# admin/

Google Workspace Admin SDK wrapper: user management.

## File Tree

```
admin/
├── __init__.py          # Exports Admin
└── admin.py             # Admin class (user management)
```

## Key Classes

### Admin (admin.py)
Inherits `DriveBase` for caching, throttling, retry.

**User Methods:**
- `get_user(user_key, customer_id)` - Get user by email/ID
- `list_users(query, customer_id, order_by, max_results)` - List users (generator)
- `find_users_by_name(given_name, family_name, customer_id)` - Search by name
- `create_user(primary_email, given_name, family_name, password, **kwargs)` - Create user
- `delete_user(user_key, customer_id)` - Delete user
- `undelete_user(user_key, customer_id)` - Restore deleted user
- `update_user(user_key, body, customer_id)` - Update user fields
- `suspend_user(user_key, customer_id)` - Suspend account
- `unsuspend_user(user_key, customer_id)` - Restore account
- `update_password(user_key, password, change_password_at_next_login, customer_id)` - Change password
- `make_admin(user_key, customer_id)` - Grant super admin
- `revoke_admin(user_key, customer_id)` - Revoke admin
- `update_name(user_key, given_name, family_name, customer_id)` - Update name

## Constants

### API
- `VERSION = "directory_v1"` - Admin SDK API version

### Defaults
- `customer_id = "my_customer"` - Default domain
- `projection = "full"` - Detail level
- `view_type = "admin_view"` - Access level
- `order_by = "email"` - Sort field
- `max_results = 100` - Results per page

### User Fields
- `primaryEmail` - Email address (required)
- `name.givenName` - First name (required)
- `name.familyName` - Last name (required)
- `password` - Password (required for creation)
- `orgUnitPath` - Organizational unit
- `suspended` - Account status
- `isAdmin` - Super admin status
- `changePasswordAtNextLogin` - Force password change

## Usage Examples

### Create User
```python
from googleapiutils2 import Admin, get_oauth2_creds

# Service account with domain-wide delegation
creds = get_oauth2_creds("auth/service-account.json")
creds = creds.with_subject("admin@domain.com")
admin = Admin(creds=creds)

# Basic user
user = admin.create_user(
    primary_email="test@domain.com",
    given_name="Test",
    family_name="User",
    password="temppass123"
)

# With options
user = admin.create_user(
    primary_email="employee@domain.com",
    given_name="Jane",
    family_name="Doe",
    password="initial_pass",
    org_unit_path="/Engineering",
    change_password_at_next_login=True
)
```

### List & Search Users
```python
# All users
for user in admin.list_users():
    print(user['primaryEmail'], user['name'])

# Query
for user in admin.list_users(query="givenName:John familyName:Doe"):
    print(user)

# By organizational unit
for user in admin.list_users(query="orgUnitPath=/Engineering"):
    print(user['primaryEmail'])

# Search by name
users = admin.find_users_by_name(given_name="John", family_name="Doe")
```

### Update User
```python
# Suspend
admin.suspend_user("user@domain.com")

# Unsuspend
admin.unsuspend_user("user@domain.com")

# Change password
admin.update_password(
    "user@domain.com",
    "newpassword123",
    change_password_at_next_login=True
)

# Update name
admin.update_name("user@domain.com", given_name="Jonathan", family_name="Doe")

# Custom fields
admin.update_user("user@domain.com", {
    "orgUnitPath": "/Sales",
    "phones": [{"value": "555-1234", "type": "work"}]
})
```

### Admin Management
```python
# Grant admin
admin.make_admin("user@domain.com")

# Revoke admin
admin.revoke_admin("user@domain.com")
```

### Delete & Restore
```python
# Delete user
admin.delete_user("user@domain.com")

# Undelete (within 20 days)
admin.undelete_user("user@domain.com")
```

## Patterns

### Customer ID
```python
# Default: "my_customer" (primary domain)
admin = Admin(creds=creds)

# Explicit domain
admin = Admin(creds=creds, customer_id="C012345")
```

### Error Handling
```python
# get_user returns None if not found
user = admin.get_user("nonexistent@domain.com")
if user is None:
    print("User not found")

# delete_user returns None if not found (no error)
admin.delete_user("nonexistent@domain.com")  # Silent no-op
```

### Pagination
```python
# Generator pattern with automatic pagination
for user in admin.list_users(max_results=500):
    # Process incrementally
    pass
```

## Dependencies

**External:**
- `google-api-python-client` - DirectoryResource
- `google.oauth2.credentials` - Credentials
- `google.oauth2.service_account` - ServiceAccountCredentials

**Internal:**
- `googleapiutils2.utils.DriveBase` - Base class
- `googleapiutils2.utils.EXECUTE_TIME` - Throttling
- `googleapiutils2.utils.THROTTLE_TIME` - Rate limiting

## Public API

**Exported from `__init__.py`:**
- `Admin`

## Notes

### Authentication
**Requires:** Service account with domain-wide delegation

**Setup:**
1. Create service account: https://console.cloud.google.com/iam-admin/serviceaccounts
2. Enable Domain-Wide Delegation
3. Add scopes in Workspace Admin: https://admin.google.com/ac/owl/domainwidedelegation
   - `https://www.googleapis.com/auth/admin.directory.user`
   - `https://www.googleapis.com/auth/admin.directory.user.security`
4. Impersonate admin: `creds.with_subject("admin@domain.com")`

### Required Scopes
```python
# From utils/misc.py SCOPES
"https://www.googleapis.com/auth/admin.directory.user"
"https://www.googleapis.com/auth/admin.directory.user.security"
"https://www.googleapis.com/auth/admin.directory.domain"
```

### Query Syntax
Workspace directory API queries:
- `givenName:John` - First name
- `familyName:Doe` - Last name
- `orgUnitPath=/Engineering` - Organizational unit
- `isSuspended=true` - Suspended accounts
- `isAdmin=true` - Admin accounts

### Limitations
- No group management (see Groups module)
- No calendar resource management
- No mobile device management
- No Chrome device management

### User Object Structure
```python
{
    "primaryEmail": "user@domain.com",
    "name": {
        "givenName": "John",
        "familyName": "Doe",
        "fullName": "John Doe"
    },
    "suspended": false,
    "isAdmin": false,
    "orgUnitPath": "/",
    "creationTime": "2024-01-01T00:00:00.000Z",
    "lastLoginTime": "2024-01-15T10:30:00.000Z",
    # ... additional fields
}
```
