""" Runner that can execute a Target """

class RunnerConfig:
    def __init__(self, runner_name: str):
        self.runner_name = runner_name

class Runner:
    def __init__(self, target):
        self.target = target
    
    def prepare(self):
        """Prepare the running environment for testing (build images, etc)"""
        pass

    def run(self):
        """Run the target code"""
        pass
        
