# общий класс для ошибок программы
class StreamStatsError(Exception):
    pass


class UnsupportedFormatError(StreamStatsError):
    pass


class InvalidEventError(StreamStatsError):
    def __init__(self, message, filename="<stream>", line=1):
        # запоминаем, где ошибка
        self.filename = filename
        self.line = line
        self.reason = message
        super().__init__(f"{filename}: строка {line}: {message}")


class InvalidTimestampError(InvalidEventError):
    pass


class CLIConfigurationError(StreamStatsError):
    pass
