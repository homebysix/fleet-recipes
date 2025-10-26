# -*- coding: utf-8 -*-
#
# FleetImporter AutoPkg Processor
#
# Uploads a package to Fleet for software deployment.
#
# Requires: Python 3.9+
#

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from autopkglib import Processor, ProcessorError

# Constants for improved readability
DEFAULT_PLATFORM = "darwin"

# Fleet version constants
FLEET_MINIMUM_VERSION = "4.74.0"

# HTTP timeout constants (in seconds)
FLEET_VERSION_TIMEOUT = 30
FLEET_UPLOAD_TIMEOUT = 900  # 15 minutes for large packages


class FleetImporter(Processor):
    """
    Upload AutoPkg-built installer packages to Fleet for software deployment.

    This processor uploads software packages (.pkg files) to Fleet and configures
    deployment settings including self-service availability, automatic installation,
    host targeting via labels, and custom install/uninstall scripts.
    """

    description = __doc__
    input_variables = {
        # --- Required basics ---
        "pkg_path": {
            "required": True,
            "description": "Path to the built .pkg from AutoPkg.",
        },
        "software_title": {
            "required": True,
            "description": "Human-readable software title, e.g., 'Firefox.app'.",
        },
        "version": {
            "required": True,
            "description": "Software version string.",
        },
        "platform": {
            "required": False,
            "default": DEFAULT_PLATFORM,
            "description": "Platform (darwin|windows|linux|ios|ipados). Default: darwin",
        },
        # --- Fleet API ---
        "fleet_api_base": {
            "required": True,
            "description": "Fleet base URL, e.g., https://fleet.example.com",
        },
        "fleet_api_token": {
            "required": True,
            "description": "Fleet API token (Bearer).",
        },
        "team_id": {
            "required": True,
            "description": "Fleet team ID to attach the uploaded package to.",
        },
        # --- Fleet deployment options ---
        "self_service": {
            "required": False,
            "default": True,
            "description": "Whether the package is available for self-service installation.",
        },
        "automatic_install": {
            "required": False,
            "default": False,
            "description": "macOS-only: automatically install on hosts that don't have this software.",
        },
        "labels_include_any": {
            "required": False,
            "default": [],
            "description": "List of label names - software is available on hosts with ANY of these labels.",
        },
        "labels_exclude_any": {
            "required": False,
            "default": [],
            "description": "List of label names - software is excluded from hosts with ANY of these labels.",
        },
        "install_script": {
            "required": False,
            "default": "",
            "description": "Custom install script body (string).",
        },
        "uninstall_script": {
            "required": False,
            "default": "",
            "description": "Custom uninstall script body (string).",
        },
        "pre_install_query": {
            "required": False,
            "default": "",
            "description": "Pre-install osquery SQL condition.",
        },
        "post_install_script": {
            "required": False,
            "default": "",
            "description": "Post-install script body (string).",
        },
    }

    output_variables = {
        "fleet_title_id": {"description": "Created/updated Fleet software title ID."},
        "fleet_installer_id": {"description": "Installer ID in Fleet."},
        "hash_sha256": {
            "description": "SHA-256 hash of the uploaded package, as returned by Fleet."
        },
    }

    def main(self):
        # Validate inputs
        pkg_path = Path(self.env["pkg_path"]).expanduser().resolve()
        if not pkg_path.is_file():
            raise ProcessorError(f"pkg_path not found: {pkg_path}")

        software_title = self.env["software_title"].strip()
        version = self.env["version"].strip()
        # Platform parameter accepted for future use but not currently utilized
        _ = self.env.get("platform", DEFAULT_PLATFORM)  # noqa: F841

        fleet_api_base = self.env["fleet_api_base"].rstrip("/")
        fleet_token = self.env["fleet_api_token"]
        team_id = int(self.env["team_id"])

        # Fleet deployment options
        self_service = bool(self.env.get("self_service", False))
        automatic_install = bool(self.env.get("automatic_install", False))
        labels_include_any = list(self.env.get("labels_include_any", []))
        labels_exclude_any = list(self.env.get("labels_exclude_any", []))
        install_script = self.env.get("install_script", "")
        uninstall_script = self.env.get("uninstall_script", "")
        pre_install_query = self.env.get("pre_install_query", "")
        post_install_script = self.env.get("post_install_script", "")

        # Query Fleet API to get server version
        self.output("Querying Fleet server version...")
        fleet_version = self._get_fleet_version(fleet_api_base, fleet_token)
        self.output(f"Detected Fleet version: {fleet_version}")

        # Check minimum version requirements
        if not self._is_fleet_minimum_supported(fleet_version):
            raise ProcessorError(
                f"Fleet version {fleet_version} is not supported. "
                f"This processor requires Fleet v{FLEET_MINIMUM_VERSION} or higher. "
                f"Please upgrade your Fleet server to a supported version."
            )

        # Check if package already exists in Fleet
        self.output(
            f"Checking if {software_title} {version} already exists in Fleet..."
        )
        existing_package = self._check_existing_package(
            fleet_api_base, fleet_token, team_id, software_title, version
        )

        if existing_package:
            self.output(
                f"Package {software_title} {version} already exists in Fleet. Skipping upload."
            )
            # Calculate hash from local package file
            hash_sha256 = self._calculate_file_sha256(pkg_path)
            self.output(
                f"Calculated SHA-256 hash from local file: {hash_sha256[:16]}..."
            )
            # Set output variables for existing package
            self.env["fleet_title_id"] = None
            self.env["fleet_installer_id"] = None
            self.env["hash_sha256"] = hash_sha256
            return

        # Upload to Fleet
        self.output("Uploading package to Fleet...")
        upload_info = self._fleet_upload_package(
            fleet_api_base,
            fleet_token,
            pkg_path,
            software_title,
            version,
            team_id,
            self_service,
            automatic_install,
            labels_include_any,
            labels_exclude_any,
            install_script,
            uninstall_script,
            pre_install_query,
            post_install_script,
        )

        if not upload_info:
            raise ProcessorError("Fleet package upload failed; no data returned")

        # Check for graceful exit case (409 Conflict)
        if upload_info.get("package_exists"):
            self.output(
                "Package already exists in Fleet (409 Conflict). Exiting gracefully."
            )
            self.env["fleet_title_id"] = None
            self.env["fleet_installer_id"] = None
            return

        # Extract upload results
        software_package = upload_info.get("software_package", {})
        title_id = software_package.get("title_id")
        installer_id = software_package.get("installer_id")
        hash_sha256 = software_package.get("hash_sha256")

        # Set output variables
        self.output(
            f"Package uploaded successfully. Title ID: {title_id}, Installer ID: {installer_id}"
        )
        self.env["fleet_title_id"] = title_id
        self.env["fleet_installer_id"] = installer_id
        if hash_sha256:
            self.env["hash_sha256"] = hash_sha256

    # ------------------- helpers -------------------

    def _calculate_file_sha256(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file.

        Args:
            file_path: Path to the file to hash

        Returns:
            Lowercase hexadecimal SHA-256 hash string
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read in chunks to handle large files efficiently
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    def _is_fleet_minimum_supported(self, fleet_version: str) -> bool:
        """Check if Fleet version meets minimum requirements."""
        try:
            # Parse version string like "4.70.0" or "4.70.0-dev"
            version_parts = fleet_version.split("-")[0].split(".")
            major = int(version_parts[0])
            minor = int(version_parts[1])
            patch = int(version_parts[2]) if len(version_parts) > 2 else 0

            # Parse minimum version from constant
            min_parts = FLEET_MINIMUM_VERSION.split(".")
            min_major = int(min_parts[0])
            min_minor = int(min_parts[1])
            min_patch = int(min_parts[2]) if len(min_parts) > 2 else 0

            # Check if >= minimum version
            if major > min_major:
                return True
            elif major == min_major and minor > min_minor:
                return True
            elif major == min_major and minor == min_minor and patch >= min_patch:
                return True
            return False
        except (ValueError, IndexError):
            # If we can't parse the version, assume it's supported to avoid blocking
            return True

    def _check_existing_package(
        self,
        fleet_api_base: str,
        fleet_token: str,
        team_id: int,
        software_title: str,
        version: str,
    ) -> dict | None:
        """Query Fleet API to check if a package version already exists.

        Returns a dict with package info if it exists, None otherwise.
        The dict includes: version, hash_sha256 if the version matches.

        The API response includes a versions array with all uploaded versions.
        We check if our version exists in that array.
        """
        try:
            # Search for the software title
            query_param = urllib.parse.quote(software_title)
            search_url = f"{fleet_api_base}/api/v1/fleet/software/titles?available_for_install=true&team_id={team_id}&query={query_param}"
            headers = {
                "Authorization": f"Bearer {fleet_token}",
                "Accept": "application/json",
            }
            req = urllib.request.Request(search_url, headers=headers)

            with urllib.request.urlopen(req, timeout=FLEET_VERSION_TIMEOUT) as resp:
                if resp.getcode() == 200:
                    data = json.loads(resp.read().decode())
                    software_titles = data.get("software_titles", [])

                    self.output(
                        f"Found {len(software_titles)} software title(s) matching '{software_title}'"
                    )

                    # Look for title match - try exact match first, then case-insensitive, then fuzzy
                    matching_title = None
                    for title in software_titles:
                        title_name = title.get("name", "")
                        # Exact match (preferred)
                        if title_name == software_title:
                            matching_title = title
                            self.output(
                                f"Found exact match for '{software_title}' (title_id: {title.get('id')})"
                            )
                            break
                        # Case-insensitive match as fallback
                        elif title_name.lower() == software_title.lower():
                            matching_title = title
                            self.output(
                                f"Found case-insensitive match: '{title_name}' for '{software_title}' (title_id: {title.get('id')})"
                            )
                            break

                    # If no exact match, try fuzzy matching (e.g., "Zoom" matches "zoom.us", "Caffeine" matches "Caffeine.app")
                    if not matching_title and software_titles:
                        for title in software_titles:
                            title_name = title.get("name", "")
                            # Check if search term is contained in title name or vice versa (case-insensitive)
                            search_lower = software_title.lower()
                            title_lower = title_name.lower()
                            if (
                                search_lower in title_lower
                                or title_lower in search_lower
                            ):
                                matching_title = title
                                self.output(
                                    f"Found fuzzy match: '{title_name}' for '{software_title}' (title_id: {title.get('id')})"
                                )
                                break

                    if not matching_title:
                        # No exact or case-insensitive match - log what we found for debugging
                        if software_titles:
                            for title in software_titles:
                                self.output(
                                    f"No match found - searched for '{software_title}', found '{title.get('name', '')}'"
                                )
                        return None

                    # Check if our version exists in the versions array
                    versions = matching_title.get("versions", [])
                    if versions:
                        self.output(
                            f"Checking {len(versions)} version(s) for '{matching_title.get('name')}'"
                        )
                        for idx, ver in enumerate(versions):
                            # Debug: show what fields are in the version object
                            if isinstance(ver, dict):
                                ver_string = ver.get("version", "")
                                self.output(
                                    f"  Version {idx + 1}: '{ver_string}' (fields: {list(ver.keys())})"
                                )
                            elif isinstance(ver, str):
                                # Sometimes versions might be returned as strings directly
                                ver_string = ver
                                self.output(
                                    f"  Version {idx + 1}: '{ver_string}' (string)"
                                )
                            else:
                                self.output(
                                    f"  Version {idx + 1}: unexpected type {type(ver)}"
                                )
                                continue

                            if ver_string == version:
                                # Hash is at the title level, not version level
                                hash_sha256 = matching_title.get("hash_sha256")
                                self.output(
                                    f"Package {software_title} {version} already exists in Fleet (hash: {hash_sha256[:16] + '...' if hash_sha256 else 'none'})"
                                )
                                return {
                                    "version": ver_string,
                                    "hash_sha256": hash_sha256,
                                    "package_name": software_title,
                                }

                    # Check the currently available software_package as well
                    sw_package = matching_title.get("software_package")
                    if sw_package:
                        pkg_version = sw_package.get("version", "")
                        if pkg_version == version:
                            hash_sha256 = matching_title.get("hash_sha256")
                            self.output(
                                f"Package {software_title} {version} already exists in Fleet as current package (hash: {hash_sha256[:16] + '...' if hash_sha256 else 'none'})"
                            )
                            return {
                                "version": pkg_version,
                                "hash_sha256": hash_sha256,
                                "package_name": sw_package.get("name", software_title),
                            }

                    # Version not found in this title
                    self.output(
                        f"Version {version} not found for '{matching_title.get('name')}'"
                    )

        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            json.JSONDecodeError,
            KeyError,
        ) as e:
            # If query fails, log and continue with upload
            self.output(f"Warning: Could not check for existing package: {e}")

        return None

    def _get_fleet_version(self, fleet_api_base: str, fleet_token: str) -> str:
        """Query Fleet API to get the server version.

        Returns the semantic version string (e.g., "4.74.0").
        If the query fails, defaults to "4.74.0" (minimum supported) assuming a modern deployment.
        """
        try:
            url = f"{fleet_api_base}/api/v1/fleet/version"
            headers = {
                "Authorization": f"Bearer {fleet_token}",
                "Accept": "application/json",
            }
            req = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(req, timeout=FLEET_VERSION_TIMEOUT) as resp:
                if resp.getcode() == 200:
                    data = json.loads(resp.read().decode())
                    version = data.get("version", "")
                    if version:
                        # Parse version string like "4.74.0-dev" or "4.74.0"
                        # Extract just the semantic version part
                        return version.split("-")[0]

        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            json.JSONDecodeError,
            KeyError,
        ):
            # If we can't get the version, assume minimum supported version for modern deployments
            pass

        # Default to minimum supported version if query fails (assume modern Fleet deployment)
        return FLEET_MINIMUM_VERSION

    def _fleet_upload_package(
        self,
        base_url,
        token,
        pkg_path: Path,
        software_title: str,
        version: str,
        team_id: int,
        self_service: bool,
        automatic_install: bool,
        labels_include_any: list[str],
        labels_exclude_any: list[str],
        install_script: str,
        uninstall_script: str,
        pre_install_query: str,
        post_install_script: str,
    ) -> dict:
        url = f"{base_url}/api/v1/fleet/software/package"
        self.output(f"Uploading file to Fleet: {pkg_path}")
        # API rules: only one of include/exclude
        if labels_include_any and labels_exclude_any:
            raise ProcessorError(
                "Only one of labels_include_any or labels_exclude_any may be specified."
            )

        boundary = "----FleetUploadBoundary" + hashlib.sha1(os.urandom(16)).hexdigest()
        body = io.BytesIO()

        def write_field(name: str, value: str):
            body.write(f"--{boundary}\r\n".encode())
            body.write(
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
            )
            body.write(str(value).encode())
            body.write(b"\r\n")

        def write_file(name: str, filename: str, path: Path):
            body.write(f"--{boundary}\r\n".encode())
            body.write(
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
            )
            body.write(b"Content-Type: application/octet-stream\r\n\r\n")
            with open(path, "rb") as f:
                shutil.copyfileobj(f, body)
            body.write(b"\r\n")

        write_field("team_id", str(team_id))
        write_field("self_service", json.dumps(bool(self_service)).lower())
        if install_script:
            write_field("install_script", install_script)
        if uninstall_script:
            write_field("uninstall_script", uninstall_script)
        if pre_install_query:
            write_field("pre_install_query", pre_install_query)
        if post_install_script:
            write_field("post_install_script", post_install_script)
        if automatic_install:
            write_field("automatic_install", "true")

        for label in labels_include_any:
            write_field("labels_include_any", label)
        for label in labels_exclude_any:
            write_field("labels_exclude_any", label)

        write_file("software", pkg_path.name, pkg_path)
        body.write(f"--{boundary}--\r\n".encode())

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        req = urllib.request.Request(url, data=body.getvalue(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=FLEET_UPLOAD_TIMEOUT) as resp:
                resp_body = resp.read()
                status = resp.getcode()
        except urllib.error.HTTPError as e:
            if e.code == 409:
                # Package already exists in Fleet - return special marker for graceful exit
                self.output(
                    "Package already exists in Fleet (409 Conflict). Exiting gracefully."
                )
                return {"package_exists": True}
            raise ProcessorError(f"Fleet upload failed: {e.code} {e.read().decode()}")
        if status != 200:
            raise ProcessorError(f"Fleet upload failed: {status} {resp_body.decode()}")
        return json.loads(resp_body or b"{}")
