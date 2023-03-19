# Scoped

The Python library to run code at function exit.

<a id="contents"></a>
## Contents

- [Background](#background)
- [Overview](#overview)
- [Installation](#installation)
- [API Reference](#api-reference)

<a id="background"></a>
## Motivation and background

[Go to the top](#contents)

This library is inspired by the common and natural C++ idiom called 
[Resource Acquisition Is Initialization (RAII)](https://en.cppreference.com/w/cpp/language/raii),
which supposes that the lifetime of an object is equal to its visibility in the scope.

It is a composite idiom, relying on several core language properties, such as 
strict object scoping rules, order of initialization, stack unwinding etc. 
In Python, however, scoping rules for objects are not that strict. For instance, 
the following code is totally valid, as conditional blocks and other controlling 
structures do not introduce new scopes:

```python
def foo():
    if True:
        x = 10

    print(x)
```

Unlike C++, when local objects go out of scope in Python, they are
not guaranteed to be removed immediately or in the order of creation. Instead, the object lifetime
in Python is managed by its built-in [Garbage Collector](https://docs.python.org/3/library/gc.html#module-gc),
which relies on reference counting mechanism.
There is the [`__del__`](](https://docs.python.org/3/reference/datamodel.html#object.__del__))
magic method, which can be used to display this behavior:

```python
class MyObj:
    def __init__(self, name, ref=None):
        self.name = name
        self.ref = ref

    def __del__(self):
        print("deleted", self.name)

def foo():
    obj1 = MyObj("1")
    obj2 = MyObj("2", obj1)
    obj3 = MyObj("3", obj2)
    obj1.ref = obj2 # add a non-trivial reference cycle

foo()
print("after return")
```

The sample above produces the following output (`Python 3.10.6`, standard package on Ubuntu):

```
deleted 3
after return
deleted 1
deleted 2
```

meaning only the 3rd object was removed at function exit, while objects
1 and 2 were removed at the interpreter exit. The garbage collector is capable
of detecting simple reference cycles, but the time and order of object removal is
not specified. Additionally, garbage collection can be turned off.

To allow scope-dependent object lifetime, Python offers
[Context managers](https://docs.python.org/3/library/contextlib.html), the `with` statement,
and the built-in `contextlib` library. There is also the
[`ExitStack`](https://docs.python.org/3/library/contextlib.html#contextlib.ExitStack)
utility that allows to write simpler code and control stack "unwinding".

```python
from contextlib import ExitStack, closing

class MyObj:
    def __init__(self, name, ref=None):
        self.name = name
        self.ref = ref

    def close(self):
        print("deleted", self.name)

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

def foo():
    with ExitStack() as es:
        obj1 = MyObj("1")
        # register an exit function
        es.callback(obj1.close)

        obj2 = MyObj("2", obj1)
        # register an exit context manager
        es.enter_context(closing(obj2))

        # acquire resource and register exit cm
        obj3 = es.enter_context(MyObj("3", obj2))

        obj1.ref = obj2 # add a non-trivial reference cycle
    print("after es")

foo()
print("after return")
```

Now, the example produces the desired output:

```
deleted 3
deleted 2
deleted 1
after es
after return
```

This approach follows Python design principles and idioms, such as
"Explicit is better than implicit". It allows both invasive and non-invasive uses
with `ContextManager` protocol and `ExitStack.callback()`. In practice, however,
the use of such constructs is often intermixed with try-except blocks,
which may reduce readability of the code (mostly because of the extra indentation levels added).
With some classes, almost every function needs to begin with exit stack initialization.
It often happens when there are some cleanup or rollback procedures supposed
to be executed on an error:

```python
import os
import os.path
import shutil
from contextlib import ExitStack


class SomeClass:
    ...

    def foo(self, dst_dir):
        dir_existed = os.path.isdir(dst_dir)
        if not dir_existed:
            os.makedirs(dst_dir)

        try:
            with open("bar.txt", "w") as input_file:
                self._write_file_contents(input_file)
        except Exception as exc:
            if not dir_existed:
                shutil.rmtree(dst_dir)
```

If there are multiple resources to control in a single function, the code becomes a mess.
This code can be made a little bit more readable and maintainable with `ExitStack` -
now we don't need to remember the original resource states, but we need to cleanup the stack
on success:

```python
class SomeClass:
    ...

    def foo_with_es(self, dst_dir):
        with ExitStack() as es:
            if not os.path.isdir(dst_dir):
                os.makedirs(dst_dir)
                es.callback(shutil.rmtree, dst_dir)

            with open("bar.txt", "w") as input_file:
                self._write_file_contents(input_file)

            es.pop_all()
```

This library tries to go a step further and improve this situation a little bit more:

```python
from scoped import scoped, on_error_do

class SomeClass:
    ...

    @scoped
    def foo_scoped(self, dst_dir):
        if not os.path.isdir(dst_dir):
            os.makedirs(dst_dir)
            on_error_do(shutil.rmtree, dst_dir)

        with open("bar.txt", "w") as input_file:
            self._write_file_contents(input_file)
```

<a id="overview"></a>
## Overview

[Go to the top](#contents)

The main interface of the library is the `@scoped` function decorator. It allows to use
helper functions such as `scope_add()`, `on_error_do()` and `on_exit_do()` inside the
function to define resource-managing variables and set up actions performed on error
and on exit.
- The `scope_add()` function provides a readable way to declare variables,
that implement the `ContextManager` protocol.
- The `on_error_do()` and `on_exit_do()` functions provide a way to add custom callbacks
(including lambdas) to the list of the actions performed on error and on the function exit

Example:

```python
import os
import os.path
import shutil
from scoped import scoped, on_error_do, scope_add

@scoped
def write_directory(dst_dir):
    """
    Creates a directory, if needed, and writes data inside.
    Cleans everything extra in the case of error.
    """

    if not os.path.isdir(dst_dir):
        os.makedirs(dst_dir)
        on_error_do(shutil.rmtree, dst_dir)

    db_connection = scope_add(open_db_conn())

    on_exit_do(extra_cleanup)

    with open("bar.txt", "w") as input_file:
        _write_file_contents(input_file, db_connection)

    # Calls on the normal exit:
    #
    # extra_cleanup()
    # open_db_conn().__enter__().__exit__()
    #
    #
    # Calls on an error:
    #
    # extra_cleanup()
    # open_db_conn().__enter__().__exit__()
    # shutil.rmtree(dst_dir)
```

<a id="installation"></a>
## Installation

```python
pip install scoped-functions
```

If you want to install from the repository:
```python
pip install "git+https://github.com/zhiltsov-max/scoped"
```

<a id="api-reference"></a>
## API Reference

[Go to the top](#contents)

- `@scoped(arg_name: str = None)`

    A function decorator that allows to register context managers and exit callbacks
    with `scope_add()`, `on_error_do()` and `on_exit_do()` inside the decorated function.

    Can be used 2 ways:

    - Implicit:

    ```python
    @scoped
    def foo():
        ...
    ```

    - Explicit: adds an additional kw-parameter with specified name to the function calls.
    This can be useful if you want to be more explicit and if you want to use extra
    functionality.

    ```python
    @scoped(arg_name='scope')
    def foo(*, scope: Scope):
        scope.add(...)
    ```

    > Note that this decorator will not work with generators, because they implemented
    > differently from normal functions. Please use the "traditional" approach with `Scope`
    > or `ExitStack` instead in these cases:

    ```python
    @scoped
    def generator():
        on_exit_do(print, "finished")
        yield

    next(gen()) # error: no Scope object

    def generator2():
        with Scope() as scope:
            scope.on_exit_do(print, "finished")
            yield

    next(gen()) # ok
    ```

- `scope_add(cm: ContextManager[T]) -> T`

    Enters the context manager and adds it to the exit stack. If called
    multiple times, exit callbacks will be called on exit in the reversed order.

    Returns: cm.__enter__() result

- `on_error_do(callback, *args, ignore_errors: bool = False, kwargs=None) -> None`

    Registers a function to be called on scope exit because of an error. The primary use
    is for error rollback functions. If called multiple times, callbacks will be called
    on exit in the reversed order.

    If `ignore_errors` is `True`, the errors from this function call will be ignored.
    Allows to pass function args with the `*args` and `kwargs` parameters.

    ```python
    def bar(*args, **kwargs):
        ...

    @scoped
    def foo(x):
        on_error_do(bar, x, ignore_errors=True, kwargs={'y': 42})

        # bar(x, y=42) will be called prior to foo() exit on error
        raise Exception("error")
    ```

- `on_exit_do(callback, *args, ignore_errors: bool = False, kwargs=None) -> None`

    Registers a function to be called on scope exit. The callback is called unconditionally,
    equivalently to the `finally` block in the `try-except` clause. If called
    multiple times, callbacks will be called on exit in the reversed order.

    ```python
    def bar(*args, **kwargs):
        ...

    def baz():
        ...

    @scoped
    def foo(x, y):
        on_error_do(bar, x)
        on_exit_do(bar, y)

        baz()

        # Called on an error:
        #
        # bar(y)
        # bar(x)
        #
        #
        # Called on the normal exit:
        #
        # bar(y)
    ```