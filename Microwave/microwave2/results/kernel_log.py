from microwave2.results.result import TestResult, Status

import re
import json

from typing import List

KERNEL_LOG_LINE_REGEX = re.compile(r"^\[\s*\d+\.\d+\]\s*(.*)$")

# TODO integrate kunit_parser


class KernelLog:
    """Record of kernel logs, eventually should support parsing Tests/KTAP"""

    def __init__(self, initial_lines: List[str] = None, test_marker=None):
        self.raw_lines = []

        self.has_test_section = False
        if test_marker is not None:
            self.has_test_section = True
            self.test_section_start = None
            self.test_section_end = None
            self.test_marker = re.compile(test_marker)

        if initial_lines is not None:
            for line in initial_lines:
                self.add_line(line)

    def get_raw_lines(self):
        """Return the raw lines in the log"""
        return self.raw_lines

    def check_line(self, line: str, idx: int):
        """Check if a line is a section marker, and record if so"""
        if not self.has_test_section:
            return False

        # Extract log line from kernel log line
        match = KERNEL_LOG_LINE_REGEX.match(line)
        if match is None:
         #   print("[KernelLog] Warning: line does not match kernel log regex")
            return False

        line = match.group(1)
        # print(f"[KernelLog] Checking line {idx}: {line}")

        # Strip line
        line = line.strip()

        # Check if line is a section marker by comparing to regex
        if not self.test_marker.match(line):
            return False

        # If line is a section marker, check if we are already in a section
        if self.test_section_start is None:
            # If we are not in a section, set the start of the section
            self.test_section_start = idx
        elif self.test_section_end is None:
            # If we are in a section, set the end of the section
            self.test_section_end = idx
        else:
            print("[KernelLog] Warning: unbalanced test section markers")

        return True

    def test_lines(self):
        """Return the lines in the test section"""
        if not self.has_test_section:
            print("[KernelLog] Warning: test section markers not found")
            return self.raw_lines

        if self.test_section_start is None:
            print("[KernelLog] Warning: test section markers not found")
            return self.raw_lines

        if self.test_section_end is None:
            # Return everything after the start
            print(
                "[KernelLog] Warning: test section end not found, returning everything after start")
            return self.raw_lines[self.test_section_start:]

        return self.raw_lines[self.test_section_start:self.test_section_end+1]

    def add_line(self, line: str, strip=True):
        if strip:
            line = line.strip()

        self.check_line(line, len(self.raw_lines))
        self.raw_lines.append(line)

    def to_json_dict(self):
        """Return the log as a json dictionary"""
        return {
            "lines": self.raw_lines,
            "metadata": {
                "test_marker": self.test_marker.pattern if self.has_test_section else None
            }
        }

    # Method to serialize log to and from disk (including test marker)
    # Formatted as json dictionary with two keys: "lines" and "metadata",
    # where "lines" is a list of strings and "metadata" is a dictionary for
    # now only containing the test marker

    def to_JSON(self, path: str):
        """Dump the log to a file"""
        with open(path, "w") as f:
            json.dump(
                {
                    "lines": self.raw_lines,
                    "metadata":
                        {
                            "test_marker": self.test_marker.pattern
                        }
                }, f)

    @classmethod
    def from_JSON(cls, path: str):
        """Load the log from a file"""
        with open(path, "r") as f:
            data = json.load(f)
            return cls(data["lines"], data["metadata"]["test_marker"])

    def log_str(self, test_only: bool = False):
        """Return the log as a string"""
        log_lines = self.raw_lines
        if test_only:
            log_lines = self.test_lines()

        return "\n".join(log_lines)

    def dump_log(self, path: str, test_only: bool = False):
        """Dump the log to a file"""
        with open(path, "w") as f:
            f.write(self.log_str(test_only=test_only))


class RawKernelLogResult(TestResult):
    def __init__(self, kernel_log: KernelLog, name: str = None):
        self.kernel_log = kernel_log
        super().__init__(name=name, sub_results=[])

    @classmethod
    def from_log_file(cls, file_path: str, test_marker=None):
        with open(file_path, 'r') as file:
            lines = file.readlines()

        kernel_log = KernelLog(initial_lines=lines, test_marker=test_marker)
        return cls(kernel_log)

    def get_lines(self):
        return self.kernel_log.raw_lines

    def get_test_lines(self):
        return self.kernel_log.test_lines()

    def get_kernel_log(self):
        return self.kernel_log

    def to_json(self):
        parent_json = super().to_json()
        parent_json["kernel_log"] = self.kernel_log.to_json_dict()
        return parent_json

    # TODO integrate process exit code


class KernelLogResult(RawKernelLogResult):
    def __init__(self, kernel_log):
        super().__init__(kernel_log)
        self.parse_sub_results()

    def parse_test_line(self, line) -> TestResult:
        """Test line regex"""
        # Test lines should be of the form [TIMESTAMP] TEST <testname>: <PASS/FAIL>, <optional message>
        # Example: [  123.456789] TEST blue_test: PASS, it was blue

        test_line_regex = re.compile(
            r"^\[\s*\d+\.\d+\]\s*TEST\s+(\w+):\s*(PASS|FAIL)(?:,\s*(.*))?$")
        match = test_line_regex.match(line)
        if match is None:
            return None
        test_name = match.group(1)
        test_status = match.group(2)
        test_message = match.group(3)
        if test_status == "PASS":
            return TestResult.success(test_message, test_name)
        else:
            return TestResult.failure(test_message, test_name)

    def parse_sub_results(self):
        self.sub_results = []
        for line in self.kernel_log.get_lines():
            test_result = self.parse_test_line(line)
            if test_result is not None:
                self.sub_results.append(test_result)
