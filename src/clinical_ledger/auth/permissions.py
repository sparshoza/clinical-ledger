"""What each demo role may do."""

from enum import StrEnum


class Permission(StrEnum):
    READ_CONTENT = "read_content"
    WRITE_RECORDS = "write_records"
    READ_EVENTS = "read_events"
    RUN_VERIFY = "run_verify"
    TAMPER = "tamper"
    RESET = "reset"


ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "clinician": frozenset(
        {
            Permission.READ_CONTENT,
            Permission.WRITE_RECORDS,
            Permission.READ_EVENTS,
            Permission.RESET,
        }
    ),
    "auditor": frozenset({Permission.READ_EVENTS, Permission.RUN_VERIFY, Permission.RESET}),
    "admin": frozenset(Permission),
}


def allows(role: str, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())
