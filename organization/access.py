from django.db.models import Q
from django.contrib.auth import get_user_model

from .models import UserScope


def is_primary_admin(user):
    return user.is_authenticated and (user.is_superuser or getattr(user, "role", None) == "admin")


def is_it_manager(user):
    return user.is_authenticated and getattr(user, "role", None) == "it_manager"


def it_assignees_for(actor, device=None):
    """Return active IT managers the actor may assign work to."""
    User = get_user_model()
    candidates = User.objects.filter(is_active=True, role="it_manager")
    if is_primary_admin(actor):
        return candidates.order_by("username")
    if not is_it_manager(actor):
        return candidates.none()

    actor_scope = Q(pk__in=[])
    for department_id, unit_id in actor.scopes.values_list("department_id", "unit_id"):
        if unit_id:
            actor_scope |= Q(scopes__department_id=department_id, scopes__unit_id=unit_id)
            actor_scope |= Q(scopes__department_id=department_id, scopes__unit__isnull=True)
        else:
            actor_scope |= Q(scopes__department_id=department_id)
    candidates = candidates.filter(actor_scope)

    if device is not None:
        device_scope = Q(scopes__department_id=device.department_id)
        if device.unit_id:
            device_scope &= Q(scopes__unit_id=device.unit_id) | Q(scopes__unit__isnull=True)
        else:
            device_scope &= Q(scopes__unit__isnull=True)
        candidates = candidates.filter(device_scope)

    return candidates.distinct().order_by("username")


def scope_query(user, prefix=""):
    """Build a department/unit filter for objects related to a scoped device."""
    scopes = UserScope.objects.filter(user=user).values_list("department_id", "unit_id")
    result = Q(pk__in=[])
    for department_id, unit_id in scopes:
        department_key = f"{prefix}department_id"
        unit_key = f"{prefix}unit_id"
        if unit_id:
            result |= Q(**{department_key: department_id, unit_key: unit_id})
        else:
            result |= Q(**{department_key: department_id})
    return result


def scoped_devices(user):
    from inventory.models import AssignmentHistory, Device

    devices = Device.objects.select_related("department", "unit", "device_type")
    if is_primary_admin(user):
        return devices
    if is_it_manager(user):
        return devices.filter(scope_query(user))
    if getattr(user, "role", None) == "unit_user":
        active_assignments = AssignmentHistory.objects.filter(
            user_id=user.pk, ended_at__isnull=True
        ).values("device_id")
        return devices.filter(pk__in=active_assignments)
    return devices.none()
