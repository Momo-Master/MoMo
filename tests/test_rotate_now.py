
from momo.apps.momo_core.main import ServiceState


def test_rotate_event_signal_sets_flag():
    state = ServiceState()
    assert not state.rotate_event.is_set()
    state.rotate_event.set()
    assert state.rotate_event.is_set()


