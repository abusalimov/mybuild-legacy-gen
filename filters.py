from _compat import *

import os.path
try:
    import collections.abc as collections_abc
except ImportError:
    import collections as collections_abc

from jinja2 import Undefined, is_undefined
from jinja2.exceptions import UndefinedError
from jinja2.filters import environmentfilter, make_attrgetter


__all__ = [
    'patsubst',
    'getattrs',
    'filterattrs',
    'file_path',
    'module_path',
    'mk_list',
    'mk_var',
]


def _split_pat_rep(*pat_rep):
    if not pat_rep:
        return '%', '%'
    elif len(pat_rep) == 1:
        return '%', pat_rep[0]
    elif len(pat_rep) == 2:
        return pat_rep
    else:
        raise TypeError("too many arguments to 'patsubst'")

def patsubst(value, *pat_rep):
    pat, rep = _split_pat_rep(*pat_rep)

    if not isinstance(pat, string_types):
        pats = list(pat)
    else:
        pats = [pat]
    if isinstance(rep, collections_abc.Mapping):
        reps = dict(rep)
    else:
        reps = dict.fromkeys(pats, rep)

    def create_matcher(pat):
        pat_start, pat_percent, pat_end = pat.partition('%')
        if pat_percent:
            def match(s):
                if s.startswith(pat_start) and s.endswith(pat_end):
                    return pat, s[len(pat_start):len(s)-len(pat_end)]
        else:
            def match(s):
                if s == pat:
                    return pat, s
        return match
    matchers = [create_matcher(pat) for pat in pats or ['%']]

    def create_replacer(rep):
        rep_start, rep_percent, rep_end = rep.partition('%')
        if rep_percent:
            def replace(stem):
                return rep_start + stem + rep_end
        else:
            def replace(stem):
                return rep
        return replace
    replacers = {pat: create_replacer(rep) for pat, rep in reps.items()}

    for s in value:
        for match in matchers:
            m = match(s)
            if m is not None:
                pat, stem = m
                yield replacers[pat](stem)
                break


def _iter_item_attr_pairs(env, items, attr, default=Undefined(name='default')):
    getter = make_attrgetter(env, attr)
    for item in items:
        try:
            ret = getter(item)
        except UndefinedError:
            ret = default
        if is_undefined(ret):
            ret = default
        if not is_undefined(ret):
            yield item, ret

@environmentfilter
def getattrs(env, items, attr, default=Undefined(name='default')):
    for item, ret in _iter_item_attr_pairs(env, items, attr, default):
        yield ret

@environmentfilter
def filterattrs(env, items, attr, value, default=Undefined(name='default')):
    for item, ret in _iter_item_attr_pairs(env, items, attr, default):
        if ret == value:
            yield item


def file_path(value, *pat_rep):
    def basename(file):
        dirname, filename = os.path.split(file)
        if not pat_rep:
            filename = filename.partition('.')[0]
        return os.path.join(dirname, filename)
    return patsubst(map(basename, value), *pat_rep)

def module_path(value, *pat_rep):
    def slashname(module):
        return module._fullname.replace('.', os.path.sep)
    return patsubst(map(slashname, value), *pat_rep)


def mk_list(value, sep=' \\\n    '):
    return sep.join(value)

def mk_var(value, var_name, sep=' \\\n    '):
    return '{var_name} :={sep}{}'.format(mk_list(value, sep), **locals())

