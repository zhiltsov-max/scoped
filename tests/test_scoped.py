# Copyright (C) 2021-2022 Intel Corporation
# Copyright (C) 2023 Maxim Zhiltsov
#
# SPDX-License-Identifier: MIT

from contextlib import suppress
from typing import Optional
from unittest import TestCase, mock

from scoped import Scope, on_error_do, on_exit_do, scoped


class TestException(Exception):
    pass


class ScopeTest(TestCase):
    def test_calls_only_exit_callback_on_exit(self):
        error_cb = mock.MagicMock()
        exit_cb = mock.MagicMock()

        with Scope() as scope:
            scope.on_error_do(error_cb)
            scope.on_exit_do(exit_cb)

        error_cb.assert_not_called()
        exit_cb.assert_called_once()

    def test_calls_both_callbacks_on_error(self):
        error_cb = mock.MagicMock()
        exit_cb = mock.MagicMock()

        with self.assertRaises(TestException), Scope() as scope:
            scope.on_error_do(error_cb)
            scope.on_exit_do(exit_cb)
            raise TestException()

        error_cb.assert_called_once()
        exit_cb.assert_called_once()

    def test_adds_cm(self):
        cm = mock.Mock()
        cm.__enter__ = mock.MagicMock(return_value=42)
        cm.__exit__ = mock.MagicMock()

        with Scope() as scope:
            retval = scope.add(cm)

        cm.__enter__.assert_called_once()
        cm.__exit__.assert_called_once()
        self.assertEqual(42, retval)

    def test_calls_cm_on_error(self):
        cm = mock.Mock()
        cm.__enter__ = mock.MagicMock()
        cm.__exit__ = mock.MagicMock()

        with suppress(TestException), Scope() as scope:
            scope.add(cm)
            raise TestException()

        cm.__enter__.assert_called_once()
        cm.__exit__.assert_called_once()

    def test_decorator_calls_on_error(self):
        cb = mock.MagicMock()

        @scoped("scope")
        def foo(*, scope: Optional[Scope] = None):
            scope.on_error_do(cb)
            raise TestException()

        with suppress(TestException):
            foo()

        cb.assert_called_once()

    def test_decorator_does_not_call_on_no_error(self):
        error_cb = mock.MagicMock()
        exit_cb = mock.MagicMock()

        @scoped("scope")
        def foo(*, scope: Optional[Scope] = None):
            scope.on_error_do(error_cb)
            scope.on_exit_do(exit_cb)

        foo()

        error_cb.assert_not_called()
        exit_cb.assert_called_once()

    def test_decorator_supports_implicit_form(self):
        error_cb = mock.MagicMock()
        exit_cb = mock.MagicMock()

        @scoped
        def foo():
            on_error_do(error_cb)
            on_exit_do(exit_cb)
            raise TestException()

        with suppress(TestException):
            foo()

        error_cb.assert_called_once()
        exit_cb.assert_called_once()

    def test_can_forward_args(self):
        cb = mock.MagicMock()

        with suppress(TestException), Scope() as scope:
            scope.on_error_do(cb, 5, ignore_errors=True, kwargs={"a2": 2})
            raise TestException()

        cb.assert_called_once_with(5, a2=2)

    def test_decorator_can_return_on_success_in_implicit_form(self):
        @scoped
        def f():
            return 42

        retval = f()

        self.assertEqual(42, retval)

    def test_decorator_can_return_on_success_in_explicit_form(self):
        @scoped("scope")
        def f(*, scope: Optional[Scope] = None):
            return 42

        retval = f()

        self.assertEqual(42, retval)
