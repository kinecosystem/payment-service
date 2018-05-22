class BaseError(Exception):
    http_code = 400
    code = 4000

    def __init__(self, message):
        self.message = message

    def to_dict(self):
        return {'code': self.code, 'error': self.message}


class AlreadyExistsError(BaseError):
    http_code = 409  # conflict
    code = 4091


class PaymentNotFoundError(BaseError):
    http_code = 404
    code = 4041


class ParseError(ValueError):
    pass
