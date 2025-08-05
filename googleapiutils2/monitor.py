from __future__ import annotations

import tempfile
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from googleapiutils2.drive import Drive
from googleapiutils2.sheets import Sheets, SheetsRange
from googleapiutils2.utils import parse_file_id

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import File


class ResourceType(Enum):
    DRIVE = "drive"
    SHEETS = "sheets"


@dataclass
class MonitoredResource:
    """A resource being monitored for changes."""

    resource_id: str
    last_modified: str

    file: File

    metadata: Any | None = None


class ResourceMonitor(ABC):
    """Monitor for changes to Google Drive or Sheets resources.

    Uses efficient polling with revision tracking to detect changes to resources.

    Args:
        resource: The Drive or Sheets instance to use
        resource_id: The ID or URL of the resource to monitor
        callback: Function to call when changes are detected
        interval: How often to check for changes (in seconds)
    """

    def __init__(
        self,
        resource: Drive | Sheets,
        drive: Drive,
        resource_id: str,
        callback: Callable[[Any, ResourceMonitor | SheetsMonitor | DriveMonitor], None],
        interval: int = 30,
    ):
        self.resource = resource
        self.resource_id = parse_file_id(resource_id)

        self.drive = drive

        self.callback = callback
        self.interval = interval

        self.running = False

        self._monitor_thread: threading.Thread | None = None
        self._state_thread: threading.Thread | None = None

    @abstractmethod
    def _get_current_state(self) -> MonitoredResource:
        """Get the current state of the resource.

        This must include at the least:
        - The resource's revision ID
        - The resource's last modified date
        - The resource's File object from the Drive API
        """
        ...

    @abstractmethod
    def _get_current_data(self) -> Any:
        """Get the current data of the resource.

        This method should return the current data of the resource.
        """
        ...

    def _has_changed(self, current_state: MonitoredResource, prev_state: MonitoredResource) -> bool:
        """Check if the resource has changed since the last check."""
        return current_state.last_modified != prev_state.last_modified

    def _state_loop(self):
        """Main monitoring loop that checks for changes."""
        prev_state = self._get_current_state()

        while self.running:
            try:
                current_state = self._get_current_state()

                # Check if the resource has been modified
                if self._has_changed(current_state=current_state, prev_state=prev_state):
                    # Get the current data and call the callback
                    current_data = self._get_current_data()

                    self.callback(current_data, self)

                    prev_state = current_state

                time.sleep(self.interval)
            except Exception as e:
                print(f"Error in monitor loop: {e}")
                time.sleep(self.interval)

    def _init_monitor(self) -> None:
        def monitor_thread():
            main_thread = threading.main_thread()

            main_thread.join()

            self._cleanup()

        self._monitor_thread = threading.Thread(target=monitor_thread, daemon=True)
        self._monitor_thread.start()

    def start(self) -> None:
        """Start monitoring the resource."""
        if self.running:
            return

        self.running = True
        self._monitor_thread = threading.Thread(target=self._state_loop, daemon=False)
        self._monitor_thread.start()

    def stop(self) -> None:
        """Stop monitoring the resource."""
        self.running = False

        if self._state_thread is not None:
            self._state_thread.join()

    def _cleanup(self) -> None:
        """Clean up resources and ensure graceful shutdown."""
        # Wait for remaining items in queue
        if self._state_thread is None:
            return

        self.running = False

        self._state_thread.join()


class DriveMonitor(ResourceMonitor):
    """Monitor for changes to Google Drive resources.

    Args:
        resource: The Drive instance to use
        resource_id: The ID or URL of the resource to monitor
        callback: Function to call when changes are detected
        interval: How often to check for changes (in seconds)
    """

    def __init__(
        self,
        drive: Drive,
        resource_id: str,
        callback: Callable[[Any, ResourceMonitor], None],
        interval: int = 30,
    ):
        super().__init__(
            resource=drive,
            drive=drive,
            resource_id=resource_id,
            callback=callback,
            interval=interval,
        )
        self.drive = cast(Drive, self.resource)

    def _get_current_state(self) -> MonitoredResource:
        """Get the current state of the Drive resource."""
        file = self.drive.get(
            file_id=self.resource_id,
            fields="id,modifiedTime",
        )

        return MonitoredResource(
            resource_id=file["id"],
            last_modified=file["modifiedTime"],
            file=file,
        )

    def _get_current_data(self) -> Any:
        """Get the current data of the Drive resource."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            self.drive.download(filepath=temp_file.name, file_id=self.resource_id)
            # read the file and return the contents
            with open(temp_file.name) as f:
                return f.read()


class SheetsMonitor(ResourceMonitor):
    """Monitor for changes to Google Sheets resources.

    Can monitor either an entire spreadsheet or a specific range within it.

    Args:
        sheets: The Sheets instance to use
        drive: The Drive instance to use for metadata
        spreadsheet_id: The ID or URL of the spreadsheet to monitor
        range_name: Optional range to monitor (e.g., "Sheet1!A1:D10" or "Sheet1")
        callback: Function to call when changes are detected
        interval: How often to check for changes (in seconds)
    """

    def __init__(
        self,
        sheets: Sheets,
        drive: Drive,
        spreadsheet_id: str,
        callback: Callable[[Any, ResourceMonitor], None],
        range_name: SheetsRange | None = None,
        interval: int = 30,
    ):
        super().__init__(
            resource=sheets,
            drive=drive,
            resource_id=spreadsheet_id,
            callback=callback,
            interval=interval,
        )
        self.sheets = cast(Sheets, self.resource)

        self.range_name = range_name

    def _get_current_state(self) -> MonitoredResource:
        """Get the current state of the Sheets resource."""
        # Get file metadata from Drive API
        file = self.drive.get(
            file_id=self.resource_id,
            fields="id,modifiedTime",
        )

        # Get additional sheets metadata if needed
        metadata = None
        if self.range_name:
            try:
                metadata = self.sheets.get_spreadsheet(spreadsheet_id=self.resource_id, range_names=[self.range_name])
            except Exception as e:
                logger.warning(f"Failed to get sheets metadata: {e}")

        return MonitoredResource(
            resource_id=file["id"],
            last_modified=file["modifiedTime"],
            file=file,
            metadata=metadata,
        )

    def _get_current_data(self) -> Any:
        """Get the current data of the Sheets resource."""
        if self.range_name:
            # If range is specified, get just that range
            return self.sheets.values(spreadsheet_id=self.resource_id, range_name=self.range_name)
        else:
            # Otherwise get the entire spreadsheet
            return self.sheets.get_spreadsheet(
                spreadsheet_id=self.resource_id,
                include_grid_data=True,
            )

    def _has_changed(self, current_state: MonitoredResource, prev_state: MonitoredResource) -> bool:
        """Enhanced change detection for sheets that includes range-specific checks."""
        # First check basic file changes
        basic_changed = super()._has_changed(current_state, prev_state)
        if basic_changed:
            return True

        # If monitoring a specific range, check range metadata
        return bool(self.range_name and current_state.metadata and prev_state.metadata and current_state.metadata != prev_state.metadata)
