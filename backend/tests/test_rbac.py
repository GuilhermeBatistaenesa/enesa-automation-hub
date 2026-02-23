from app.core.rbac import (
    PERMISSION_ADMIN_MANAGE,
    PERMISSION_ARTIFACT_DOWNLOAD,
    PERMISSION_ROBOT_PUBLISH,
    PERMISSION_ROBOT_READ,
    PERMISSION_ROBOT_RUN,
    PERMISSION_RUN_CANCEL,
    PERMISSION_RUN_READ,
    PERMISSION_SERVICE_MANAGE,
    PERMISSION_SERVICE_READ,
    PERMISSION_SERVICE_RUN,
    PERMISSION_WORKER_MANAGE,
    Role,
    permissions_for_role,
)
from app.services.identity_service import Principal, _role_from_groups, settings


def test_role_permission_matrix() -> None:
    admin_permissions = permissions_for_role(Role.ADMIN)
    assert PERMISSION_ADMIN_MANAGE in admin_permissions
    assert PERMISSION_ROBOT_PUBLISH in admin_permissions
    assert PERMISSION_SERVICE_MANAGE in admin_permissions
    assert PERMISSION_WORKER_MANAGE in admin_permissions

    maintainer_permissions = permissions_for_role(Role.MAINTAINER)
    assert PERMISSION_ROBOT_PUBLISH in maintainer_permissions
    assert PERMISSION_ADMIN_MANAGE not in maintainer_permissions
    assert PERMISSION_SERVICE_RUN in maintainer_permissions
    assert PERMISSION_RUN_CANCEL in maintainer_permissions

    operator_permissions = permissions_for_role(Role.OPERATOR)
    assert PERMISSION_ROBOT_RUN in operator_permissions
    assert PERMISSION_ADMIN_MANAGE not in operator_permissions
    assert PERMISSION_SERVICE_RUN in operator_permissions
    assert PERMISSION_RUN_CANCEL in operator_permissions

    viewer_permissions = permissions_for_role(Role.VIEWER)
    assert PERMISSION_ROBOT_READ in viewer_permissions
    assert PERMISSION_RUN_READ in viewer_permissions
    assert PERMISSION_ARTIFACT_DOWNLOAD in viewer_permissions
    assert PERMISSION_SERVICE_READ in viewer_permissions


def test_principal_is_admin() -> None:
    principal = Principal(
        subject="abc",
        auth_source="local",
        role=Role.ADMIN,
        permissions=set(),
    )
    assert principal.is_admin is True


def test_group_mapping_to_role() -> None:
    original_admin = settings.azure_ad_group_admin_ids
    original_operator = settings.azure_ad_group_operator_ids
    original_viewer = settings.azure_ad_group_viewer_ids
    try:
        settings.azure_ad_group_admin_ids = "g-admin"
        settings.azure_ad_group_operator_ids = "g-operator"
        settings.azure_ad_group_viewer_ids = "g-viewer"

        assert _role_from_groups({"g-admin"}) == Role.ADMIN
        assert _role_from_groups({"g-operator"}) == Role.OPERATOR
        assert _role_from_groups({"g-viewer"}) == Role.VIEWER
    finally:
        settings.azure_ad_group_admin_ids = original_admin
        settings.azure_ad_group_operator_ids = original_operator
        settings.azure_ad_group_viewer_ids = original_viewer
