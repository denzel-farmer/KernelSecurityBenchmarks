# Wrapper for locally testing kernel modules via microwave
# Mostly a placeholder, should be replaced with something much better

from microwave2.testers.tester import TesterConfig

from microwave2.targets.kernel_target import KernelTarget
from microwave2.targets.kernel_module_target import KernelModuleTarget, KernelModuleTargetConfig
from microwave2.targets.target import TargetConfig

from microwave2.testers.module_tester import KernelModuleTester

from microwave2.tests.test import TestConfig, DynamicTestConfig
from microwave2.tests.linux_test import LinuxTest

from microwave2.remote import GitConfig, GitAuthInfo
from microwave2.results.result import Result, TestResult

from microwave2.local_storage import local_paths
from microwave2.results.kernel_log import RawKernelLogResult, KernelLog

from microwave2.utils.utils import Arch
import platform, os
from datetime import datetime

import json

def run_config(tester_config:TesterConfig) -> Result:
    tester = KernelModuleTester(tester_config)
    result = tester.download()
    if (result.is_failure()):
        print("Failed to download components")
        print(result.message, result.error)
        return result
    
    result = tester.build()
    if (result.is_failure()):
        print("Failed to build components")
        print(result.message, result.error)
        return result
    
    result = tester.run()
    if (result.is_failure()):
        print("Failed to run test")
        print(result.message, result.error)
        return result
    
    return result

def run_config_file(config_path:str) -> Result:
    """Run a kernel module test using a config file"""
    with open(config_path, "r") as f:
        json_str = f.read()

    json_dict = json.loads(json_str)
    config = TesterConfig.from_json(json_dict)
    result = run_config(config)

    results_path = os.path.join(local_paths.get_results_dir(), config.get_run_name(), "result.json")
    result.save_result(results_path)
    
    return result



