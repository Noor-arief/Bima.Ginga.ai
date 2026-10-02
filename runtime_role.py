from __future__ import annotations

import os


class RuntimeRoleError(RuntimeError):
    pass


def assert_runtime_role(expected: str, env_var: str = "APP_ROLE") -> str:
    actual = os.getenv(env_var, "").strip()
    expected = str(expected or "").strip()
    if not expected:
        raise ValueError("expected runtime role must not be empty")
    if not actual:
        raise RuntimeRoleError(
            f"{env_var} is required; expected {expected!r}. Refusing to start without an explicit runtime boundary."
        )
    if actual != expected:
        raise RuntimeRoleError(
            f"runtime role mismatch: expected {expected!r}, got {actual!r}. Refusing to start the wrong application in this service."
        )
    return actual
