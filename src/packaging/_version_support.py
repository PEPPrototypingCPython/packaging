# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.
"""
.. testsetup::

    from packaging.version import parse, normalize_pre, Version, comparison_key
"""

from __future__ import annotations

import builtins
import re
import sys
import typing
from abc import ABCMeta
from collections.abc import Callable
from importlib import import_module
from typing import (
    Any,
    Literal,
    NamedTuple,
    SupportsInt,
    TypedDict,
)

if sys.version_info >= (3, 13):  # pragma: no cover
    from warnings import deprecated as deprecated  # noqa: PLC0414 - Strict re-export.
elif typing.TYPE_CHECKING:
    from typing_extensions import deprecated as deprecated  # noqa: PLC0414 - Strict re-export.
else:  # pragma: no cover
    import functools
    import warnings

    def deprecated(message: str) -> object:
        def decorator(func: Callable[[...], object]) -> object:
            @functools.wraps(func)
            def wrapper(*args: object, **kwargs: object) -> object:
                warnings.warn(
                    message,
                    category=DeprecationWarning,
                    stacklevel=2,
                )
                return func(*args, **kwargs)

            return wrapper

        return decorator


_LETTER_NORMALIZATION = {
    "alpha": "a",
    "beta": "b",
    "c": "rc",
    "pre": "rc",
    "preview": "rc",
    "rev": "post",
    "r": "post",
}


LocalType = tuple[int | str, ...]


CmpLocalType = tuple[tuple[int, str], ...]


CmpSuffix = tuple[int, int, int, int, int, int]


CmpKey = (
    tuple[int, tuple[int, ...], CmpSuffix]
    | tuple[int, tuple[int, ...], CmpSuffix, CmpLocalType]
)


VersionComparisonMethod = Callable[[CmpKey, CmpKey], bool]


# Sentinel for __replace__, typed as Any so it can be the default for any field.
# mypy is missing sentinel currently
UNSET: Any = object() if sys.version_info < (3, 15) else builtins.sentinel("UNSET")  # type: ignore[attr-defined]


def normalize_pre(letter: str, /) -> str:
    """Normalize the pre-release segment of a version string.

    Returns a lowercase version of the string if not a known pre-release
    identifier.

    >>> normalize_pre('alpha')
    'a'
    >>> normalize_pre('BETA')
    'b'
    >>> normalize_pre('rc')
    'rc'

    :param letter:

    .. versionadded:: 26.1
    """
    letter = letter.lower()
    return _LETTER_NORMALIZATION.get(letter, letter)


class InvalidVersion(ValueError):
    """Raised when a version string is not a valid version.

    >>> Version("invalid")
    Traceback (most recent call last):
        ...
    packaging.version.InvalidVersion: Invalid version: 'invalid'
    """


if typing.TYPE_CHECKING:
    ComparisonMeta = ABCMeta
else:
    try:
        import_module("importlib.version")
    except ModuleNotFoundError as exc:
        if exc.name != "importlib.version":
            raise
        ComparisonMeta = type
    else:
        ComparisonMeta = ABCMeta


# Virtual native membership is unnecessary on the Python-only backend.
class BaseVersion(metaclass=ComparisonMeta):
    __slots__ = ()

    # This can also be a normal member (see the packaging_legacy package);
    # we are just requiring it to be readable. Actually defining a property
    # has runtime effect on subclasses, so it's typing only.
    if typing.TYPE_CHECKING:

        @property
        def _key(self) -> tuple[Any, ...]: ...

    def __hash__(self) -> int:
        return hash(self._key)

    # Please keep the duplicated `isinstance` check
    # in the six comparisons hereunder
    # unless you find a way to avoid adding overhead function calls.
    def __lt__(self, other: BaseVersion) -> bool:
        if not isinstance(other, BaseVersion):
            return NotImplemented

        return self._key < other._key

    def __le__(self, other: BaseVersion) -> bool:
        if not isinstance(other, BaseVersion):
            return NotImplemented

        return self._key <= other._key

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseVersion):
            return NotImplemented

        return self._key == other._key

    def __ge__(self, other: BaseVersion) -> bool:
        if not isinstance(other, BaseVersion):
            return NotImplemented

        return self._key >= other._key

    def __gt__(self, other: BaseVersion) -> bool:
        if not isinstance(other, BaseVersion):
            return NotImplemented

        return self._key > other._key

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, BaseVersion):
            return NotImplemented

        return self._key != other._key


# Deliberately unanchored so callers can embed the pattern in larger expressions.
# ++ behaves differently on CPython and PyPy, so use *+ and ?+ instead.
_VERSION_PATTERN = r"""
    v?+                                                   # optional leading v
    (?a:
        (?:(?P<epoch>[0-9]+)!)?+                          # epoch
        (?P<release>[0-9]+(?:\.[0-9]+)*+)                 # release segment
        (?P<pre>                                          # pre-release
            [._-]?+
            (?P<pre_l>alpha|a|beta|b|preview|pre|c|rc)
            [._-]?+
            (?P<pre_n>[0-9]+)?
        )?+
        (?P<post>                                         # post release
            (?:-(?P<post_n1>[0-9]+))
            |
            (?:
                [._-]?
                (?P<post_l>post|rev|r)
                [._-]?
                (?P<post_n2>[0-9]+)?
            )
        )?+
        (?P<dev>                                          # dev release
            [._-]?+
            (?P<dev_l>dev)
            [._-]?+
            (?P<dev_n>[0-9]+)?
        )?+
    )
    (?a:\+
        (?P<local>                                        # local version
            [a-z0-9]+
            (?:[._-][a-z0-9]+)*+
        )
    )?+
"""


# Early Python 3.11 and PyPy releases had possessive-qualifier bugs.
_VERSION_PATTERN_OLD = _VERSION_PATTERN.replace("*+", "*").replace("?+", "?")


VERSION_PATTERN = (
    _VERSION_PATTERN_OLD
    if (sys.implementation.name == "cpython" and sys.version_info < (3, 11, 5))
    or (sys.implementation.name == "pypy" and sys.version_info < (3, 11, 13))
    or sys.version_info < (3, 11)
    else _VERSION_PATTERN
)


"""
A string containing the regular expression used to match a valid version.

The pattern is not anchored at either end, and is intended for embedding in larger
expressions (for example, matching a version number as part of a file name). The
regular expression should be compiled with the ``re.VERBOSE`` and ``re.IGNORECASE``
flags set.

.. versionchanged:: 26.0

   The regex now uses possessive qualifiers on Python 3.11 if they are
   supported (CPython 3.11.5+, PyPy 3.11.13+).

:meta hide-value:
"""


_LOCAL_PATTERN = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", re.IGNORECASE | re.ASCII)


SIMPLE_VERSION_INDICATORS = frozenset(".0123456789")


def validate_epoch(value: object, /) -> int:
    epoch = value or 0
    if isinstance(epoch, int) and epoch >= 0:
        return epoch
    msg = f"epoch must be non-negative integer, got {epoch}"
    raise InvalidVersion(msg)


def validate_release(value: object, /) -> tuple[int, ...]:
    release = (0,) if value is None else value
    if (
        isinstance(release, tuple)
        and len(release) > 0
        and all(isinstance(i, int) and i >= 0 for i in release)
    ):
        return release
    msg = f"release must be a non-empty tuple of non-negative integers, got {release}"
    raise InvalidVersion(msg)


def validate_pre(value: object, /) -> tuple[Literal["a", "b", "rc"], int] | None:
    if value is None:
        return value
    if isinstance(value, tuple) and len(value) == 2:
        letter, number = value
        # The letter must be a string before it can be normalized.
        if (
            isinstance(letter, str)
            and (normalized := normalize_pre(letter)) in {"a", "b", "rc"}
            and isinstance(number, int)
            and number >= 0
        ):
            # type checkers can't infer the Literal type here on letter
            return (normalized, number)  # type: ignore[return-value]
    msg = f"pre must be a tuple of ('a'|'b'|'rc', non-negative int), got {value}"
    raise InvalidVersion(msg)


def validate_post(value: object, /) -> tuple[Literal["post"], int] | None:
    if value is None:
        return value
    if isinstance(value, int) and value >= 0:
        return ("post", value)
    msg = f"post must be non-negative integer, got {value}"
    raise InvalidVersion(msg)


def validate_dev(value: object, /) -> tuple[Literal["dev"], int] | None:
    if value is None:
        return value
    if isinstance(value, int) and value >= 0:
        return ("dev", value)
    msg = f"dev must be non-negative integer, got {value}"
    raise InvalidVersion(msg)


def validate_local(value: object, /) -> LocalType | None:
    if value is None:
        return value
    if isinstance(value, str) and _LOCAL_PATTERN.fullmatch(value):
        return parse_local_version(value)
    msg = f"local must be a valid version string, got {value!r}"
    raise InvalidVersion(msg)


class LegacyVersion(NamedTuple):
    epoch: int
    release: tuple[int, ...]
    dev: tuple[Literal["dev"], int] | None
    pre: tuple[Literal["a", "b", "rc"], int] | None
    post: tuple[Literal["post"], int] | None
    local: LocalType | None


def subclass_state(value: object, excluded: tuple[str, ...] = ()) -> object:
    """Preserve subclass attributes without serializing implementation caches."""
    if sys.version_info >= (3, 11):
        state = object.__getstate__(value)
    else:
        # Python 3.10 has no object.__getstate__; subclasses may add arbitrary slots.
        dictionary = getattr(value, "__dict__", None)
        slots: dict[str, object] = {}
        for cls in type(value).__mro__:
            names = cls.__dict__.get("__slots__", ())
            if isinstance(names, str):
                names = (names,)
            for slot_name in names:
                if slot_name in {"__dict__", "__weakref__"}:
                    continue
                name = slot_name
                if slot_name.startswith("__") and not slot_name.endswith("__"):
                    name = "_" + cls.__name__.lstrip("_") + slot_name
                item = getattr(value, name, UNSET)
                if item is not UNSET:
                    slots[name] = item
        state = (dictionary, slots) if slots else dictionary
    if isinstance(state, tuple):
        dictionary, slots = state
        slots = {name: item for name, item in slots.items() if name not in excluded}
        return (dictionary, slots) if slots else dictionary
    return state


def restore_subclass_state(value: object, state: object) -> bool:
    """Apply subclass pickle state, excluding historical component states."""
    dictionary = state
    slots: dict[str, object] = {}
    if isinstance(state, tuple) and len(state) == 2:
        dictionary, raw_slots = state
        if not isinstance(raw_slots, dict) or "_epoch" in raw_slots:
            return False
        slots = raw_slots
    if dictionary is not None and (
        not isinstance(dictionary, dict) or "_version" in dictionary
    ):
        return False
    if dictionary is not None:
        value.__dict__.update(dictionary)
    # Slot names are a dynamic part of the subclass serialization contract.
    for name, item in list(slots.items()):
        setattr(value, name, item)
    return True


def parse_letter_version(
    letter: str | None, number: str | bytes | SupportsInt | None
) -> tuple[str, int] | None:
    if letter:
        # We normalize any letters to their lower case form
        letter = letter.lower()

        # Normalize alternate pre-release names to their short forms.
        letter = _LETTER_NORMALIZATION.get(letter, letter)

        # A missing pre-release number is zero.
        return letter, int(number or 0)

    if number:
        # We assume if we are given a number, but we are not given a letter
        # then this is using the implicit post release syntax (e.g. 1.0-1)
        return "post", int(number)

    return None


_local_version_separators = re.compile(r"[\._-]")


def parse_local_version(local: str | None) -> LocalType | None:
    """
    Takes a string like ``"abc.1.twelve"`` and turns it into
    ``("abc", 1, "twelve")``.
    """
    if local is not None:
        return tuple(
            part.lower() if not part.isdigit() else int(part)
            for part in _local_version_separators.split(local)
        )
    return None


_PRE_RANK = {"a": 0, "b": 1, "rc": 2}


_PRE_RANK_DEV_ONLY = -1  # sorts before a(0)


_PRE_RANK_STABLE = 3  # sorts after rc(2)


_LOCAL_STR_RANK = -1  # sorts before all non-negative ints


_STABLE_SUFFIX = (_PRE_RANK_STABLE, 0, 0, 0, 1, 0)


def comparison_key(
    epoch: int,
    release: tuple[int, ...],
    pre: tuple[str, int] | None,
    post: tuple[str, int] | None,
    dev: tuple[str, int] | None,
    local: LocalType | None,
) -> CmpKey:
    """Build a comparison key for PEP 440 ordering.

    Returns ``(epoch, release, suffix)`` or
    ``(epoch, release, suffix, local)`` so that plain tuple
    comparison gives the correct order.

    Trailing zeros are stripped from the release so that ``1.0.0 == 1``.

    The suffix is a flat 6-int tuple that encodes pre/post/dev:
    ``(pre_rank, pre_n, post_rank, post_n, dev_rank, dev_n)``

    pre_rank: dev-only=-1, a=0, b=1, rc=2, no-pre=3
        Dev-only releases (no pre or post) get -1 so they sort before
        any alpha/beta/rc.  Releases without a pre-release tag get 3
        so they sort after rc.
    post_rank: no-post=0, post=1
        Releases without a post segment sort before those with one.
    dev_rank: dev=0, no-dev=1
        Releases without a dev segment sort after those with one.

    Local segments use ``(n, "")`` for ints and ``(-1, s)`` for strings,
    following PEP 440: strings sort before ints, strings compare
    lexicographically, ints compare numerically, and shorter segments
    sort before longer when prefixes match.  Versions without a local
    segment sort before those with one (3-tuple < 4-tuple).

    >>> comparison_key(0, (1, 0, 0), None, None, None, None)
    (0, (1,), (3, 0, 0, 0, 1, 0))
    >>> comparison_key(0, (1,), ("a", 1), None, None, None)
    (0, (1,), (0, 1, 0, 0, 1, 0))
    >>> comparison_key(0, (1,), None, None, None, ("ubuntu", 1))
    (0, (1,), (3, 0, 0, 0, 1, 0), ((-1, 'ubuntu'), (1, '')))
    """
    # Strip trailing zeros: 1.0.0 compares equal to 1.
    len_release = len(release)
    i = len_release
    while i and release[i - 1] == 0:
        i -= 1
    trimmed = release if i == len_release else release[:i]

    # Fast path: stable release with no local segment.
    if pre is None and post is None and dev is None and local is None:
        return epoch, trimmed, _STABLE_SUFFIX

    if pre is None and post is None and dev is not None:
        # dev-only (e.g. 1.0.dev1) sorts before all pre-releases.
        pre_rank, pre_n = _PRE_RANK_DEV_ONLY, 0
    elif pre is None:
        pre_rank, pre_n = _PRE_RANK_STABLE, 0
    else:
        pre_rank, pre_n = _PRE_RANK[pre[0]], pre[1]

    post_rank = 0 if post is None else 1
    post_n = 0 if post is None else post[1]

    dev_rank = 1 if dev is None else 0
    dev_n = 0 if dev is None else dev[1]

    suffix = (pre_rank, pre_n, post_rank, post_n, dev_rank, dev_n)

    if local is None:
        return epoch, trimmed, suffix

    cmp_local: CmpLocalType = tuple(
        (seg, "") if isinstance(seg, int) else (_LOCAL_STR_RANK, seg) for seg in local
    )
    return epoch, trimmed, suffix, cmp_local


class VersionParts(TypedDict):
    epoch: int
    release: tuple[int, ...]
    pre: tuple[str, int] | None
    post: int | None
    dev: int | None
    local: str | None


def legacy_version_parts(state: object) -> VersionParts:
    """Decode and validate historical component pickle formats."""
    if isinstance(state, tuple) and len(state) == 6:
        epoch, release, pre, post, dev, local = state
    elif isinstance(state, tuple) and len(state) == 2 and isinstance(state[1], dict):
        slots = state[1]
        epoch, release = slots["_epoch"], slots["_release"]
        pre, post, dev, local = (
            slots.get(name) for name in ("_pre", "_post", "_dev", "_local")
        )
    elif isinstance(state, dict) and isinstance(state.get("_version"), LegacyVersion):
        version = state["_version"]
        epoch, release = version.epoch, version.release
        pre, post, dev, local = version.pre, version.post, version.dev, version.local
    else:
        raise TypeError(f"Cannot restore Version from {state!r}")
    normalized_epoch = validate_epoch(epoch)
    normalized_release = validate_release(release)
    normalized_pre = validate_pre(pre)
    normalized_post = validate_post(None if post is None else post[1])
    normalized_dev = validate_dev(None if dev is None else dev[1])
    return {
        "epoch": normalized_epoch,
        "release": normalized_release,
        "pre": normalized_pre,
        "post": None if normalized_post is None else normalized_post[1],
        "dev": None if normalized_dev is None else normalized_dev[1],
        "local": None if local is None else ".".join(map(str, local)),
    }
