# Capability catalog

Use this tool-backed development capability to inspect the optional engineering capabilities available to the current project.

Run `python3 scripts/capability_manager.py list` for the derived catalog and `python3 scripts/capability_manager.py show <id>` for a complete descriptor. Use `audit` before relying on a selected capability.

The adapter is a repository-local development script. It installs nothing, does not contact a network service, and cannot modify application production dependencies, credentials, or runtime permissions.
