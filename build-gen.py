#!/usr/bin/env python

import sys, os.path
def _path_to(path, rel_to=os.path.dirname(__file__)):
    return os.path.join(rel_to, path)

sys.path.insert(0, _path_to('../mybuild-legacy-parser'))
sys.path.insert(0, _path_to('../mybuild-git'))


from _compat import *

from pprint import pprint

from mybuild.context import resolve
from mybuild.solver import SolveError
from mybuild.rgraph import *

import loader

import logging
logger = logging.getLogger(__name__)


def my_resolve(conf_module):
    try:
        return resolve(conf_module)
    except SolveError as e:
        e.rgraph = get_error_rgraph(e)
        for reason, depth in traverse_error_rgraph(e.rgraph):
            print_reason(e.rgraph, reason, depth)
        raise e

def print_reason(rgraph, reason, depth):
    print ('  ' * depth, reason)
    if not reason.follow:
        return

    literal = None
    if reason.literal is not None:
        literal = ~reason.literal
    else:
        literal = reason.cause_literals[0]

    assert literal in rgraph.violation_graphs

    print('---dead branch {0}---------'.format(literal))
    reason_generator = traversal(rgraph.violation_graphs[literal])
    for reason in reason_generator:
        print_reason(rgraph, reason[0], reason[1])
    print('---------dead branch {0}---'.format(literal))


def buildgen(modules):
    pass

def main():
    loader.init_and_load()
    from genconfig.mods import conf
    import embox

    @pydsl.module
    def build(self):
        self.depends.extend([
            conf,

            # Mandatory modules
            embox.arch.system,
            embox.arch.cpu,
            embox.arch.interrupt,
            embox.arch.context,
            embox.arch.mmu,
            embox.arch.syscall,
            embox.arch.usermode,
            embox.arch.smp,
            embox.kernel.Kernel,
            embox.kernel.spinlock,
            embox.lib.debug.whereami_api,
        ])

    try:
        modules = my_resolve(build)
    except SolveError:
        return

    buildgen(modules)

if __name__ == '__main__':
    import util, logging
    util.init_logging(sys.stderr, level=logging.INFO)

    main()

