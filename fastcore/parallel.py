# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/03a_parallel.ipynb.

# %% auto 0
__all__ = ['threaded', 'startthread', 'parallelable', 'NoDaemonProcess', 'ProcessPool', 'parallel', 'add_one', 'run_procs',
           'parallel_gen']

# %% ../nbs/03a_parallel.ipynb 1
import time
from threading import Thread
from multiprocessing import pool,Process,Queue,set_start_method,get_context

from .imports import *
from .basics import *
from .foundation import *
from .meta import *
from .xtras import *
from functools import wraps

# %% ../nbs/03a_parallel.ipynb 2
try:
    if sys.platform == 'darwin' and IN_NOTEBOOK: set_start_method("fork")
except: pass

# %% ../nbs/03a_parallel.ipynb 5
def threaded(f):
    "Run `f` in a thread, and returns the thread"
    @wraps(f)
    def _f(*args, **kwargs):
        res = Thread(target=f, args=args, kwargs=kwargs)
        res.start()
        return res
    return _f

# %% ../nbs/03a_parallel.ipynb 7
def startthread(f):
    "Like `threaded`, but start thread immediately"
    threaded(f)()

# %% ../nbs/03a_parallel.ipynb 9
def parallelable(param_name, num_workers, f=None):
    f_in_main = f == None or sys.modules[f.__module__].__name__ == "__main__"
    if sys.platform == "win32" and IN_NOTEBOOK and num_workers > 0 and f_in_main:
        print("Due to IPython and Windows limitation, python multiprocessing isn't available now.")
        print(f"So `{param_name}` has to be changed to 0 to avoid getting stuck")
        return False
    return True

# %% ../nbs/03a_parallel.ipynb 10
class NoDaemonProcess(Process):
    # See https://stackoverflow.com/questions/6974695/python-process-pool-non-daemonic
    @property
    def daemon(self):
        return False
    @daemon.setter
    def daemon(self, value):
        pass

# %% ../nbs/03a_parallel.ipynb 11
@delegates()
class ProcessPool(pool.Pool):
    "Same as Python's `pool.Pool`, except not daemonic and can pass reuse_workers=False"
    def __init__(self, max_workers=defaults.cpus, context=None, reuse_workers=True, **kwargs):
        if max_workers is None: max_workers=defaults.cpus
        if context is None: context = get_context()
        class NoDaemonContext(type(context)): Process=NoDaemonProcess
        super().__init__(max_workers, context=NoDaemonContext(), maxtasksperchild=None if reuse_workers else 1)

# %% ../nbs/03a_parallel.ipynb 12
try: from fastprogress import progress_bar
except: progress_bar = None

# %% ../nbs/03a_parallel.ipynb 13
def _gen(items, pause):
    for item in items:
        time.sleep(pause)
        yield item

# %% ../nbs/03a_parallel.ipynb 14
def parallel(f, items, *args, n_workers=defaults.cpus, total=None, progress=None, pause=0,
            method=None, chunksize=1, reuse_workers=True, **kwargs):
    "Applies `func` in parallel to `items`, using `n_workers`"
    if not method and sys.platform == 'darwin': method='fork' # Is this really a good idea?
    g = partial(f, *args, **kwargs)
    if not parallelable('n_workers', n_workers, f): n_workers=0
    if n_workers==0: return L(map(g, items))
    with ProcessPool(n_workers, context=get_context(method), reuse_workers=reuse_workers) as ex:
        _items = _gen(items, pause)
        r = ex.imap(g, _items, chunksize=chunksize)
        if progress and progress_bar:
            if total is None: total = len(items)
            r = progress_bar(r, total=len(items), leave=False)
        return L(r) # Collect the items from the iterator before we leave the pool context

# %% ../nbs/03a_parallel.ipynb 15
def add_one(x, a=1):
    # this import is necessary for multiprocessing in notebook on windows
    import random
    time.sleep(random.random()/80)
    return x+a

# %% ../nbs/03a_parallel.ipynb 21
def run_procs(f, f_done, args):
    "Call `f` for each item in `args` in parallel, yielding `f_done`"
    processes = L(args).map(Process, args=arg0, target=f)
    for o in processes: o.start()
    yield from f_done()
    processes.map(Self.join())

# %% ../nbs/03a_parallel.ipynb 22
def _f_pg(obj, queue, batch, start_idx):
    for i,b in enumerate(obj(batch)): queue.put((start_idx+i,b))

def _done_pg(queue, items): return (queue.get() for _ in items)

# %% ../nbs/03a_parallel.ipynb 23
def parallel_gen(cls, items, n_workers=defaults.cpus, **kwargs):
    "Instantiate `cls` in `n_workers` procs & call each on a subset of `items` in parallel."
    if not parallelable('n_workers', n_workers): n_workers = 0
    if n_workers==0:
        yield from enumerate(list(cls(**kwargs)(items)))
        return
    batches = L(chunked(items, n_chunks=n_workers))
    idx = L(itertools.accumulate(0 + batches.map(len)))
    queue = Queue()
    if progress_bar: items = progress_bar(items, leave=False)
    f=partial(_f_pg, cls(**kwargs), queue)
    done=partial(_done_pg, queue, items)
    yield from run_procs(f, done, L(batches,idx).zip())
