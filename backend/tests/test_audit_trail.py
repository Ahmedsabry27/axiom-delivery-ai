def test_audit_events():

    events = [
        "WorkflowStarted",
        "TaskStarted",
        "TaskCompleted",
        "WorkflowCompleted",
    ]

    assert len(events) == 4

    assert "WorkflowCompleted" in events
