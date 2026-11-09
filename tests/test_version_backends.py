# This file is dual licensed under the terms of the Apache License, Version
# 2.0, and the BSD License. See the LICENSE file in the root of this repository
# for complete details.
"""Public pickle identities must survive changes to the available backend."""

from __future__ import annotations

import builtins
import importlib
import os
import pickle
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import packaging.version
from packaging._version_support import subclass_state
from packaging.version import _TrimmedRelease
from tests.version_pickle_support import (
    DictionaryVersion,
    LabeledVersion,
    PrivateSlotsVersion,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence


_WORKER = """
import pickle
import sys
if sys.argv[1] == "python":
    sys.modules["importlib.version"] = None
from packaging.version import InvalidVersion, Version, _TrimmedRelease
from packaging.specifiers import SpecifierSet
from packaging.requirements import Requirement
from tests.version_pickle_support import (
    CustomStateVersion, LabeledVersion, RequiredLabelVersion,
)
labeled = LabeledVersion("1!2.3rc4.post5.dev6+abc.1")
labeled.label = "label"
labeled.extra = {"a": 1}
custom = CustomStateVersion("2.4")
custom.label = "custom"
values = [Version("1.2.0"), labeled, SpecifierSet(">=1.0,!=2.0"),
          Requirement("demo[extra]>=1.0; python_version > '3.10'"),
          InvalidVersion("bad version"), RequiredLabelVersion("2.3", "required"),
          _TrimmedRelease("1.2.0.0"), custom]
if sys.argv[2] == "write":
    data = [
        pickle.dumps(item, protocol)
        for protocol in range(pickle.HIGHEST_PROTOCOL + 1)
        for item in values
    ]
    sys.stdout.buffer.write(pickle.dumps(data))
else:
    data = pickle.loads(sys.stdin.buffer.read())
    assert len(data) == len(values) * (pickle.HIGHEST_PROTOCOL + 1)
    for index, payload in enumerate(data):
        value = pickle.loads(payload)
        expected = values[index % len(values)]
        assert type(value) is type(expected), (value, expected)
        assert str(value) == str(expected), (value, expected)
        if isinstance(value, Version):
            assert value.release == expected.release
            assert hash(value) == hash(expected)
        for name in ("label", "extra", "args"):
            assert getattr(value, name, None) == getattr(expected, name, None)
        # The object must remain serializable after restoration, too.
        assert type(pickle.loads(pickle.dumps(value))) is type(value)
"""


def run_backend(backend: str, action: str, data: bytes = b"") -> bytes:
    """Use fresh imports so each process selects exactly one backend."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [sys.executable, "-c", _WORKER, backend, action],
        input=data,
        capture_output=True,
        env=env,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr.decode()
    return result.stdout


@pytest.mark.parametrize("writer", ["python", "current"])
@pytest.mark.parametrize("reader", ["python", "current"])
def test_pickles_restore_into_selected_backend(writer: str, reader: str) -> None:
    run_backend(reader, "read", run_backend(writer, "write"))


# Written by unchanged packaging 713d0d7 using Python 3.15 and protocol 2.
_TRIMMED_RELEASE_PICKLE = (
    b"\x80\x02cpackaging.version\n_TrimmedRelease\nq\x00)\x81q\x01"
    b"(K\x00K\x01K\x00K\x00\x87q\x02NNNNtq\x03b."
)


def test_historical_trimmed_release_pickle() -> None:
    value = pickle.loads(_TRIMMED_RELEASE_PICKLE)
    assert str(value) == "1"
    assert value.release == (1,)
    assert str(pickle.loads(pickle.dumps(value))) == "1"


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
def test_subclass_dictionary_and_private_slots(protocol: int) -> None:
    labeled = LabeledVersion("1.2.3")
    labeled.label = "slot"
    labeled.extra = {"key": "value"}
    restored = pickle.loads(pickle.dumps(labeled, protocol))
    assert restored.label == "slot"
    assert restored.extra == {"key": "value"}

    private = PrivateSlotsVersion("1.2.3")
    private.set_label("private")
    assert pickle.loads(pickle.dumps(private, protocol)).get_label() == "private"
    unset = PrivateSlotsVersion("1.2.3")
    assert str(pickle.loads(pickle.dumps(unset, protocol))) == "1.2.3"

    dictionary = DictionaryVersion("1.2.3")
    dictionary.note = "dictionary"
    assert pickle.loads(pickle.dumps(dictionary, protocol)).note == "dictionary"


def test_subclass_rejects_invalid_historical_slots() -> None:
    value = LabeledVersion("1.2.3")
    with pytest.raises(TypeError):
        value.__setstate__((None, "not slots"))


def test_native_import_dependency_error_is_not_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = builtins.__import__

    def broken(
        name: str,
        namespace: Mapping[str, object] | None = None,
        localns: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> object:
        if level == 1 and "_version_native" in fromlist:
            raise ModuleNotFoundError(
                "missing internal dependency", name="unrelated_dependency"
            )
        return original(name, namespace, localns, fromlist, level)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(builtins, "__import__", broken)
            with pytest.raises(ModuleNotFoundError, match="missing internal"):
                importlib.reload(packaging.version)
    finally:
        importlib.reload(packaging.version)


def test_trimmed_subclass_attributes_survive_pickle() -> None:
    class LabeledTrimmed(_TrimmedRelease):
        __slots__ = ("label",)
        label: str

    value = LabeledTrimmed("1.0.0")
    value.__setstate__((None, {"label": "trimmed"}))
    assert value.label == "trimmed"
    assert str(value) == "1"


def test_default_object_state_for_dictionary_only_subclass() -> None:
    class StateOnly:
        note: str

    value = StateOnly()
    value.note = "state"
    assert subclass_state(value) == {"note": "state"}


def test_legacy_pre_release_parser() -> None:
    assert packaging.version._parse_letter_version("ALPHA", None) == ("a", 0)
    assert packaging.version._parse_letter_version(None, "2") == ("post", 2)
