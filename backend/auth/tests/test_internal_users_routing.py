from __future__ import annotations

import auth.api.routes.internal_users as internal_users_route


def test_summary_route_is_registered_before_dynamic_id_route() -> None:
    paths = [route.path for route in internal_users_route.router.routes if hasattr(route, "path")]

    assert "/internal/users/summary" in paths
    assert "/internal/users/{id}" in paths
    assert paths.index("/internal/users/summary") < paths.index("/internal/users/{id}")

