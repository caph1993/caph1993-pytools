import functools
import weakref
from typing import Any, Callable, Protocol, Type, TypeVar, Union, cast
'''
Typing this library correctly is impossible right now.

The main issue is that we can not create types for callable objects with a partial signature, like "Callable[[SELF, ...], OUT]" for a normal method.

https://github.com/python/mypy/issues/5876

I decided to leave it partially implemented (for future inspiration) using
Union[Callable[[SELF], OUT], Callable[..., OUT]] 
'''

SELF = TypeVar("SELF", contravariant=True)
OUT = TypeVar("OUT", covariant=True)


class _NormalMethod_fixed_signature(Protocol[SELF, OUT]):
    __name__: str

    def __call__(_self, self: SELF, *args, **kwargs) -> OUT:
        ...


class _NormalMethod_any_signature(Protocol[SELF, OUT]):
    __name__: str
    __call__: Callable


_NormalMethod = Union[_NormalMethod_fixed_signature,
                      _NormalMethod_any_signature,]

_ClassMethod = _NormalMethod_any_signature
_StaticMethod = _NormalMethod_any_signature


class _Property(Protocol[SELF, OUT]):

    def __get__(self, instance: SELF, _) -> OUT:
        ...


class cached_property(property, _Property[SELF, OUT]):
    '''decorator for converting a method into a cached property'''

    # https://stackoverflow.com/a/4037979/3671939

    def __init__(self, method: Callable[[SELF], OUT]):
        self._method = method

    def __get__(self, instance: SELF, _) -> OUT:
        value = self._method(instance)
        setattr(instance, self._method.__name__, value)
        return value


def set_method(cls):
    '''decorator for adding or replacing a method of a given class'''

    def decorator(method: _NormalMethod[SELF, Any]):
        assert hasattr(method, '__call__'), f'Not callable method: {method}'
        name: str = method.__name__  # type:ignore
        setattr(cls, name, method)

    return decorator


def cached_method(maxsize=128, typed=False):
    '''decorator for converting a method into an lru cached method'''

    # https://stackoverflow.com/a/33672499/3671939
    def decorator(func: _NormalMethod[SELF, OUT]) -> _NormalMethod[SELF, OUT]:

        @functools.wraps(func)
        def wrapped_func(self: SELF, *args, **kwargs):
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

    def decorator(method: _NormalMethod[SELF, OUT]):
        f = cast(
            _NormalMethod[SELF, OUT],
            cached_method(maxsize, typed)(method),
        )
        return set_method(cls)(f)

    return decorator


def set_classmethod(cls):
    '''decorator for adding or replacing a classmethod of a given class'''

    def decorator(method: _ClassMethod[SELF, OUT]):
        f = cast(_NormalMethod[SELF, OUT], classmethod(method))
        return set_method(cls)(f)

    return decorator


def set_staticmethod(cls):
    '''decorator for adding or replacing a staticmethod of a given class'''

    def decorator(method: _StaticMethod[SELF, OUT][SELF, Any]):
        f = cast(_NormalMethod[SELF, OUT], staticmethod(method))
        return set_method(cls)(f)

    return decorator


def set_property(cls: Type[SELF]):
    '''decorator for adding or replacing a property of a given class'''

    def decorator(method: Callable[[SELF], OUT]):
        f = cast(_NormalMethod[SELF, OUT], property(method))
        return set_method(cls)(f)

    return decorator


def set_cached_property(cls: Type[SELF]):
    '''decorator for adding or replacing a cached_property of a given class'''

    def decorator(method: Callable[[SELF], OUT]):
        f = cast(_NormalMethod[SELF, OUT], cached_property(method))
        return set_method(cls)(f)

    return decorator


set_cachedproperty = set_cached_property  # Previous versions

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