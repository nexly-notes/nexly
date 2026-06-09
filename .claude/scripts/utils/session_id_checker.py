from lib.store import StateStore


def session_id_matches(session_id: str) -> tuple[bool, str]:
    # Identity comes from the hook; check that a row already exists for it.
    state_store = StateStore(session_id)
    if state_store.load_by_session_id(session_id) is None:
        return False, "Session ID does not match state session ID"
    return True, "Session ID matches state session ID"
