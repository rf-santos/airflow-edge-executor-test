"""
RBAC bootstrap for local Airflow UI segregation by team.

Creates two team roles and demo users, where each user is assigned BOTH:
    - the built-in "Viewer" role (for baseline UI read access)
    - a team-specific role that ADDS edit privileges for that team's DAGs

Demo users created:
    - team_a_user: Viewer + Team A DAG edit rights (team_a_*)
    - team_b_user: Viewer + Team B DAG edit rights (team_b_*)

Behavioral intent:
    - Each team user can interact with their team's DAGs (trigger, clear, delete runs, etc.).
    - Each team user can view the other team's DAGs but cannot modify them.
    - Baseline UI (non-admin) viewing is provided by the Viewer role; Admin stays unchanged.

Implementation notes:
    - We add DAG-level permissions on resources named DAG:<dag_id> using Airflow's RBAC.
    - Team roles grant actions: can_read, can_edit on their own DAGs; can_read on others.
    - We discover DAGs at runtime via DagBag and apply by prefix (team_a_*, team_b_*).
    - Safe to re-run; operations are idempotent.

Usage:
    AIRFLOW_HOME=. airflow "shell < scripts/setup_rbac.py"
    or simply run inside a configured container: python scripts/setup_rbac.py

Note: In production, manage users/roles centrally (e.g., SSO, external IdP).
"""

from __future__ import annotations
from airflow.www.fab_security.manager import AUTH_DB
from airflow.www.app import create_app
from airflow.models.dagbag import DagBag
from airflow.security import permissions as perms
from typing import Any, cast
import os


TEAM_PREFIX = {
    "team_a": "team_a_",
    "team_b": "team_b_",
}

# Consolidated roles for each team with operator-level permissions
TEAM_A_USER_ROLE = "team_a_user"
TEAM_B_USER_ROLE = "team_b_user"


def _ensure_role(sm, role_name):
    role = sm.find_role(role_name)
    if not role:
        role = sm.add_role(role_name)
    return role


def _copy_base_perms(sm, target_role, base_role_name="Viewer"):
    """
    Deprecated in this setup: we no longer copy Viewer permissions into team roles.
    We keep this function (no-op) for backward compatibility if imported elsewhere.
    """
    return


def _ensure_action_and_resource(sm, action, resource):
    """
    Ensure a Permission for (action, resource) exists and return it.

    Airflow 2.10's FAB security manager override exposes:
      - get_permission(action_name, resource_name)
      - create_permission(action_name, resource_name)
    but not add_action/add_resource, so we rely on create_permission to
    implicitly provision missing pieces.
    """
    perm = None
    if hasattr(sm, "get_permission"):
        perm = sm.get_permission(action, resource)
    if not perm and hasattr(sm, "create_permission"):
        perm = sm.create_permission(action, resource)
    if not perm:
        raise RuntimeError(
            f"Unable to ensure permission for action={action!r}, resource={resource!r}"
        )
    return perm


def _grant_dag_perms(sm, role_name, dag_id, actions):
    role = sm.find_role(role_name)
    if not role:
        return
    resource = perms.resource_name_for_dag(dag_id)
    for action in actions:
        perm = _ensure_action_and_resource(sm, action, resource)
        if perm not in role.permissions:
            sm.add_permission_to_role(role, perm)


def ensure_roles_and_users(app):
    sm = app.appbuilder.sm

    # Cleanup: remove any team-specific roles/users not in the consolidated set
    desired_roles = {TEAM_A_USER_ROLE, TEAM_B_USER_ROLE}
    desired_users = {"team_a_user", "team_b_user"}
    try:
        # Establish optional DB session (best-effort)
        session: Any = None
        if hasattr(sm, "get_session"):
            raw = sm.get_session() if callable(sm.get_session) else sm.get_session  # type: ignore[operator]
            session = cast(Any, raw)

        # Roles
        roles = []
        if hasattr(sm, "get_all_roles"):
            roles = sm.get_all_roles()  # type: ignore[attr-defined]
        elif hasattr(sm, "rolemodel") and session is not None:
            roles = session.query(sm.rolemodel).all()  # type: ignore[attr-defined]
        for r in roles or []:
            name = getattr(r, "name", None)
            if name and name.startswith("team_") and name not in desired_roles:
                if hasattr(sm, "del_role"):
                    sm.del_role(name)  # type: ignore[attr-defined]
                elif session is not None:
                    session.delete(r)

        # Users
        users = []
        if hasattr(sm, "get_all_users"):
            users = sm.get_all_users()  # type: ignore[attr-defined]
        elif hasattr(sm, "user_model") and session is not None:
            users = session.query(sm.user_model).all()  # type: ignore[attr-defined]
        for u in users or []:
            username = getattr(u, "username", None)
            if (
                username
                and username.startswith("team_")
                and username not in desired_users
            ):
                if hasattr(sm, "del_user"):
                    sm.del_user(u)  # type: ignore[attr-defined]
                elif session is not None:
                    session.delete(u)
        if session is not None:
            session.commit()
    except Exception:
        # Best-effort cleanup only
        pass

    # Create team roles (no longer copy Viewer perms; users will be assigned Viewer directly)
    role_names = [TEAM_A_USER_ROLE, TEAM_B_USER_ROLE]
    for rn in role_names:
        _ensure_role(sm, rn)

    # Ensure team roles can create Dag Runs (required by API/UI trigger)
    DAG_RUNS_RESOURCE = "DAG Runs"
    CREATE_ACTION = perms.ACTION_CAN_CREATE
    perm = _ensure_action_and_resource(sm, CREATE_ACTION, DAG_RUNS_RESOURCE)
    for rn in role_names:
        role = sm.find_role(rn)
        if role and perm not in role.permissions:
            sm.add_permission_to_role(role, perm)

    # Discover DAGs and grant DAG-level permissions by team prefix
    dagbag = DagBag(read_dags_from_db=False, include_examples=False)
    dag_ids = sorted(dagbag.dags.keys())

    for dag_id in dag_ids:
        if dag_id.startswith(TEAM_PREFIX["team_a"]):
            # Team A DAGs: grant consolidated Team A user full control (read+edit)
            _grant_dag_perms(
                sm,
                TEAM_A_USER_ROLE,
                dag_id,
                actions=[perms.ACTION_CAN_READ, perms.ACTION_CAN_EDIT],
            )
            # Allow Team B to view only
            _grant_dag_perms(
                sm, TEAM_B_USER_ROLE, dag_id, actions=[perms.ACTION_CAN_READ]
            )
        elif dag_id.startswith(TEAM_PREFIX["team_b"]):
            # Team B DAGs
            _grant_dag_perms(
                sm,
                TEAM_B_USER_ROLE,
                dag_id,
                actions=[perms.ACTION_CAN_READ, perms.ACTION_CAN_EDIT],
            )
            # Allow Team A to view only
            _grant_dag_perms(
                sm, TEAM_A_USER_ROLE, dag_id, actions=[perms.ACTION_CAN_READ]
            )
        else:
            # Non-team DAGs: just ensure both teams can read
            for rn in role_names:
                _grant_dag_perms(sm, rn, dag_id, actions=[perms.ACTION_CAN_READ])

    # Create/Update demo users (AUTH_DB only). Skip if using SSO.
    if app.config.get("AUTH_TYPE") == AUTH_DB:
        # Allow env overrides and forced resets for local testing convenience
        default_pw = os.getenv("RBAC_DEMO_DEFAULT_PASSWORD", "test")
        team_a_pw = os.getenv("TEAM_A_USER_PASSWORD", default_pw)
        team_b_pw = os.getenv("TEAM_B_USER_PASSWORD", default_pw)
        force_reset = os.getenv("RBAC_DEMO_FORCE_RESET", "false").lower() in {
            "1",
            "true",
            "yes",
        }

        demo_users = [
            (
                "team_a_user",
                "team_a_user@example.com",
                TEAM_A_USER_ROLE,
                "Team A User",
                team_a_pw,
            ),
            (
                "team_b_user",
                "team_b_user@example.com",
                TEAM_B_USER_ROLE,
                "Team B User",
                team_b_pw,
            ),
        ]

        viewer_role = sm.find_role("Viewer")

        def _sync_user_roles(user_obj, desired_role_objs):
            """Ensure user has Viewer + team role (and preserves Admin if already present) via direct assignment.

            Avoids relying on add_role/remove_role helpers that may not exist in the overridden
            security manager. Performs minimal diffs and commits the session if available.
            """
            if not user_obj:
                return
            current_roles = list(getattr(user_obj, "roles", []))
            current_names = {getattr(r, "name", None) for r in current_roles}
            desired = [r for r in desired_role_objs if r]
            # Preserve Admin if currently present
            admin_roles = [
                r for r in current_roles if getattr(r, "name", None) == "Admin"
            ]
            # Build final desired list preserving ordering: Admin (if any) + desired unique roles
            final_roles = []
            seen = set()
            for r in admin_roles + desired:
                name = getattr(r, "name", None)
                if name and name not in seen:
                    final_roles.append(r)
                    seen.add(name)
            final_names = {getattr(r, "name", None) for r in final_roles}
            if final_names != current_names:
                try:
                    user_obj.roles = final_roles  # type: ignore[assignment]
                except Exception:
                    pass

        for username, email, role_name, fullname, password in demo_users:
            user = sm.find_user(username=username)
            team_role = sm.find_role(role_name)
            if not user:
                # Create with the team role initially (FAB API takes a single role on creation)
                sm.add_user(
                    username=username,
                    first_name=fullname.split()[0],
                    last_name=fullname.split()[-1],
                    email=email,
                    role=team_role,
                    password=password,
                )
                # Reload to update roles to include Viewer as well (if it exists)
                user = sm.find_user(username=username)

            # Ensure role assignment includes Viewer + team role (Admin preserved automatically)
            desired_role_objs = [r for r in (viewer_role, team_role) if r]
            _sync_user_roles(user, desired_role_objs)

            # Optionally reset password if requested
            if force_reset:
                sm.update_user(user, password=password)


def main():
    app = create_app()
    # Type ignore: Airflow's Flask app context manager is valid at runtime
    with app.app_context():  # type: ignore[attr-defined]
        ensure_roles_and_users(app)
        print("RBAC bootstrap complete.")


if __name__ == "__main__":
    main()
