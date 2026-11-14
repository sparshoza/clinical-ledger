import pytest

from clinical_ledger.auth.permissions import ROLE_PERMISSIONS, Permission, allows

P = Permission
EXPECTED = {
    "clinician": {P.READ_CONTENT, P.WRITE_RECORDS, P.READ_EVENTS, P.RESET},
    "auditor": {P.READ_EVENTS, P.RUN_VERIFY, P.RESET},
    "admin": set(P),
}


@pytest.mark.parametrize("role", sorted(EXPECTED))
@pytest.mark.parametrize("permission", list(P))
def test_role_matrix(role: str, permission: Permission) -> None:
    assert allows(role, permission) is (permission in EXPECTED[role])


def test_matrix_covers_every_role() -> None:
    assert set(ROLE_PERMISSIONS) == set(EXPECTED)
    assert len(list(P)) * len(EXPECTED) == 18
