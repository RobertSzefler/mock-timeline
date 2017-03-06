""" Proof of concept implementation of cross-mock call ordering checks.
"""
# This code has been tested to work with python 2.7.13, 3.5.3 and 3.6.0

# TODO interprocess call clock
# TODO track call wall clock
# TODO thread safety (global_call_clock)
# TODO? get rid of the on-the fly _Call instrumentation code in favor of
# monkey patching _Call upfront?
# TODO review assert_executed_* exception formatting (format_with_parent etc)

from contextlib import contextmanager

try:  # pragma: no cover
    # We need to bypass mock.__init__'s notorious namespace cloaking.
    import mock.mock as mock
except ImportError:  # pragma: no cover
    import unittest.mock as mock

import six


global_call_clock = 0


class MockTimelineAssertionError(AssertionError):
    pass


def format_with_parent(self):
    # TODO handle other cases as implemented in mock._Call.__repr__
    if len(self) == 2:
        args, kwargs = self
    else:
        _, args, kwargs = self
    return mock._format_call_signature(self._parent_mock, args, kwargs)


def assert_executed_after(self, other):
    if CallEvent(self) < CallEvent(other):
        raise MockTimelineAssertionError('%s executed before %s' % (
            self.format_with_parent(), other.format_with_parent()
        ))


def assert_executed_before(self, other):
    if CallEvent(self) > CallEvent(other):
        # TODO format callee object!
        raise MockTimelineAssertionError('%s executed before %s' % (
            self.format_with_parent(), other.format_with_parent()
        ))


class TimelineTrackingMock(mock.Mock):
    def __call__(_mock_self, *args, **kwargs):
        _mock_self._mock_check_sig(*args, **kwargs)
        return_value = _mock_self._mock_call(*args, **kwargs)
        _mock_self.__track_call_time()
        return return_value

    def __track_call_time(self):
        # TODO lock global_call_clock
        global global_call_clock
        global_call_clock += 1
        self.last_call_global_clock = global_call_clock
        call_1 = self.call_args_list[-1]
        call_2 = self.mock_calls[-1]
        self.__instrument_call(call_1)
        self.__instrument_call(call_2)

    def __instrument_call(self, call):
        call.global_clock = global_call_clock
        call._parent_mock = self
        call.format_with_parent = six.create_bound_method(
            format_with_parent, call
        )
        call.assert_executed_after = six.create_bound_method(
            assert_executed_after, call
        )
        call.assert_executed_before = six.create_bound_method(
            assert_executed_before, call
        )

    def get_call(self, *args, **kwargs):
        # Loosely modelled after mock.NonCallableMock.assert_any_call
        self.assert_any_call(*args, **kwargs)
        expected = self._call_matcher((args, kwargs))
        actual = [
            self._call_matcher(c) for c in self.call_args_list if c == expected
        ]
        # assert_any_call() above assures that there is at least one matching
        # call.
        if len(actual) > 1:
            # TODO support the Exception case (six.raise_from etc)
            expected_string = self._format_mock_call_signature(args, kwargs)
            raise MockTimelineAssertionError(
                '%s executed more than once' % expected_string
            )

        return actual[0]


def assert_call_order(calls):
    # TODO the prev/next tracking code is far from elegant.
    call_iter = iter(calls)
    try:
        prev_call = next(call_iter)
    except StopIteration:
        return
    while True:
        try:
            next_call = next(call_iter)
        except StopIteration:
            break
        next_call.assert_executed_after(prev_call)
        prev_call = next_call


def monkey_patch_mock():
    # Transplant everything from TimelineTrackingMock onto the Mock from the
    # unittest/mock library.
    # TODO thread safety
    if getattr(mock, '_is_patched_by_mock_timeline', False):
        return
    for name, value in vars(TimelineTrackingMock).items():
        if name in ['__module__', '__doc__']:
            continue
        setattr(mock.Mock, name, value)
    mock._is_patched_by_mock_timeline = True


def monkey_unpatch_mock():
    if not getattr(mock, '_is_patched_by_mock_timeline', False):
        raise RuntimeError(
            'monkey_unpatch_mock called and mock has not been patched before'
        )
    # TODO
    del mock._is_patched_by_mock_timeline


@contextmanager
def patched_mock():
    monkey_patch_mock()
    try:
        yield
    finally:
        monkey_unpatch_mock()


class CallEvent(object):
    def __init__(self, call):
        self.call = call

    def __lt__(self, other):
        return self.call.global_clock < other.call.global_clock

    def __gt__(self, other):
        return self.call.global_clock > other.call.global_clock

    def __eq__(self, other):
        # XXX is this really needed?
        return self == other
