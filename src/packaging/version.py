# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.
"""PEP 440 version values and normalization helpers.

.. testsetup::

    from packaging.version import parse, normalize_pre, Version, _cmpkey
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._version_support import (
    VERSION_PATTERN,
    BaseVersion,
    LegacyVersion,
    comparison_key,
    normalize_pre,
    parse_letter_version,
)

if TYPE_CHECKING:
    # Type-check the published API; check the native adapter separately.
    from . import _version_python as _implementation

    USE_NATIVE_VERSION: bool = False
else:
    try:
        from . import _version_native as _implementation

        USE_NATIVE_VERSION = True
    except ModuleNotFoundError as exc:
        if exc.name != "importlib.version":
            raise
        from . import _version_python as _implementation

        USE_NATIVE_VERSION = False

Version = _implementation.Version
InvalidVersion = _implementation.InvalidVersion
_TrimmedRelease = _implementation.TrimmedRelease
_BaseVersion = BaseVersion
_Version = LegacyVersion
_cmpkey = comparison_key
_parse_letter_version = parse_letter_version

# Pickles use the public import path for either implementation.
Version.__module__ = __name__
InvalidVersion.__module__ = __name__
_BaseVersion.__module__ = __name__
_BaseVersion.__name__ = _BaseVersion.__qualname__ = "_BaseVersion"
_Version.__module__ = __name__
_Version.__name__ = _Version.__qualname__ = "_Version"
normalize_pre.__module__ = __name__
_TrimmedRelease.__module__ = __name__
_TrimmedRelease.__name__ = _TrimmedRelease.__qualname__ = "_TrimmedRelease"

__all__ = ["VERSION_PATTERN", "InvalidVersion", "Version", "normalize_pre", "parse"]


def __dir__() -> list[str]:
    return __all__


def parse(version: str) -> Version:
    """Parse a version string using the available implementation."""
    return Version(version)
