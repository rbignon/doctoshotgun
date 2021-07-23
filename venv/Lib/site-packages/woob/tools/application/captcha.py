# -*- coding: utf-8 -*-

from __future__ import print_function

from threading import Lock, Event

from woob.capabilities.captcha import CapCaptchaSolver
from woob.core import Woob

__all__ = ['CaptchaMixin']


class CaptchaMixin(object):
    def __init__(self, *args, **kwargs):
        super(CaptchaMixin, self).__init__(*args, **kwargs)
        self.captcha_woob = Woob()
        self.captcha_woob.load_backends(caps=[CapCaptchaSolver])

    def solve_captcha(self, job, backend):
        def call_solver(solver_backend, job):
            with lock:
                if solved.is_set():
                    solver_backend.logger.info('already solved, ignoring')
                    return

                ret = solver_backend.solve_catpcha_blocking(job)
                if ret:
                    solver_backend.logger.info('backend solved job')
                    backend.config['captcha_response'].set(ret.solution)
                    solved.set()

        def all_solvers_finished():
            if not solved.is_set():
                print('Error(%s): CAPTCHA could not be solved.' % backend.name, file=self.stderr)
            else:
                print('Info(%s): CAPTCHA was successfully solved. Please retry operation.' % backend.name, file=self.stderr)

        lock = Lock()
        solved = Event()

        bres = self.captcha_woob.do(call_solver, job)
        bres.callback_thread(None, None, all_solvers_finished)
