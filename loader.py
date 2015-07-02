from _compat import *

import re
import sys
import os.path
import timeit
import types
from glob import glob
from importlib import import_module

from mylang_legacy import runtime
from mylang_legacy.parse import my_parse

from nsloader import pyfile

from nsimporter.hook import NamespaceFinder
from nsimporter.hook import NamespaceRouterImportHook
from nsimporter.package import PreloadPackageLoader
from nsimporter.package import AutoloadPackageModule

import logging
logger = logging.getLogger(__name__)


NAMESPACE_PATH = {
    'embox':       ['src'],
    'third_party': ['third-party'],
    'platform':    ['platform'],
}


class LegacyMyFileLoader(pyfile.PyFileLoader):
    """Loads My-files using myfile parser/linker."""

    @property
    def defaults(self):
        return dict(((ns, import_module(ns)) for ns in NAMESPACE_PATH),
                    __builtins__=runtime.builtins)

    def _exec_module(self, module):
        source_string = self.get_source(self.name)
        res = my_parse(source_string, self.path, module.__dict__)


class LegacyPackageModule(AutoloadPackageModule):
    """Provides few workarounds to get legacy my-files imported."""

    def __getattr__(self, name):
        return super(LegacyPackageModule, self).__getattr__(name)

    def __setattr__(self, name, value):
        if isinstance(value, types.ModuleType):
            try:
                old_value = getattr(self, name)
            except AttributeError:
                pass
            else:
                if not isinstance(old_value, types.ModuleType):
                    try:
                        module = sys.modules[old_value.__module__]
                        extra_fmt = " defined in '{module.__file__}'"
                    except (AttributeError, KeyError):
                        extra_fmt = ''
                    fmt = ("Package '{self.__name__}.{name}' is shadowed "
                           "by a '{old_value.__class__.__name__}' "
                           "object '{old_value}'" + extra_fmt)
                    logger.warn(fmt.format(**locals()))
                    return
        super(LegacyPackageModule, self).__setattr__(name, value)


namespace_router = NamespaceRouterImportHook()
sys.meta_path.insert(0, namespace_router)

default_loader_details = [
    (LegacyMyFileLoader, ['.my'], {'Mybuild': ['Mybuild']}),
]
default_preload_modules = ['Mybuild', 'Pybuild']


def register_namespace(namespace, path=['.'],
                       loader_details=default_loader_details,
                       preload_modules=default_preload_modules):
    """Registers a new namespace recognized by a namespace importer.

    Args:
        namespace (str): namespace root name.
        path (list): a list of strings (or a string of space-separated
            entries) denoting directories to search when loading files.
        loader_details: See NamespaceFinder constructor.
        preload_modules: List of submodule names to import by default.
    """

    if '.' in namespace:
        raise NotImplementedError('To keep things simple')

    if namespace in sys.modules:
        for name in list(sys.modules):
            if namespace == name or name.startswith(namespace+'.'):
                del sys.modules[name]
    # normalize path
    path = [os.path.normpath(path_entry) for path_entry in path]

    def package_loader(fullname, path):
        return PreloadPackageLoader(fullname, path,
                                    module_type=LegacyPackageModule,
                                    preload_modules=preload_modules)
    finder = NamespaceFinder(namespace, path, loader_details, package_loader)
    namespace_router.namespace_map[namespace] = finder

    logger.info("Registered namespace '%s': %r", namespace, path)

def unregister_namespace(namespace):
    """Unregisters and returns a previously registered namespace (if any)."""
    return namespace_router.namespace_map.pop(namespace, None)


def init_namespaces(namespace_path=NAMESPACE_PATH):
    for ns, path in NAMESPACE_PATH.items():
        register_namespace(ns, path=path)

    register_namespace('genconfig', path=['conf'],
                       loader_details=[(LegacyMyFileLoader, ['.config'], {})])

def load_all_modules():
    def find_files_in(dirpath, myext='.my', myname='Mybuild'):
        for d, _, _ in os.walk(dirpath):
            for filepath in glob(os.path.join(d, '*'+myext)):
                yield os.path.splitext(filepath)[0]
            for filepath in glob(os.path.join(d, myname)):
                yield os.path.dirname(filepath)

    def to_module_name(namespace, dirpath, path):
        relpath = os.path.relpath(path, dirpath)
        return os.path.join(namespace, relpath) .replace(os.path.sep, '.')

    start_time = timeit.default_timer()

    count = 0
    for ns, finder in namespace_router.namespace_map.items():
        modules = []
        for start_dir in finder.path:
            modules.extend(to_module_name(ns, start_dir, path)
                           for path in find_files_in(start_dir))

        import_module(ns)
        for name in modules:
            if not re.match(r'^\b[\w\.]+\b$', name):
                logger.warn("Skipping '{}'".format(name))
                continue
            import_module(name)
            count += 1

    end_time = timeit.default_timer()
    elapsed = end_time - start_time

    logger.info('Loaded %d files in %#.2f seconds', count, elapsed)

def init_and_load():
    init_namespaces()
    load_all_modules()
