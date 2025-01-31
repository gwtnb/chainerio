from chainerio.io import IO
from chainerio.profiler import IOProfiler

import os
from typing import Optional


class FileSystem(IO):

    def __init__(self, io_profiler: Optional[IOProfiler] = None,
                 root: str = ""):
        IO.__init__(self, io_profiler, root)

    def get_actual_path(self, path: str) -> str:
        return os.path.join(self.root, path)
