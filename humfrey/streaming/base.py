class ModeError(Exception):
    pass

class StreamingParser(object):
    """
    Base class for streaming parsers.

    These expose the underlying stream as file-like objects, or can be
    used to parse the stream, but not both.
    """
    
    def __init__(self, stream, encoding='utf-8'):
        self._stream, self._encoding = stream, encoding
        self._mode = None

    @property
    def mode(self):
        return self._mode
    @mode.setter
    def mode(self, mode):
        if self._mode == mode:
            return
        elif self._mode is not None:
            raise ModeError()
        else:
            self._mode = mode
