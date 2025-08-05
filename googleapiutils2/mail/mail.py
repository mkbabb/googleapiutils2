from __future__ import annotations

import base64
from collections.abc import Generator
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING, Literal

from google.oauth2.credentials import Credentials
from googleapiclient import discovery

from googleapiutils2.utils import (
    EXECUTE_TIME,
    THROTTLE_TIME,
    DriveBase,
    ServiceAccountCredentials,
)

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1.resources import (
        Draft,
        GmailResource,
        Label,
        Message,
    )

VERSION = "v1"


class Mail(DriveBase):
    """A wrapper around the Gmail API.

    Args:
        creds (Credentials, optional): The credentials to use. If None, the following paths will be tried:
            - ~/auth/credentials.json
            - env var: GOOGLE_API_CREDENTIALS
        execute_time (float, optional): The time to wait between requests. Defaults to EXECUTE_TIME (0.1).
        throttle_time (float, optional): The time to wait between requests. Defaults to THROTTLE_TIME (30).
    """

    def __init__(
        self,
        creds: Credentials | ServiceAccountCredentials | None = None,
        execute_time: float = EXECUTE_TIME,
        throttle_time: float = THROTTLE_TIME,
    ):
        super().__init__(creds=creds, execute_time=execute_time, throttle_time=throttle_time)

        self.service: GmailResource = discovery.build("gmail", VERSION, credentials=self.creds)  # type: ignore
        self.messages = self.service.users().messages()
        self.drafts = self.service.users().drafts()
        self.labels = self.service.users().labels()

    def _create_message(
        self,
        sender: str,
        to: str | list[str],
        subject: str,
        body: str,
        html: bool = False,
    ) -> Message:
        """Create a message for an email.

        Args:
            sender: Email address of the sender.
            to: Email address(es) of the receiver(s).
            subject: Subject of the email.
            body: Body of the email.
            html: Whether the body is HTML. Defaults to False.

        Returns:
            An object containing a base64url encoded email object.
        """
        if isinstance(to, str):
            to = [to]

        message = MIMEMultipart()
        message["to"] = ", ".join(to)
        message["from"] = sender
        message["subject"] = subject

        msg_type = "html" if html else "plain"
        message.attach(MIMEText(body, msg_type))

        return {"raw": base64.urlsafe_b64encode(message.as_bytes()).decode()}

    def send(
        self,
        sender: str,
        to: str | list[str],
        subject: str,
        body: str,
        html: bool = False,
        user_id: str = "me",
    ) -> Message:
        """Send an email message.

        Args:
            sender: Email address of the sender.
            to: Email address(es) of the receiver(s).
            subject: Subject of the email.
            body: Body of the email.
            html: Whether the body is HTML. Defaults to False.
            user_id: The user's email address. 'me' refers to authenticated user.

        Returns:
            The sent Message.
        """
        message = self._create_message(
            sender=sender,
            to=to,
            subject=subject,
            body=body,
            html=html,
        )

        return self.execute(self.messages.send(userId=user_id, body=message))  # type: ignore

    def create_draft(
        self,
        sender: str,
        to: str | list[str],
        subject: str,
        body: str,
        html: bool = False,
        user_id: str = "me",
    ) -> Draft:
        """Create an email draft.

        Args:
            sender: Email address of the sender.
            to: Email address(es) of the receiver(s).
            subject: Subject of the email.
            body: Body of the email.
            html: Whether the body is HTML. Defaults to False.
            user_id: The user's email address. 'me' refers to authenticated user.

        Returns:
            The created Draft.
        """
        message = self._create_message(
            sender=sender,
            to=to,
            subject=subject,
            body=body,
            html=html,
        )

        return self.execute(self.drafts.create(userId=user_id, body={"message": message}))  # type: ignore

    def list_messages(
        self,
        query: str | None = None,
        label_ids: list[str] | None = None,
        max_results: int | None = None,
        user_id: str = "me",
    ) -> Generator[Message, None, None]:
        """List Messages of the user's mailbox matching the query.

        Args:
            query: Only return messages matching the specified query.
                Supports the same query format as the Gmail search box.
                For example: "from:someuser@example.com after:2023/04/01"
            label_ids: Only return messages with labels that match all given label IDs.
            max_results: Maximum number of messages to return.
            user_id: The user's email address. 'me' refers to authenticated user.

        Yields:
            Messages that match the search criteria
        """
        request = self.messages.list(userId=user_id)
        if query:
            request = self.messages.list(userId=user_id, q=query)
        if label_ids:
            request = self.messages.list(userId=user_id, labelIds=label_ids)
        if max_results:
            request = self.messages.list(userId=user_id, maxResults=max_results)

        while request is not None:
            response = self.execute(request)  # type: ignore
            messages = response.get("messages", [])  # type: ignore

            for message in messages:
                full_msg = self.get_message(message["id"], user_id=user_id)
                yield full_msg

            request = self.messages.list_next(request, response)  # type: ignore

    def get_message(
        self,
        message_id: str,
        format: Literal["full", "metadata", "minimal"] = "full",
        user_id: str = "me",
    ) -> Message:
        """Get a Message with given ID.

        Args:
            message_id: The ID of the Message required.
            format: The format to return the message in.
            user_id: The user's email address. 'me' refers to authenticated user.

        Returns:
            A Message.
        """
        return self.execute(self.messages.get(userId=user_id, id=message_id, format=format))  # type: ignore

    def modify_message(
        self,
        message_id: str,
        add_label_ids: list[str] | None = None,
        remove_label_ids: list[str] | None = None,
        user_id: str = "me",
    ) -> Message:
        """Modify the labels on the specified message.

        Args:
            message_id: The ID of the message to modify.
            add_label_ids: A list of label IDs to add to the message.
            remove_label_ids: A list of label IDs to remove from the message.
            user_id: The user's email address. 'me' refers to authenticated user.

        Returns:
            The modified message.
        """
        body = {
            "addLabelIds": add_label_ids or [],
            "removeLabelIds": remove_label_ids or [],
        }

        return self.execute(
            self.messages.modify(userId=user_id, id=message_id, body=body)  # type: ignore
        )  # type: ignore

    def trash_message(self, message_id: str, user_id: str = "me") -> Message:
        """Move a message to trash.

        Args:
            message_id: The ID of the message to trash.
            user_id: The user's email address. 'me' refers to authenticated user.

        Returns:
            The trashed Message.
        """
        return self.execute(self.messages.trash(userId=user_id, id=message_id))  # type: ignore

    def untrash_message(self, message_id: str, user_id: str = "me") -> Message:
        """Remove a message from trash.

        Args:
            message_id: The ID of the message to remove from trash.
            user_id: The user's email address. 'me' refers to authenticated user.

        Returns:
            The untrashed Message.
        """
        return self.execute(self.messages.untrash(userId=user_id, id=message_id))  # type: ignore

    def delete_message(self, message_id: str, user_id: str = "me") -> None:
        """Permanently delete a message. This operation cannot be undone.

        Args:
            message_id: The ID of the message to delete.
            user_id: The user's email address. 'me' refers to authenticated user.
        """
        self.execute(self.messages.delete(userId=user_id, id=message_id))  # type: ignore

    def list_labels(self, user_id: str = "me") -> Generator[Label, None, None]:
        """Lists all labels in the user's mailbox.

        Args:
            user_id: The user's email address. 'me' refers to authenticated user.

        Yields:
            Label objects
        """
        response = self.execute(self.labels.list(userId=user_id))  # type: ignore
        yield from response.get("labels", [])  # type: ignore

    def get_label(self, label_id: str, user_id: str = "me") -> Label:
        """Gets a specific label.

        Args:
            label_id: The ID of the label to retrieve.
            user_id: The user's email address. 'me' refers to authenticated user.

        Returns:
            A Label object.
        """
        return self.execute(self.labels.get(userId=user_id, id=label_id))  # type: ignore

    def create_label(
        self,
        name: str,
        label_list_visibility: Literal["labelShow", "labelHide", "labelShowIfUnread"] = "labelShow",
        message_list_visibility: Literal["show", "hide"] = "show",
        user_id: str = "me",
    ) -> Label:
        """Creates a new label.

        Args:
            name: The display name of the label.
            label_list_visibility: The visibility of the label in the label list.
            message_list_visibility: The visibility of messages with this label.
            user_id: The user's email address. 'me' refers to authenticated user.

        Returns:
            The created Label.
        """
        label_object = {
            "name": name,
            "labelListVisibility": label_list_visibility,
            "messageListVisibility": message_list_visibility,
        }

        return self.execute(
            self.labels.create(userId=user_id, body=label_object)  # type: ignore
        )  # type: ignore

    def delete_label(self, label_id: str, user_id: str = "me") -> None:
        """Deletes a label.

        Args:
            label_id: The ID of the label to delete.
            user_id: The user's email address. 'me' refers to authenticated user.
        """
        self.execute(self.labels.delete(userId=user_id, id=label_id))  # type: ignore

    def modify_label(
        self,
        label_id: str,
        name: str | None = None,
        label_list_visibility: (Literal["labelShow", "labelHide", "labelShowIfUnread"] | None) = None,
        message_list_visibility: Literal["show", "hide"] | None = None,
        user_id: str = "me",
    ) -> Label:
        """Updates a label.

        Args:
            label_id: The ID of the label to modify.
            name: The display name of the label.
            label_list_visibility: The visibility of the label in the label list.
            message_list_visibility: The visibility of messages with this label.
            user_id: The user's email address. 'me' refers to authenticated user.

        Returns:
            The modified Label.
        """
        label_object = {}
        if name is not None:
            label_object["name"] = name
        if label_list_visibility is not None:
            label_object["labelListVisibility"] = label_list_visibility
        if message_list_visibility is not None:
            label_object["messageListVisibility"] = message_list_visibility

        return self.execute(
            self.labels.update(userId=user_id, id=label_id, body=label_object)  # type: ignore
        )  # type: ignore
