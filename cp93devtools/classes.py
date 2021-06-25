import functools
import weakref


def dynamic_class(cls):
  '''
  Class decorator that enables setting methods interactively for developing in jupyter:
  
  obj = MyClass()
  
  @MyClass.set_method
  def hello(self, *args):
  return print('hello', *args)
  
  obj.hello('world')
  
  '''

  class Setters:

    @classmethod
    def set_method(cls, method):
      assert hasattr(method, '__call__'), f'Not callable method: {method}'
      setattr(cls, method.__name__, method)

    @classmethod
    def set_classmethod(cls, method):
      assert hasattr(method, '__call__'), f'Not callable method: {method}'
      setattr(cls, method.__name__, classmethod(method))

    @classmethod
    def set_staticmethod(cls, method):
      assert hasattr(method, '__call__'), f'Not callable method: {method}'
      setattr(cls, method.__name__, staticmethod(method))

    @classmethod
    def set_property(cls, method):
      assert hasattr(method, '__call__'), f'Not callable method: {method}'
      setattr(cls, method.__name__, property(method))

    @classmethod
    def set_cachedproperty(cls, method):
      assert hasattr(method, '__call__'), f'Not callable method: {method}'
      setattr(cls, method.__name__, cached_property(method))

    @classmethod
    def _set_cachedmethod(cls, maxsize, method):
      assert hasattr(method, '__call__'), f'Not callable method: {method}'
      setattr(cls, method.__name__, cached_method(maxsize)(method))

    @classmethod
    def set_cachedmethod(cls, maxisze_or_method):
      if hasattr(maxisze_or_method, '__call__'):
        maxsize = None
        method = maxisze_or_method
      else:
        maxsize = maxisze_or_method
        method = None
      assert isinstance(maxsize, int) or maxsize is None
      if method is None:
        return lambda method: cls._set_cachedmethod(maxsize, method)
      else:
        return cls._set_cachedmethod(maxsize, method)

  cls.set_method = Setters.set_method
  cls.set_classmethod = Setters.set_classmethod
  cls.set_staticmethod = Setters.set_staticmethod
  cls.set_property = Setters.set_property
  cls.set_cachedproperty = Setters.set_cachedproperty
  cls.set_cachedmethod = Setters.set_cachedmethod
  return cls


class cached_property(object):  # https://stackoverflow.com/a/4037979/3671939

  def __init__(self, method):
    self._method = method

  def __get__(self, instance, _):
    value = self._method(instance)
    setattr(instance, self._method.__name__, value)
    return value


def cached_method(maxsize):  # https://stackoverflow.com/a/33672499/3671939

  def decorator(func):

    @functools.wraps(func)
    def wrapped_func(self, *args, **kwargs):
      # We're storing the wrapped method inside the instance. If we had
      # a strong reference to self the instance would never die.
      self_weak = weakref.ref(self)

      @functools.wraps(func)
      @functools.lru_cache(maxsize=maxsize)
      def _cached_method(*args, **kwargs):
        return func(self_weak(), *args, **kwargs)

      setattr(self, func.__name__, _cached_method)
      return _cached_method(*args, **kwargs)

    return wrapped_func

  return decorator