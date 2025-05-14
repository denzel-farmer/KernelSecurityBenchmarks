# SPDX-License-Identifier: GPL-2.0
#
# Builds a .config from a kunitconfig.
#
# Copyright (C) 2019, Google LLC.
# Author: Felix Guo <felixguoxiuping@gmail.com>
# Author: Brendan Higgins <brendanhiggins@google.com>


# TODO: add a qemu wrapper that includes qemu params for each architecture?? Like kunit_kernel.py

import os
from dataclasses import dataclass
import re
from typing import Any, Dict, Iterable, List, Tuple
from enum import Enum
from microwave2.utils.utils import Arch

CONFIG_IS_NOT_SET_PATTERN = r'^# CONFIG_(\w+) is not set$'
CONFIG_PATTERN = r'^CONFIG_(\w+)=(\S+|".*")$'


@dataclass(frozen=True)
class KconfigEntry:
    name: str
    value: str

    def __str__(self) -> str:
        if self.value == 'n':
            return f'# CONFIG_{self.name} is not set'
        return f'CONFIG_{self.name}={self.value}'


class KconfigParseError(Exception):
    """Error parsing Kconfig defconfig or .config."""


class Kconfig:
    """Represents defconfig or .config specified using the Kconfig language."""

    def __init__(self, kconfig_label="no_label") -> None:
        self._entries = {}  # type: Dict[str, str]
        self.kconfig_label = kconfig_label

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return self._entries == other._entries

    def __repr__(self) -> str:
        return ','.join(str(e) for e in self.as_entries())

    def set_label(self, kconfig_label: str) -> None:
        self.kconfig_label = kconfig_label

    def get_label(self) -> str:
        return self.kconfig_label

    def as_entries(self) -> Iterable[KconfigEntry]:
        for name, value in self._entries.items():
            yield KconfigEntry(name, value)

    def add_entry(self, name: str, value: str) -> None:
        self._entries[name] = value

    def is_subset_of(self, other: 'Kconfig') -> bool:
        for name, value in self._entries.items():
            b = other._entries.get(name)
            if b is None:
                if value == 'n':
                    continue
                return False
            if value != b:
                return False
        return True

    def conflicting_options(self, other: 'Kconfig') -> List[Tuple[KconfigEntry, KconfigEntry]]:
        diff = []  # type: List[Tuple[KconfigEntry, KconfigEntry]]
        for name, value in self._entries.items():
            b = other._entries.get(name)
            if b and value != b:
                pair = (KconfigEntry(name, value), KconfigEntry(name, b))
                diff.append(pair)
        return diff

    def merge_in_entries(self, other: 'Kconfig') -> None:
        for name, value in other._entries.items():
            self._entries[name] = value

    def write_to_file(self, path: str) -> None:
        with open(path, 'a+') as f:
            for e in self.as_entries():
                f.write(str(e) + '\n')


def parse_file(path: str) -> Kconfig:
    with open(path, 'r') as f:
        return parse_from_string(f.read())


def parse_from_string(blob: str) -> Kconfig:
    """Parses a string containing Kconfig entries."""
    kconfig = Kconfig()
    is_not_set_matcher = re.compile(CONFIG_IS_NOT_SET_PATTERN)
    config_matcher = re.compile(CONFIG_PATTERN)
    for line in blob.split('\n'):
        line = line.strip()
        if not line:
            continue

        match = config_matcher.match(line)
        if match:
            kconfig.add_entry(match.group(1), match.group(2))
            continue

        empty_match = is_not_set_matcher.match(line)
        if empty_match:
            kconfig.add_entry(empty_match.group(1), 'n')
            continue

        if line[0] == '#':
            continue
        raise KconfigParseError('Failed to parse: ' + line)
    return kconfig


DEFCONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "linux-configs")

# TOOD also add configs for supporting important subsystems that can be merged
SUPPORTED_DEFCONFIGS = ["manual_minimized_defconfig", "def_localmod_defconfig", "manmin_nosec_defconfig"]
# Get parsed defconfig from name


def parse_defconfig(defconfig_name: str, arch: Arch) -> Kconfig:
    """Get parsed defconfig from name."""
    if defconfig_name not in SUPPORTED_DEFCONFIGS:
        raise KconfigParseError(f"Unsupported defconfig: {defconfig_name}")

    defconfig_path = os.path.join(
        DEFCONFIG_DIR, arch.linux_make_config_str(), defconfig_name)
    return parse_file(defconfig_path)


def generate_kconfig(arch: Arch, defconfig_names: list[str]=[], kconfig_strings: list[str]=[], kconfig_entries: List[KconfigEntry]=[], label_base:str=None, allow_def_override=False) -> Kconfig:
    """
    Generate a kernel config, can be specified with any combination of the following:
        - supported defconfig name 
        - absolute path to defconfig/.config file or fragment
        - string containing a defconfig/.config file or fragment
        - specific Kconfig entries
        Loads everything in and combines them into a single Kconfig object.
        Will validate that the configs don't directly conflict, but will not check kconfig dependencies.
        These dependencies must be checked by the kernel build system, so will not be validated until the kernel is built (
        in linux_make.py)
    """

    # Base config is empty
    if label_base is None:
        label = "gen_kconfig"
    else:
        label = label_base
    
    kconfig = Kconfig(kconfig_label=label)
   

    # Add defconfigs in order if specified
    for defconfig_name in defconfig_names:
        diff = kconfig.conflicting_options(parse_defconfig(defconfig_name, arch))
        if diff:
            raise KconfigParseError(str(f"Conflicting options found in {defconfig_name}: {diff}"))

        label += f"_{defconfig_name}"
        kconfig.set_label(label)
        kconfig.merge_in_entries(parse_defconfig(defconfig_name, arch))

    # Add kconfig strings in order if specified
    for kconfig_string in kconfig_strings:
        diff = kconfig.conflicting_options(parse_from_string(kconfig_string))
        if diff:
            if allow_def_override:
                print(f"Warning: Conflicting options found in {kconfig_string}: {diff}")
            else:
                raise KconfigParseError(str(f"Conflicting options found in {kconfig_string}: {diff}"))

        kconfig.merge_in_entries(parse_from_string(kconfig_string))


    # Add kconfig entries in order if specified
    for kconfig_entry in kconfig_entries:
        entry_config = Kconfig().add_entry(kconfig_entry.name, kconfig_entry.value)
        diff = kconfig.conflicting_options(entry_config)
        if diff:
            if allow_def_override:
                print(f"Warning: Conflicting options found in {kconfig_entry}: {diff}")
            else:
                raise KconfigParseError(f"Conflicting options found in {kconfig_entry}: {diff}")

        kconfig.merge_in_entries(entry_config)

    return kconfig