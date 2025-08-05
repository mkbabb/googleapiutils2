from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING, Any

from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from googleapiclient import discovery

from googleapiutils2.utils import (
    EXECUTE_TIME,
    THROTTLE_TIME,
    DriveBase,
)

if TYPE_CHECKING:
    from googleapiclient._apis.admin.directory_v1.resources import (
        DirectoryResource,
        User,
    )


class Admin(DriveBase):
    """A wrapper around the Google Admin SDK API for managing users and groups.

    Args:
        creds (Credentials, optional): The credentials to use. If None, the following paths will be tried:
            - ~/auth/credentials.json
            - env var: GOOGLE_API_CREDENTIALS
        execute_time (float, optional): The time to wait between requests. Defaults to EXECUTE_TIME (0.1).
        throttle_time (float, optional): The time to wait between requests. Defaults to THROTTLE_TIME (30).
        customer_id (str, optional): The customer ID to use. Defaults to "my_customer".
    """

    def __init__(
        self,
        creds: Credentials | ServiceAccountCredentials | None = None,
        execute_time: float = EXECUTE_TIME,
        throttle_time: float = THROTTLE_TIME,
        customer_id: str = "my_customer",
    ):
        super().__init__(
            creds=creds,
            execute_time=execute_time,
            throttle_time=throttle_time,
        )

        self.service: DirectoryResource = discovery.build("admin", "directory_v1", credentials=self.creds)  # type: ignore
        self.users = self.service.users()
        self.customer_id = customer_id

    def get_user(
        self,
        user_key: str,
        projection: str = "full",
        view_type: str = "admin_view",
        customer_id: str | None = None,
        **kwargs: Any,
    ) -> User | None:
        """Get a user by their email address or unique ID.

        Args:
            user_key (str): The user's email address or unique ID
            projection (str, optional): Amount of detail to include. Can be "basic", "full", or "custom".
            view_type (str, optional): Whether to fetch admin or domain-wide view
            customer_id (str, optional): Customer ID to use instead of default
            **kwargs: Additional parameters to pass to the API

        Returns:
            User: The user object
        """
        kwargs.update(
            {
                "userKey": user_key,
                "projection": projection,
                "viewType": view_type,
            }
        )

        if customer_id:
            kwargs["customer"] = customer_id

        try:
            return self.execute_no_retry(self.users.get(**kwargs))  # type: ignore
        except Exception:
            return None

    def find_users_by_name(
        self,
        given_name: str | None = None,
        family_name: str | None = None,
        **kwargs: Any,
    ) -> Generator[User, None, None]:
        """Find users by their given name and/or family name.

        Args:
            given_name (str, optional): First name to search for
            family_name (str, optional): Last name to search for
            **kwargs: Additional parameters to pass to list_users()

        Yields:
            User: User objects matching the name criteria
        """
        name_parts = []
        if given_name:
            name_parts.append(f"givenName='{given_name}'")
        if family_name:
            name_parts.append(f"familyName='{family_name}'")

        if name_parts:
            query = " ".join(name_parts)
            yield from self.list_users(query=query, **kwargs)

    def create_user(
        self,
        primary_email: str,
        given_name: str,
        family_name: str,
        password: str,
        org_unit_path: str = "/",
        suspended: bool = False,
        change_password_at_next_login: bool = False,
        get_extant: bool = True,
        **kwargs: Any,
    ) -> User:
        """Create a new Google Workspace user.

        Args:
            primary_email (str): The user's primary email address
            given_name (str): The user's first name
            family_name (str): The user's last name
            password (str): The user's password
            org_unit_path (str, optional): The user's org unit path. Defaults to "/".
            suspended (bool, optional): Whether the user is suspended. Defaults to False.
            change_password_at_next_login (bool, optional): Whether the user must change password
            get_extant (bool, optional): Return existing user if found. Defaults to True.
            **kwargs: Additional fields to include in the user object

        Returns:
            User: The created or existing user object
        """
        if get_extant and (existing_user := self.get_user(primary_email)):
            return existing_user

        user_data = {
            "primaryEmail": primary_email,
            "name": {
                "givenName": given_name,
                "familyName": family_name,
            },
            "password": password,
            "orgUnitPath": org_unit_path,
            "suspended": suspended,
            "changePasswordAtNextLogin": change_password_at_next_login,
        }
        user_data.update(kwargs)

        return self.execute(self.users.insert(body=user_data))  # type: ignore

    def update_user(
        self,
        user_key: str,
        updates: dict[str, Any],
        **kwargs: Any,
    ) -> User:
        """Update a user's information.

        Args:
            user_key (str): The user's email address or unique ID
            updates (dict): Dictionary of fields to update
            **kwargs: Additional parameters to pass to the API

        Returns:
            User: The updated user object
        """
        return self.execute(self.users.update(userKey=user_key, body=updates, **kwargs))  # type: ignore

    def delete_user(
        self,
        user_key: str,
        ignore_if_not_found: bool = True,
        **kwargs: Any,
    ) -> None:
        """Delete a user.

        Args:
            user_key (str): The user's email address or unique ID
            **kwargs: Additional parameters to pass to the API
        """
        try:
            self.execute_no_retry(self.users.delete(userKey=user_key, **kwargs))  # type: ignore
        except Exception as e:
            if ignore_if_not_found and "notFound" in str(e):
                return None
            else:
                raise e

    def list_users(
        self,
        query: str | None = None,
        order_by: str = "email",
        projection: str = "full",
        customer_id: str | None = None,
        show_deleted: bool = False,
        max_results: int = 100,
        page_token: str | None = None,
        **kwargs: Any,
    ) -> Generator[User, None, None]:
        """List users in the domain.

        Args:
            query (str, optional): Query string for filtering users
            order_by (str, optional): Property to use for sorting
            projection (str, optional): Amount of detail to include
            customer_id (str, optional): Customer ID to use instead of default
            show_deleted (str, optional): Include deleted users
            max_results (int, optional): Maximum results per page
            page_token (str, optional): Token for getting the next page
            **kwargs: Additional parameters to pass to the API

        Yields:
            User: User objects matching the criteria
        """
        params = {
            "customer": customer_id or self.customer_id,
            "maxResults": max_results,
            "orderBy": order_by,
            "projection": projection,
            "showDeleted": show_deleted,
            **kwargs,
        }

        if query:
            params["query"] = query
        if page_token:
            params["pageToken"] = page_token

        while True:
            response: Any = self.execute(self.users.list(**params))
            yield from response.get("users", [])

            if not response.get("nextPageToken"):
                break

            params["pageToken"] = response["nextPageToken"]

    def undelete_user(
        self,
        user_key: str,
        org_unit_path: str = "/",
        **kwargs: Any,
    ) -> User:
        """Undelete a previously deleted user.

        Args:
            user_key (str): The user's email address or unique ID
            org_unit_path (str, optional): Org unit to place the restored user in
            **kwargs: Additional parameters to pass to the API

        Returns:
            User: The restored user object
        """
        return self.execute(self.users.undelete(userKey=user_key, body={"orgUnitPath": org_unit_path}, **kwargs))  # type: ignore

    def suspend_user(
        self,
        user_key: str,
        **kwargs: Any,
    ) -> User:
        """Suspend a user's account.

        Args:
            user_key (str): The user's email address or unique ID
            **kwargs: Additional parameters to pass to the API

        Returns:
            User: The updated user object
        """
        return self.update_user(user_key=user_key, updates={"suspended": True}, **kwargs)

    def unsuspend_user(
        self,
        user_key: str,
        **kwargs: Any,
    ) -> User:
        """Unsuspend a user's account.

        Args:
            user_key (str): The user's email address or unique ID
            **kwargs: Additional parameters to pass to the API

        Returns:
            User: The updated user object
        """
        return self.update_user(user_key=user_key, updates={"suspended": False}, **kwargs)

    def update_password(
        self,
        user_key: str,
        password: str,
        change_password_at_next_login: bool = True,
        **kwargs: Any,
    ) -> User:
        """Update a user's password.

        Args:
            user_key (str): The user's email address or unique ID
            password (str): The new password
            change_password_at_next_login (bool, optional): Whether user must change password
            **kwargs: Additional parameters to pass to the API

        Returns:
            User: The updated user object
        """
        return self.update_user(
            user_key=user_key,
            updates={
                "password": password,
                "changePasswordAtNextLogin": change_password_at_next_login,
            },
            **kwargs,
        )

    def make_admin(
        self,
        user_key: str,
        **kwargs: Any,
    ) -> User:
        """Make a user a super admin.

        Args:
            user_key (str): The user's email address or unique ID
            **kwargs: Additional parameters to pass to the API

        Returns:
            User: The updated user object
        """
        return self.update_user(user_key=user_key, updates={"isAdmin": True}, **kwargs)

    def revoke_admin(
        self,
        user_key: str,
        **kwargs: Any,
    ) -> User:
        """Revoke a user's super admin status.

        Args:
            user_key (str): The user's email address or unique ID
            **kwargs: Additional parameters to pass to the API

        Returns:
            User: The updated user object
        """
        return self.update_user(user_key=user_key, updates={"isAdmin": False}, **kwargs)

    def update_name(
        self,
        user_key: str,
        given_name: str | None = None,
        family_name: str | None = None,
        **kwargs: Any,
    ) -> User:
        """Update a user's name.

        Args:
            user_key (str): The user's email address or unique ID
            given_name (str, optional): New first name
            family_name (str, optional): New last name
            **kwargs: Additional parameters to pass to the API

        Returns:
            User: The updated user object
        """
        updates: dict = {"name": {}}
        if given_name is not None:
            updates["name"]["givenName"] = given_name
        if family_name is not None:
            updates["name"]["familyName"] = family_name

        return self.update_user(user_key=user_key, updates=updates, **kwargs)
