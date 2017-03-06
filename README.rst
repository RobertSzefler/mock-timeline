-------------
mock-timeline
-------------

:author: Robert Szefler
:version: 0.1
:date: 2015-03-06

What's this
-----------

mock-timeline implements cross-mock call order checking for Python mock/unittest.mock library.

Install
-------

::

    $ python setup.py install

Test
----

::

    $ py.test

How to use
----------

The following examples are written using python 3. For python 2, you'd need to change the mock
import, basically.

Example 1:

.. code-block:: python

    from unittest.mock import Mock
    from mock_timeline import assert_call_order, patched_mock

    with patched_mock():
        mock = Mock()
        mock.f()
        mock.g()
        mock.h()
        assert_call_order([mock.f.get_call(), mock.g.get_call()])

Example 2:

.. code-block:: python

    from unittest.mock import Mock
    from mock_timeline import patched_mock

    with patched_mock():
        mock = Mock()
        mock.x.y(42)
        mock.z([], a=1)
        mock.x.y.get_call(42).assert_executed_before(mock.z.get_call([], a=1))

TODO

Issues
------

* The code is not production ready. Currently it's a proof of concept.
* Not thread safe at all.
* Does not support interprocess event ordering.
* The implementation relies heavily on monkey-patching mock/unittest.mock's internals; I would
  not expect it to be stable after major changes in said libraries.
