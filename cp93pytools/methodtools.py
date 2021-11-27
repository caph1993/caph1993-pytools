import functools
import weakref
from typing import Any, Callable, Optional, Type, TypeVar, Union, cast
from typing_extensions import Protocol
from typing import Callable, TypeVar, Generic
'''
Typing this library correctly is impossible right now.

The main issue is that we can not create types for callable objects with a partial signature, like "Callable[[SELF, ...], OUT]" for a normal method.

https://github.com/python/mypy/issues/5876

'''

_T = TypeVar('_T')


class _NormalMethod(Protocol[_T]):
    __name__: str
    __call__: Callable[..., _T]


_ClassMethod = _NormalMethod
_StaticMethod = _NormalMethod


class _Property(Protocol[_T]):
    __get__: Callable[..., _T]


class cached_property(property, _Property[_T]):
    '''
    decorator for converting a method into a cached property
    See https://stackoverflow.com/a/4037979/3671939
    This uses a modification:
    1. inherit from property, which disables setattr(instance, name, value)
        as it raises AttributeError: Can't set attribute
    2. use instance.__dict__[name] = value to fix
    '''

    def __init__(self, method: Callable[..., _T]):
        self._method = method

    def __get__(self, instance, _) -> _T:
        name = self._method.__name__
        value = self._method(instance)
        instance.__dict__[name] = value
        return value


def set_method(cls):
    '''decorator for adding or replacing a method of a given class'''
    return _set_method(cls, None)


def _set_method(cls, proxy: Callable = None):
    '''decorator for adding or replacing a method of a given class'''

    def decorator(method: _NormalMethod):
        assert hasattr(method, '__call__'), f'Not callable method: {method}'
        name: str = method.__name__
        method = proxy(method) if proxy else method
        setattr(cls, name, method)

    return decorator


def cached_method(maxsize=128, typed=False):
    '''decorator for converting a method into an lru cached method'''

    # https://stackoverflow.com/a/33672499/3671939
    def decorator(func: _NormalMethod[_T]) -> _NormalMethod[_T]:

        @functools.wraps(func)
        def wrapped_func(self, *args, **kwargs):
            # We're storing the wrapped method inside the instance. If we had
            # a strong reference to self the instance would never die.
            weak_self = weakref.ref(self)

            @functools.wraps(func)
            @functools.lru_cache(maxsize=maxsize, typed=typed)
            def _cached_method(*args, **kwargs):
                self = weak_self()
                assert self
                return func(self, *args, **kwargs)

            setattr(self, func.__name__, _cached_method)
            return _cached_method(*args, **kwargs)

        return wrapped_func

    return decorator


def set_cached_method(cls, maxsize=128, typed=False):
    '''decorator for adding or replacing a cached_method of a given class'''
    return _set_method(cls, cached_method(maxsize, typed))


def set_classmethod(cls):
    '''decorator for adding or replacing a classmethod of a given class'''
    return _set_method(cls, classmethod)


def set_staticmethod(cls):
    '''decorator for adding or replacing a staticmethod of a given class'''
    return _set_method(cls, staticmethod)


def set_property(cls):
    '''decorator for adding or replacing a property of a given class'''
    return _set_method(cls, property)


def set_cached_property(cls):
    '''decorator for adding or replacing a cached_property of a given class'''
    return _set_method(cls, cached_property)


set_cachedproperty = set_cached_property  # Previous versions

F = TypeVar('F', bound=Callable[..., Any])


class copy_signature(Generic[F]):

    def __init__(self, target: F) -> None:
        ...

    def __call__(self, wrapped: Callable[..., Any]) -> F:
        return cast(F, wrapped)


from typing import Callable, TypeVar, Generic
import functools, types

F = TypeVar('F', bound=Callable[..., Any])


def copy_function(f: F, name: str = None) -> F:
    """Based on http://stackoverflow.com/a/6528148/190597"""
    g = types.FunctionType(
        f.__code__,
        f.__globals__,
        name=name or f.__name__,
        argdefs=f.__defaults__,
        closure=f.__closure__,
    )
    g = functools.update_wrapper(g, f)
    g.__kwdefaults__ = f.__kwdefaults__
    return cast(F, g)


class implemented_at(Generic[F]):
    '''
    Decorator that ignores the wrapped function and uses the
    parameter function instead.
    
    Useful for implementing methods in separate files.
        Docs are copied so that any editor can provide help(method).
        Types signatures are copied so that type checkers work seamlessly.
    
    For usage details see help(implemented_at.usage)
    '''

    def __init__(self, target: F) -> None:
        self.target = target

    def __call__(self, wrapped: Callable[..., Any]) -> F:
        return copy_function(self.target, wrapped.__name__)

    @staticmethod
    def usage():
        '''
        # --- main.py ---
        (from .) import other_file

        class Hello:
            @implemented_at(other_file.hello)
            def hello(self):
                ...

        # --- other_file.py ---
        from __future__ import annotations
        from typing import TYPE_CHECKING, Type
        if TYPE_CHECKING:
            from (.)main import Hello

        def hello(obj: Hello, name:str):
            'I just say "hello {name}" for some given name'
            print(f'hello {name}')

        # --- interactive console ---
        h = Hello()
        help(h.hello)
        h.hello('world')
        '''


if False:

    class Test:
        zero = 0

        @cached_property
        def prop(self):
            print('x')
            return 1 + 1

    @set_method(Test)
    def f(self: Test):
        print(self.zero)

    t = Test()
    x = t.prop