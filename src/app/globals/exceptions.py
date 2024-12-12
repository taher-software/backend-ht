from .error import Error


class ApiException(Exception):
    """The base ApiException model"""

    def __init__(self, status_code: int, error: Error):
        super().__init__(status_code)
        self.status_code = status_code
        self.error = error
