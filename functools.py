"""
functools.py - Functional tools for PythonExtra
"""

try:
    from collections import namedtuple
except ImportError:
    # Fallback if collections not available
    def namedtuple(typename, field_names):
        if isinstance(field_names, str):
            field_names = field_names.replace(',', ' ').split()

        def __new__(cls, *args):
            return tuple.__new__(cls, args)

        def __repr__(self):
            return f"{typename}({', '.join(f'{k}={v}' for k, v in zip(field_names, self))})"

        dct = {'__new__': __new__, '__repr__': __repr__, '__slots__': ()}
        for i, name in enumerate(field_names):
            dct[name] = property(lambda self, i=i: self[i])

        return type(typename, (tuple,), dct)

def reduce(function, iterable, initializer=None):
    it = iter(iterable)
    if initializer is None:
        try:
            value = next(it)
        except StopIteration:
            raise TypeError("reduce() of empty sequence with no initial value")
    else:
        value = initializer
    for element in it:
        value = function(value, element)
    return value

class partial:
    def __init__(self, func, *args, **keywords):
        self.func = func
        self.args = args
        self.keywords = keywords

    def __call__(self, *args, **keywords):
        new_keywords = self.keywords.copy()
        new_keywords.update(keywords)
        return self.func(*self.args, *args, **new_keywords)

WRAPPER_ASSIGNMENTS = ('__module__', '__name__', '__qualname__', '__doc__',
                       '__annotations__')
WRAPPER_UPDATES = ('__dict__',)

def update_wrapper(wrapper,
                   wrapped,
                   assigned=WRAPPER_ASSIGNMENTS,
                   updated=WRAPPER_UPDATES):
    for attr in assigned:
        try:
            value = getattr(wrapped, attr)
        except AttributeError:
            pass
        else:
            setattr(wrapper, attr, value)
    for attr in updated:
        try:
            getattr(wrapper, attr).update(getattr(wrapped, attr, {}))
        except AttributeError:
            pass
    wrapper.__wrapped__ = wrapped
    return wrapper

def wraps(wrapped,
          assigned=WRAPPER_ASSIGNMENTS,
          updated=WRAPPER_UPDATES):
    return partial(update_wrapper, wrapped=wrapped,
                   assigned=assigned, updated=updated)

def cmp_to_key(mycmp):
    """Convert a cmp= function into a key= function."""
    class K(object):
        __slots__ = ['obj']
        def __init__(self, obj):
            self.obj = obj
        def __lt__(self, other):
            return mycmp(self.obj, other.obj) < 0
        def __gt__(self, other):
            return mycmp(self.obj, other.obj) > 0
        def __eq__(self, other):
            return mycmp(self.obj, other.obj) == 0
        def __le__(self, other):
            return mycmp(self.obj, other.obj) <= 0
        def __ge__(self, other):
            return mycmp(self.obj, other.obj) >= 0
        def __ne__(self, other):
            return mycmp(self.obj, other.obj) != 0
        __hash__ = None
    return K

def total_ordering(cls):
    """Class decorator that fills in missing ordering methods"""
    convert = {
        '__lt__': [('__gt__', lambda self, other: not (self < other or self == other)),
                   ('__le__', lambda self, other: self < other or self == other),
                   ('__ge__', lambda self, other: not self < other)],
        '__le__': [('__ge__', lambda self, other: not self <= other or self == other),
                   ('__lt__', lambda self, other: self <= other and not self == other),
                   ('__gt__', lambda self, other: not self <= other)],
        '__gt__': [('__lt__', lambda self, other: not (self > other or self == other)),
                   ('__ge__', lambda self, other: self > other or self == other),
                   ('__le__', lambda self, other: not self > other)],
        '__ge__': [('__le__', lambda self, other: not self >= other or self == other),
                   ('__gt__', lambda self, other: self >= other and not self == other),
                   ('__lt__', lambda self, other: not self >= other)]
    }

    roots = set()
    for op in convert:
        op_func = getattr(cls, op, None)
        # Check if it exists AND is not object's default implementation
        if op_func is not None and op_func is not getattr(object, op, None):
             roots.add(op)

    if not roots:
         raise ValueError('must define at least one ordering operation: < > <= >=')

    root = max(roots)       # prefer __lt__ to __le__ to __gt__ to __ge__

    for opname, opfunc in convert[root]:
        # Only if missing OR is object's default implementation
        if getattr(cls, opname, None) is getattr(object, opname, None):
            opfunc.__name__ = opname
            setattr(cls, opname, opfunc)

    return cls

_sentinel = object()
_CacheInfo = namedtuple("CacheInfo", ["hits", "misses", "maxsize", "currsize"])

def lru_cache(maxsize=128, typed=False):
    if callable(maxsize):
        user_function, maxsize = maxsize, 128
        return _lru_cache_wrapper(user_function, maxsize, typed)

    def decorator(user_function):
        return _lru_cache_wrapper(user_function, maxsize, typed)
    return decorator

def _lru_cache_wrapper(user_function, maxsize, typed):
    cache = {}
    hits = 0
    misses = 0

    def wrapper(*args, **kwds):
        nonlocal hits, misses
        key = args
        if kwds:
            key += (_sentinel,)
            for item in sorted(kwds.items()):
                key += item
        if typed:
            key += tuple(type(v) for v in args)
            if kwds:
                key += tuple(type(v) for v in kwds.values())

        # Check if key is in cache.
        if key in cache:
            # Move to end (most recently used)
            val = cache.pop(key)
            cache[key] = val
            hits += 1
            return val

        result = user_function(*args, **kwds)
        cache[key] = result
        misses += 1

        if maxsize is not None and len(cache) > maxsize:
            # Remove first item (least recently used)
            # In MicroPython/Python 3.7+, dict iterates in insertion order.
            # So next(iter(cache)) gives the oldest inserted key.
            del cache[next(iter(cache))]

        return result

    def cache_info():
        return _CacheInfo(hits, misses, maxsize, len(cache))

    def cache_clear():
        nonlocal hits, misses
        cache.clear()
        hits = 0
        misses = 0

    wrapper.cache_info = cache_info
    wrapper.cache_clear = cache_clear
    return wrapper
