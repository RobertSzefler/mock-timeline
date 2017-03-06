from __future__ import print_function

try:  # pragma: no cover
    # We need to bypass mock.__init__'s notorious namespace cloaking.
    import mock.mock as mock
except ImportError:  # pragma: no cover
    import unittest.mock as mock

import pytest

from mock_timeline import (
    assert_call_order, CallEvent, MockTimelineAssertionError,
    monkey_patch_mock, patched_mock, TimelineTrackingMock, monkey_unpatch_mock
)


@pytest.fixture
def mocks_with_calls():
    mock_1 = TimelineTrackingMock()
    mock_2 = TimelineTrackingMock()
    mock_1(3)
    mock_2(5, x=1)
    mock_1(42)
    mock_2('a')
    mock_2([])
    mock_1(999)
    return mock_1, mock_2


@pytest.fixture
def mock_1(mocks_with_calls):
    return mocks_with_calls[0]


@pytest.fixture
def mock_2(mocks_with_calls):
    return mocks_with_calls[1]


class TestTimelineTrackingMock:
    def test_get_call_ok(self):
        a_mock = TimelineTrackingMock()
        call_list = [((1, ), {}), ((2, 3), {}), ((42, ), {'x': []})]
        for args, kwargs in call_list:
            a_mock(*args, **kwargs)
        counter = 0
        for args, kwargs in call_list:
            counter += 1
            call = a_mock.get_call(*args, **kwargs)
            assert isinstance(call, mock._Call)
            call_args, call_kwargs = call
            assert call_args == args
            assert call_kwargs == kwargs
            assert call.global_clock == counter
            assert call._parent_mock == a_mock

    def test_get_call_missing(self):
        a_mock = TimelineTrackingMock()
        a_mock(1, 2, x=3)
        a_mock(42)
        with pytest.raises(AssertionError) as exc:
            a_mock.get_call(777, x=[])
        assert exc.value.__class__ == AssertionError
        assert str(exc.value) == 'mock(777, x=[]) call not found'

    def test_get_call_ambiguous(self):
        a_mock = TimelineTrackingMock()
        a_mock(1, 2, x=3)
        a_mock(42)
        a_mock(5, y=1)
        a_mock(42)
        with pytest.raises(MockTimelineAssertionError) as exc:
            a_mock.get_call(42)
        assert str(exc.value) == 'mock(42) executed more than once'

    def test_assert_executed_before(self, mock_1, mock_2):
        call_1 = mock_1.get_call(3)
        call_2 = mock_2.get_call('a')
        call_1.assert_executed_before(call_2)

    def test_assert_executed_before_fail(self, mock_1, mock_2):
        call_1 = mock_1.get_call(3)
        call_2 = mock_2.get_call('a')
        with pytest.raises(MockTimelineAssertionError) as exc:
            call_2.assert_executed_before(call_1)
        assert str(exc.value) == "{}('a') executed before {}(3)".format(
            mock_2, mock_1
        )

    def test_assert_executed_after(self, mock_1, mock_2):
        call_1 = mock_1.get_call(999)
        call_2 = mock_2.get_call(5, x=1)
        call_1.assert_executed_after(call_2)

    def test_assert_executed_after_fail(self, mock_1, mock_2):
        call_1 = mock_1.get_call(999)
        call_2 = mock_2.get_call(5, x=1)
        with pytest.raises(MockTimelineAssertionError) as exc:
            call_2.assert_executed_after(call_1)
        assert str(exc.value) == "{}(5, x=1) executed before {}(999)".format(
            mock_2, mock_1
        )


class TestAssertCallOrder:
    def test_empty(self):
        assert_call_order([])

    def test_empty_generator(self):
        assert_call_order(xrange(0))

    @pytest.mark.parametrize('wrapper_func', [
        # TODO I don't think I like the constructs below
        # TODO make this into a single parametrized fixture with what's below
        lambda list_: list_,
        lambda list_: (item for item in list_),
    ])
    def test_with_calls(self, mock_1, mock_2, wrapper_func):
        call_1 = mock_2.get_call(5, x=1)
        call_2 = mock_1.get_call(42)
        call_3 = mock_2.get_call([])
        assert_call_order(wrapper_func([call_1, call_2, call_3]))

    @pytest.mark.parametrize('wrapper_func', [
        # TODO I don't think I like the constructs below
        lambda list_: list_,
        lambda list_: (item for item in list_),
    ])
    def test_with_calls_fail(self, mock_1, mock_2, wrapper_func):
        call_1 = mock_2.get_call(5, x=1)
        call_2 = mock_1.get_call(42)
        call_3 = mock_2.get_call([])
        with pytest.raises(MockTimelineAssertionError) as exc:
            assert_call_order(wrapper_func([call_1, call_3, call_2]))
        assert str(exc.value) == '{}(42) executed before {}([])'.format(
            call_2._parent_mock, call_3._parent_mock
        )

    def test_more_complex_ok(self):
        mock = TimelineTrackingMock()
        mock.f()
        mock.g.x()
        mock.h.y()
        assert_call_order([mock.f.get_call(), mock.h.y.get_call()])

    def test_more_complex_fail(self):
        mock = TimelineTrackingMock()
        mock.f()
        mock.g.x()
        mock.h.y()
        with pytest.raises(MockTimelineAssertionError) as exc:
            assert_call_order([mock.h.y.get_call(), mock.g.x.get_call()])
        assert str(exc.value) == '{}() executed before {}()'.format(
            mock.g.x, mock.h.y
        )


class TestMonkeyPatching:
    @pytest.yield_fixture
    def mock_cleanup(self):
        try:
            yield
        finally:
            # Clean up the global state in unittest/mock in case some tests
            # went wrong.
            try:
                del mock._is_patched_by_mock_timeline
            except AttributeError:
                pass

    @pytest.mark.usefixtures('mock_cleanup')
    def test_monkey_patch_mock(self):
        monkey_patch_mock()

    @pytest.mark.usefixtures('mock_cleanup')
    def test_monkey_patch_mock_twice(self):
        monkey_patch_mock()
        monkey_patch_mock()

    @pytest.mark.usefixtures('mock_cleanup')
    def test_monkey_unpatch_mock_twice(self):
        monkey_patch_mock()
        monkey_unpatch_mock()
        with pytest.raises(RuntimeError):
            monkey_unpatch_mock()
        # TODO

    @pytest.mark.usefixtures('mock_cleanup')
    def test_patched_mock(self):
        # TODO rethink this test, it's quite sketchy
        with patched_mock():
            m_with_instrumentation = mock.Mock()
            m_with_instrumentation()
            assert isinstance(
                m_with_instrumentation.get_call().global_clock, int
            )
        m_without_instrumentation = mock.Mock()
        assert isinstance(m_with_instrumentation.get_call(), mock.Mock)
        assert isinstance(m_without_instrumentation.get_call(), mock.Mock)


class TestCallEvent:
    def test_init(self):
        event = CallEvent(mock.sentinel.call)
        assert event.call == mock.sentinel.call


def ignoreme():
    # TODO
    monkey_patch_mock()

    m1 = mock.Mock()
    m2 = mock.Mock()
    m1('a')
    m2(1)
    call_1 = m1.get_call('a')
    call_2 = m2.get_call(1)
    print('???', call_1, call_2)
    print('???', call_1.assert_executed_before(call_2))

    monkey_unpatch_mock()

    with patched_mock():
        m1 = mock.Mock()
        m2 = mock.Mock()
        m1('a')
        m2(1)
        call_1 = m1.get_call('a')
        call_2 = m2.get_call(1)
        print('???', call_1, call_2)
        print('???', call_1.assert_executed_before(call_2))
