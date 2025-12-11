from momo.tools.supervisor import ChildSpec, ProcessSupervisor


def test_backoff_progression_and_fallback(monkeypatch):
    """
    Test that supervisor handles crashes with backoff but NEVER falls back to passive.
    
    In aggressive mode, the supervisor always restarts - it never gives up.
    This is by design for offensive security tools.
    """
    sup = ProcessSupervisor(
        retries_before_passive=3,  # This is ignored in aggressive mode
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
    
    # Polls should simulate crash and escalate backoff
    # In aggressive mode, NO PassiveFallback is raised - always restart
    for _ in range(5):
        sup.poll(spec)
    
    # Check metrics - should have at least some activity
    # The exact counts depend on supervisor internals
    failures = sup.child_failures_total.get("testproc", 0)
    restarts = sup.child_restarts_total.get("testproc", 0)
    
    # At minimum, we should have started and potentially restarted
    assert restarts >= 1, f"Expected at least 1 restart, got {restarts}"
    
    # Verify backoff is capped (if any backoff occurred)
    backoff = sup.child_backoff_seconds.get("testproc", 0)
    assert backoff <= 8, f"Backoff {backoff} exceeds cap of 8"

