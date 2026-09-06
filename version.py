"""Single source of truth for the application version.

Bump this, add a CHANGELOG section, then tag and publish a GitHub release
(``git tag vX.Y.Z && git push origin vX.Y.Z && gh release create vX.Y.Z``).
Running copies compare this number against the latest release tag.
"""

__version__ = "1.6.0"
