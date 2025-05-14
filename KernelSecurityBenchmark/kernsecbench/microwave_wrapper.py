# TODO merge with local kmod

# Wrapper for locally testing kernel modules via microwave
# Mostly a placeholder, should be replaced with something much better

from microwave2.testers.tester import TesterConfig

from microwave2.targets.kernel_target import KernelTarget, KernelTargetConfig
from microwave2.targets.kernel_module_target import KernelModuleTarget, KernelModuleTargetConfig
from microwave2.targets.target import TargetConfig

from microwave2.utils.kernel_config import Kconfig, generate_kconfig

from microwave2.testers.kernel_tester import KernelTester

from microwave2.tests.test import TestConfig, DynamicTestConfig
from microwave2.tests.linux_test import LinuxTest

from microwave2.remote import GitConfig, GitAuthInfo
from microwave2.results.result import Result, TestResult
from microwave2.results.kernel_log import RawKernelLogResult, KernelLog

from microwave2.utils.utils import Arch
import platform
import os
from datetime import datetime
# from dotenv import load_dotenv

GIT_USER = "denzel-farmer"
# Load environment variables from .env file
# load_dotenv()
# Get token from environment variables
GIT_TOKEN = os.environ.get("GIT_TOKEN")
if not GIT_TOKEN:
    raise ValueError("GIT_TOKEN not found in environment variables")
print("GIT_TOKEN loaded successfully")
GIT_URL = "github.com"

BENCHMARK_REPO_REL_DIR = "KernelSecurityBenchmark/kernsecbench/benchmarks"
BENCHMARK_ABS_DIR = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "benchmarks")
RAW_LOG_DIR = os.path.join(os.path.dirname(
    os.path.abspath(__file__)), "kernel-logs")

TEST_BUILD_MODULE = "build_benchmarks.py"
LAUNCH_SCRIPT = "launch.sh"

TEST_ORG = "denzel-farmer"
TEST_REPO = "KernelSecurityBenchmarks"
TEST_BRANCH = "main"

LINUX_TARGET_NAME = "linux"
LINUX_TARGET_ORG = "torvalds"
LINUX_TARGET_TAG = "v6.8"


def build_tester(test_name: str,
                 kconfig: Kconfig = None,
                 target_name: str = LINUX_TARGET_NAME,
                 target_repo_name: str = LINUX_TARGET_NAME,
                 target_org: str = LINUX_TARGET_ORG,
                 target_tag: str = LINUX_TARGET_TAG,
                 target_branch: str = "main",
                 exec_arch: Arch = Arch.X86,
                 worker_arch: Arch = Arch.X86,
                 build_function: str = None,  # Function within module to call to build
                 launch_script: str = LAUNCH_SCRIPT,  # Launch script relative to benchmarks dir
                 test_subdir: str = BENCHMARK_REPO_REL_DIR,
                 target_subdir: str = None,
                 extra_args: str = None
                 ) -> KernelTester:
    """Build tester for a linux kernel"""
    # input("Building tester for linux kernel")
    # TODO swap out for using the local repo as remote
    test_git_config = GitConfig(
        auth=GitAuthInfo(user=GIT_USER, token=GIT_TOKEN),
        base_url=GIT_URL,
        org=TEST_ORG,
        repo_name=TEST_REPO,
        branch=TEST_BRANCH
    )

    # If no build function is specified, no build module is needed
    module_name = TEST_BUILD_MODULE
    if build_function is None:
        module_name = None

    test_config = DynamicTestConfig(
        test_name=test_name,
        test_subdir=test_subdir,
        module_name=module_name,
        build_entrypoint=build_function,
        launch_script=launch_script,
        sparse_download=False,
        exec_arch=exec_arch,
        worker_arch=worker_arch,
        git_config=test_git_config
    )

    target_git_config = GitConfig(
        auth=GitAuthInfo(user=GIT_USER, token=GIT_TOKEN),
        base_url=GIT_URL,
        org=target_org,
        repo_name=target_repo_name,
        branch=target_branch,
        tag=target_tag
    )

    target_config = KernelTargetConfig(
        target_name=target_name,
        exec_arch=exec_arch,
        worker_arch=worker_arch,
        target_subdir=target_subdir,
        git_config=target_git_config,
        kconfig=kconfig
    )

    tester_config = TesterConfig(
        test_config=test_config,
        target_config=target_config,
        extra_args=extra_args
    )

    return KernelTester(tester_config)


def saved_kernel_log_dir(log_base_dir: str, kconfig: Kconfig, test_name: str) -> str:
    return os.path.join(log_base_dir, kconfig.get_label(), test_name)


def build_saved_kernel_log_path(log_base_dir: str, kconfig: str, test_name: str) -> str:
    return saved_kernel_log_dir(log_base_dir, kconfig, test_name) + "/kernel_current.json"


def run_linux_benchmark(test_name: str, kconfig: Kconfig, build_function: str, launch_script: str = LAUNCH_SCRIPT, interactive: bool = False, log_base_dir: str = RAW_LOG_DIR, extra_args: str = None) -> TestResult:
    """Run a linux kernel benchmark"""

    tester = build_tester(test_name=test_name,
                          kconfig=kconfig,
                          build_function=build_function,
                          launch_script=launch_script,
                          extra_args=extra_args)

    # TODO add support for adding a 'run label' to runs, which allows identifying runs with different configs but same target name

    result = tester.download()
    if (result.is_failure()):
        print("Failed to download components")
        print(result.message, result.error)
        return None
    result = tester.build(rebuild=False, interactive=interactive)
    if (result.is_failure()):
        print("Failed to build components")
        print(result.message, result.error)
        return None

    if interactive:
        print("Booting interactively, won't generate kernel log or autostart test")
        tester.run_interactive()
        return None

    result = tester.run()
    if (result.is_failure()):
        print("Failed to run test")
        print(result.message, result.error)
        return None

    if (log_base_dir is not None):
        kernel_logs = result.get_kernel_log()
        log_full_base = saved_kernel_log_dir(
            log_base_dir, kconfig, test_name)
        os.makedirs(log_full_base, exist_ok=True)

        # Save full kernel log to json
        json_current_path = build_saved_kernel_log_path(
            log_base_dir, kconfig, test_name)
        kernel_logs.to_JSON(json_current_path)

        # Save copy of json with date/time in name
        date_time_str = datetime.now().strftime("%d_%m_%y-%H:%M:%S")
        json_full_path = os.path.join(
            log_full_base, f"kernel_{date_time_str}.json")
        kernel_logs.to_JSON(json_full_path)

        # Dump to current path in only log readable format
        log_current_path = os.path.join(log_full_base, "kernel_current.log")
        kernel_logs.dump_log(log_current_path)

    return result
