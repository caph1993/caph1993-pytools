import sys
import importlib
from types import ModuleType

# https://stackoverflow.com/q/42870428


def deep_reload(m: ModuleType):
    name = m.__name__  # get the name that is used in sys.modules
    name_ext = name + '.'  # support finding sub modules or packages
    del m

    def compare(loaded: str):
        return (loaded == name) or loaded.startswith(name_ext)

    all_mods = tuple(
        sys.modules)  # prevent changing iterable while iterating over it
    sub_mods = filter(compare, all_mods)
    for pkg in sub_mods:
        del sys.modules[
            pkg]  # remove sub modules and packages from import cache
    return importlib.import_module(name)