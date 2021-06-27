import functools
import weakref


def cached_method(maxsize=128, typed=False):
  '''decorator for converting a method into an lru cached method'''

  # https://stackoverflow.com/a/33672499/3671939
  def decorator(func):

    @functools.wraps(func)
    def wrapped_func(self, *args, **kwargs):
      # We're storing the wrapped method inside the instance. If we had
      # a strong reference to self the instance would never die.
      self_weak = weakref.ref(self)

      @functools.wraps(func)
      @functools.lru_cache(maxsize=maxsize, typed=typed)
      def _cached_method(*args, **kwargs):
        return func(self_weak(), *args, **kwargs)

      setattr(self, func.__name__, _cached_method)
      return _cached_method(*args, **kwargs)

    return wrapped_func

  return decorator


class cached_property(object):
  '''decorator for converting a method into a cached property'''

  # https://stackoverflow.com/a/4037979/3671939

  def __init__(self, method):
    self._method = method

  def __get__(self, instance, _):
    value = self._method(instance)
    setattr(instance, self._method.__name__, value)
    return value


def set_method(cls):
  '''decorator for adding or replacing a method of a given class'''

  def decorator(method):
    assert hasattr(method, '__call__'), f'Not callable method: {method}'
    setattr(cls, method.__name__, method)

  return decorator


def set_cached_method(cls, maxsize=128, typed=False):
  '''decorator for adding or replacing a cached_method of a given class'''
  return lambda method: set_method(cls)(cached_method(maxsize, typed)(method))


def set_classmethod(cls):
  '''decorator for adding or replacing a classmethod of a given class'''
  return lambda method: set_method(cls)(classmethod(method))


def set_staticmethod(cls):
  '''decorator for adding or replacing a staticmethod of a given class'''
  return lambda method: set_method(cls)(staticmethod(method))


def set_property(cls):
  '''decorator for adding or replacing a property of a given class'''
  return lambda method: set_method(cls)(property(method))


def set_cachedproperty(cls):
  '''decorator for adding or replacing a cached_property of a given class'''
  return lambda method: set_method(cls)(cached_property(method))
