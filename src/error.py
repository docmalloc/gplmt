class ExperimentSyntaxError(Exception):
    def __init__(self, message):
        self.message = message


class ExperimentExecutionError(Exception):
    def __init__(self, message):
        self.message = message


class ExperimentSetupError(Exception):
    def __init__(self, message):
        self.message = message

class StopExperimentException(Exception):
    def __init__(self, scope):
        self.scope = scope
