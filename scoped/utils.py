# Copyright (C) 2021-2022 Intel Corporation
# Copyright (C) 2023 Maxim Zhiltsov
#
# SPDX-License-Identifier: MIT

from functools import wraps


def optional_arg_decorator(fn):
    @wraps(fn)
    def wrapped_decorator(*args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return fn(args[0], **kwargs)

        else:

            def real_decorator(decoratee):
                return fn(decoratee, *args, **kwargs)

            return real_decorator

    return wrapped_decorator
