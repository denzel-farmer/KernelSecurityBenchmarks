from microwave2.runners.runner import Runner
from microwave2.runners.kernel_log_runner import KernelLogRunner

from typing import Dict

def select_runner(type: str, runner_config: Dict) -> Runner:
    if type == "qemu":
        return KernelLogRunner(runner_config)
    else:
        raise NotImplementedError("Runner type not implemented")
    