from momo.tools.supervisor import ChildSpec, PassiveFallback, ProcessSupervisor


def test_backoff_progression_and_fallback(monkeypatch):
    sup = ProcessSupervisor(
        retries_before_passive=3,
        backoff_initial_secs=1,
        backoff_cap_secs=8,
        jitter_frac=0.0,
        fault_injection=True,
    )
    spec = ChildSpec(name="testproc", start_cmd=["python", "-c", "print('ok')"], enabled=True)

    # Replace sleep to avoid delays
    monkeypatch.setattr("time.sleep", lambda s: None)

    # First start
    sup.start(spec)
    # Polls should simulate crash and escalate backoff, then fallback
    raised = False
    try:
        for _ in range(3):
            sup.poll(spec)
    except PassiveFallback:
        raised = True
    assert raised
    # Check metrics present
    assert sup.child_failures_total.get("testproc", 0) >= 1
    assert sup.child_restarts_total.get("testproc", 0) >= 1

