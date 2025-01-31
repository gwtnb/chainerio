import os
from struct import pack, unpack, calcsize
import threading
import tempfile
import warnings

from chainerio import cache
import pickle

DEFAULT_CACHE_PATH = os.path.join(
    os.getenv('HOME'), ".chainer", "chainerio", "cache")


class LockContext:
    def __init__(self, locked_lock):
        self.locked_lock = locked_lock

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.locked_lock.unlock()


class RWLock:
    '''Reader-writer lock

    TODO(kuenishi): Add unit tests

    '''

    def __init__(self):
        self.cv = threading.Condition()
        self.writer = None
        self.reader = set()

    def rdlock(self):
        with self.cv:
            self.cv.wait_for(lambda: self.writer is None)
            self.reader.add(threading.get_ident())
            return LockContext(self)

    def wrlock(self):
        with self.cv:
            thread_id = threading.get_ident()
            self.cv.wait_for(lambda: self.writer is None and
                             self.writer != thread_id and
                             len(self.reader) == 0)
            self.writer = thread_id
            return LockContext(self)

    def unlock(self):
        with self.cv:
            thread_id = threading.get_ident()
            if self.writer == thread_id:
                self.writer = None
            else:
                self.reader.remove(thread_id)
            self.cv.notify_all()


class DummyLock:
    '''Dummy class for multithread-unsafe fast cache class
    '''

    def __init__(self):
        pass

    def rdlock(self):
        return LockContext(self)

    def wrlock(self):
        return LockContext(self)

    def unlock(self):
        pass


class FileCache(cache.Cache):
    '''Stores cache data in local filesystem

    Stores cache data in local filesystem,
    ``~/.chainer/chainerio/cache`` by default. Cache data is
    automatically deleted after the object is collected. If the
    process quit (typically by SIGTERM) the cache remains after the
    death of process.

    TODO(kuenishi): retain cache file in case of correct process
    termination and reuse for future process re-invocation.

    '''

    def __init__(self, length, multithread_safe=False, do_pickle=False,
                 dir=DEFAULT_CACHE_PATH, verbose=False):
        self._multithread_safe = multithread_safe
        self.length = length
        self.do_pickle = do_pickle
        assert self.length > 0

        if self.multithread_safe:
            self.lock = RWLock()
        else:
            self.lock = DummyLock()

        self.pos = 0
        self.dir = dir
        assert self.dir is not None
        os.makedirs(self.dir, exist_ok=True)

        self.closed = False
        self.indexfp = tempfile.NamedTemporaryFile(delete=True, dir=self.dir)
        self.indexfile = self.indexfp.name
        self.datafp = tempfile.NamedTemporaryFile(delete=True, dir=self.dir)
        self.datafile = self.datafp.name

        # allocate space to store 2n 64bit unsigned integers
        # 16 bytes * n chunks
        # Size must be smaller than max value of signed long long
        buf = pack('Qq', 0, -1)
        self.buflen = calcsize('Qq')
        assert self.buflen == 16
        for i in range(self.length):
            offset = self.buflen * i
            r = os.pwrite(self.indexfp.fileno(), buf, offset)
            assert r == self.buflen
        self.verbose = verbose
        if self.verbose:
            print('created index file:', self.indexfile)
            print('created data file:', self.datafile)

    def __len__(self):
        return self.length

    @property
    def multiprocess_safe(self):
        return False

    @property
    def multithread_safe(self):
        return self._multithread_safe

    def get(self, i):
        if self.closed:
            return
        data = self._get(i)
        if self.do_pickle and data:
            data = pickle.loads(data)
        return data

    def _get(self, i):
        assert i >= 0 and i < self.length
        offset = self.buflen * i
        with self.lock.rdlock():
            buf = os.pread(self.indexfp.fileno(), self.buflen, offset)
            (o, l) = unpack('Qq', buf)
            if l < 0 or o < 0:
                return None

            data = os.pread(self.datafp.fileno(), l, o)
            assert len(data) == l
            return data

    def put(self, i, data):
        try:
            if self.do_pickle:
                data = pickle.dumps(data)
            return self._put(i, data)

        except OSError as ose:
            # Disk full (ENOSPC) possibly by cache; just warn and keep running
            if ose.errno == 28:
                warnings.warn(ose.strerror, RuntimeWarning)
                return False
            else:
                raise ose

    def _put(self, i, data):
        if self.closed:
            return
        assert i >= 0 and i < self.length
        offset = self.buflen * i

        with self.lock.wrlock():
            buf = os.pread(self.indexfp.fileno(), self.buflen, offset)
            (o, l) = unpack('Qq', buf)
            if l >= 0 and o >= 0:
                # Already data exists
                return False

            pos = self.pos

            '''Notes on possibility of partial write

            write(3) says partial writes ret<nbyte may happen in
            case nbytes>PIPE_BUF. In Linux 5.0 PIPE_BUF is
            4096 so partial writes do not happen when writing
            index, but they may happen when writing data. We
            hope it is rare, it seems to happen mostly in case
            of multiple writer processes, disk full and
            ``EINTR``.

            CPython does care this case by retrying
            ``pwrite(2)`` as long as it returns ``-1`` . But
            returns when the return value is positive. We'd
            better care that case.

            '''
            buf = pack('Qq', pos, len(data))
            r = os.pwrite(self.indexfp.fileno(), buf, offset)
            assert r == self.buflen

            current_pos = pos
            while current_pos - pos < len(data):
                r = os.pwrite(self.datafp.fileno(),
                              data[current_pos-pos:], current_pos)
                assert r > 0
                current_pos += r
            assert current_pos - pos == len(data)

            self.pos += len(data)
            return True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        with self.lock.wrlock():
            if not self.closed:
                self.closed = True
                self.indexfp.close()
                self.datafp.close()
                self.indexfp = None
                self.datafp = None
