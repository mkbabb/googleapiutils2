from __future__ import annotations

import operator
from typing import *

from cachetools import cachedmethod
from google.oauth2.credentials import Credentials
from googleapiclient import discovery

from ..drive.misc import create_listing_fields, list_drive_items
from ..utils import (
    EXECUTE_TIME,
    THROTTLE_TIME,
    DriveBase,
    named_methodkey,
)
from .misc import DEFAULT_FIELDS, VERSION

if TYPE_CHECKING:
    pass
    from googleapiclient._apis.admin.directory_v1 import (
        DirectoryResource,
        Group,
        Member,
    )


class Groups(DriveBase):
    """A wrapper around the Google Groups API.

    Args:
        creds (Credentials, optional): The credentials to use. If None, the following paths will be tried:
            - ~/auth/credentials.json
            - env var: GOOGLE_API_CREDENTIALS
        execute_time (float, optional): The time to wait between requests. Defaults to EXECUTE_TIME (0.1).
        throttle_time (float, optional): The time to wait between requests. Defaults to THROTTLE_TIME (30).
    """

    def __init__(
        self,
        creds: Credentials | None = None,
        execute_time: float = EXECUTE_TIME,
        throttle_time: float = THROTTLE_TIME,
    ):
        super().__init__(
            creds=creds, execute_time=execute_time, throttle_time=throttle_time
        )

        self.service: DirectoryResource = discovery.build(
            "admin", VERSION, credentials=self.creds
        )  # type: ignore
        self.groups = self.service.groups()

        self.members = self.service.members()

    @cachedmethod(operator.attrgetter("_cache"), key=named_methodkey("get"))
    def get(
        self,
        group_id: str,
        fields: str = DEFAULT_FIELDS,
    ) -> Group:

        return self.execute(self.groups.get(groupKey=group_id, fields=fields))

    def list(
        self,
        customer: str | None = None,
        domain: str | None = None,
        query: str | None = None,
        fields: str = DEFAULT_FIELDS,
        order_by: str = "email",
    ) -> Iterable[Group]:
        if customer is None and domain is None:
            raise ValueError("Either customer or domain must be provided.")

        kwargs = {}
        if customer is not None:
            kwargs["customer"] = customer
        if domain is not None:
            kwargs["domain"] = domain
        if query is not None:
            kwargs["query"] = query

        list_func = lambda x: self.execute(
            self.groups.list(
                **kwargs,  # type: ignore
                pageToken=x,
                fields=create_listing_fields(fields),
                orderBy=order_by,  # type: ignore
            )
        )

        for response in list_drive_items(list_func):
            yield from response.get("groups", [])  # type: ignore

    def create(
        self,
        email: str,
        name: str,
        description: str | None = None,
        group: Group | None = None,
    ) -> Group:
        group = group if group is not None else {}
        group |= {
            "email": email.strip().lower(),
            "name": name,
        }  # type: ignore
        if description is not None:
            group["description"] = description

        return self.execute(self.groups.insert(body=group))

    def update(
        self,
        group_id: str,
        group: Group,
    ) -> Group:
        return self.execute(self.groups.update(groupKey=group_id, body=group))

    def delete(self, group_id: str) -> None:
        self.execute(self.groups.delete(groupKey=group_id))

    def has_member(
        self,
        group_key: str,
        member_key: str,
    ) -> bool:
        return self.execute(
            self.members.hasMember(
                groupKey=group_key,
                memberKey=member_key,
            )
        ).get("isMember", False)

    @cachedmethod(operator.attrgetter("_cache"), key=named_methodkey("members_get"))
    def members_get(
        self,
        group_key: str,
        member_key: str | None = None,
        member: Member | None = None,
    ) -> Member:
        """Gets a group member's metadata by its key.

        Args:
            group_id (str): The ID of the group.
            member_key (str): The key of the member to get.
        """
        if member_key is None and member is None:
            raise ValueError("Either member_key or member must be provided.")

        if member is not None:
            return member

        return self.execute(
            self.members.get(
                groupKey=group_key,
                memberKey=member_key,  # type: ignore
            )
        )

    def members_list(
        self,
        group_key: str,
        includeDerivedMembership: bool = False,
    ) -> Iterable[Member]:
        list_func = lambda x: self.execute(
            self.members.list(
                groupKey=group_key,
                includeDerivedMembership=includeDerivedMembership,
                pageToken=x,
            )
        )
        for response in list_drive_items(list_func):
            yield from response.get("members", [])  # type: ignore

    def members_insert(
        self,
        group_key: str,
        member_key: str | None = None,
        member: Member | None = None,
    ) -> Member:
        member = self.members_get(
            group_key=group_key, member_key=member_key, member=member
        )
        member_key = member.get("id")

        return self.execute(
            self.members.insert(
                groupKey=group_key,
                body=member,  # type: ignore
            )
        )

    def members_update(
        self,
        group_key: str,
        member_key: str | None = None,
        member: Member | None = None,
    ) -> Member:
        member = self.members_get(
            group_key=group_key, member_key=member_key, member=member
        )
        member_key = member.get("id")

        return self.execute(
            self.members.update(
                groupKey=group_key,
                memberKey=member_key,  # type: ignore
                body=member,
            )
        )

    def members_delete(
        self,
        group_key: str,
        member_key: str | None = None,
        member: Member | None = None,
    ) -> None:
        member = self.members_get(
            group_key=group_key, member_key=member_key, member=member
        )
        member_key = member.get("id")

        self.execute(
            self.members.delete(
                groupKey=group_key,
                memberKey=member_key,  # type: ignore
            )
        )
