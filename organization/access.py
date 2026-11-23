from django.db.models import Q
from django.contrib.auth import get_user_model

from .models import UserScope


def is_primary_admin(user):
    return user.is_authenticated and (user.is_superuser or getattr(user, "role", None) == "admin")


def is_it_manager(user):
    return user.is_authenticated and getattr(user, "role", None) == "it_manager"


def it_units_for(actor):
    """Return active support units the actor may route issues to."""
    from .models import Unit

    units = Unit.objects.filter(is_active=True)
    if is_primary_admin(actor):
        return units
    if not is_it_manager(actor):
        return units.none()

    actor_scope = Q(pk__in=[])
    for department_id, unit_id in actor.scopes.values_list("department_id", "unit_id"):
        if unit_id:
            actor_scope |= Q(pk=unit_id)
        else:
            actor_scope |= Q(department_id=department_id)
    return units.filter(actor_scope).distinct()


def it_assignees_for(actor, device=None, unit=None):
    """Return active IT managers the actor may assign within a team or device scope."""
    User = get_user_model()
    candidates = User.objects.filter(is_active=True, role="it_manager")
    if not is_primary_admin(actor) and not is_it_manager(actor):
        return candidates.none()

    if is_it_manager(actor):
        actor_scope = Q(pk__in=[])
        for department_id, unit_id in actor.scopes.values_list("department_id", "unit_id"):
            if unit_id:
                actor_scope |= Q(scopes__department_id=department_id, scopes__unit_id=unit_id)
                actor_scope |= Q(scopes__department_id=department_id, scopes__unit__isnull=True)
            else:
                actor_scope |= Q(scopes__department_id=department_id)
        candidates = candidates.filter(actor_scope)

    if unit is not None:
        candidates = candidates.filter(
            scopes__department_id=unit.department_id,
        ).filter(Q(scopes__unit_id=unit.pk) | Q(scopes__unit__isnull=True))
    elif device is not None:
        device_scope = Q(scopes__department_id=device.department_id)
        if device.unit_id:
            device_scope &= Q(scopes__unit_id=device.unit_id) | Q(scopes__unit__isnull=True)
        else:
            device_scope &= Q(scopes__unit__isnull=True)
        candidates = candidates.filter(device_scope)

    return candidates.distinct().order_by("username")


def visible_issues_for(user):
    """Return issues visible to a reporter, scoped IT worker, or primary admin."""
    from support.models import Issue

    if is_primary_admin(user):
        return Issue.objects.all()
    if is_it_manager(user):
        team_ids = it_units_for(user).values("pk")
        return Issue.objects.filter(
            Q(assigned_unit_id__in=team_ids)
            | Q(assigned_to_id=user.pk)
            | Q(assigned_unit__isnull=True, device__in=scoped_devices(user))
        ).distinct()
    if getattr(user, "role", None) == "unit_user":
        eligible_units = user.scopes.filter(unit__isnull=False).values("unit_id")
        return Issue.objects.filter(
            Q(reported_by=user)
            | Q(participants__user=user, device__unit_id__in=eligible_units)
        ).distinct()
    return Issue.objects.none()


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
