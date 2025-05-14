import enum

import re

from dataclasses import dataclass

from typing import List


class Status(enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"

class Result:
    """Result of a test"""
    def __init__(self, status: Status, message: str = None, error: Exception = None):
        self.status = status
        self.message = message
        self.error = error

    @classmethod
    def success(cls, message: str = None):
        return cls(status=Status.SUCCESS, message=message)
    
    @classmethod
    def failure(cls, message: str = None, error: Exception = None):
        return cls(status=Status.FAILURE, message=message, error=error)
    
    def is_success(self):
        return self.status == Status.SUCCESS
    
    def is_failure(self):
        return self.status == Status.FAILURE
    
    def to_json(self):
        return {
            "status": self.status.value,
            "message": self.message,
            "error": str(self.error) if self.error else None
        }

    def save_result(self, result_dir: str):
        """Save the result to a JSON file"""
        import json
        with open(file_path, 'w') as f:
            json.dump(self.to_json(), f, indent=4)

    # str method
    def __str__(self):
        return f"Result(status={self.status}, message={self.message}, error={self.error})"
    
    # repr method
    def __repr__(self):
        return self.__str__()
    
class ProcResult(Result):
    """Result of a process run with subprocess, includes: returncode, stdout, stderr"""
    def __init__(self, returncode: int, stdout: str, stderr: str, message: str = None, error: Exception = None):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        
        status = Status.SUCCESS if returncode == 0 else Status.FAILURE
        super().__init__(status=status, message=message, error=error)

    def get_stdout(self):
        return self.stdout

    def get_stderr(self):
        return self.stderr

    def get_returncode(self):
        return self.returncode

    def to_json(self):
        parent_json = super().to_json()
        parent_json["returncode"] = self.returncode
        parent_json["stdout"] = self.stdout
        parent_json["stderr"] = self.stderr
        return parent_json

    def __str__(self):
        return f"ProcResult(returncode={self.returncode}, stdout={self.stdout}, stderr={self.stderr})"



class TestResult(Result):
    def __init__(self, name:str = None, sub_results:List['TestResult']=[]):  
        self.name = name
        self.sub_results = sub_results

        super().__init__(status=self.is_success())

    def has_name(self):
        return self.name is not None
    
    def get_name(self):
        return self.name
    
    # Add success class method
    @classmethod
    def success(cls, message: str = None, name: str = None):
        return cls(status=Status.SUCCESS, message=message, name=name)
    
    # Add failure class method
    @classmethod
    def failure(cls, message: str = None, name: str = None):
        return cls(status=Status.FAILURE, message=message, name=name)

    def add_sub_result(self, result):
        self.sub_results.append(result)
        self.status = self.is_success()

    def is_success(self):
        return all(r.is_success() for r in self.sub_results)

    def to_json(self):
        parent_json = super().to_json()
        parent_json["name"] = self.name
        parent_json["sub_results"] = [r.to_json() for r in self.sub_results]
        return parent_json


    