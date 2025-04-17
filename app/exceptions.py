class UnauthorizedError(Exception):
    pass

class MissingFieldsError(Exception):
    def __init__(self, fields):
        super().__init__("Missing required fields")
        self.fields = fields
