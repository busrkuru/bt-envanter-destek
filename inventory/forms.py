from django import forms
from django.contrib.auth import get_user_model

from support.models import Issue
from organization.access import it_assignees_for, it_units_for, is_it_manager, is_primary_admin
from organization.models import Unit

User = get_user_model()


class IssueCreateForm(forms.ModelForm):
    class Meta:
        model = Issue
        fields = ("device", "title", "description", "priority")
        labels = {
            "device": "Cihaz",
            "title": "Konu",
            "description": "Sorunu açıklayın",
            "priority": "Öncelik",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, devices, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["device"].queryset = devices


class IssueManagementForm(forms.Form):
    assigned_unit = forms.ModelChoiceField(
        label="Yönlendirilen ekip",
        queryset=Unit.objects.none(),
        required=False,
        empty_label="Ekip seçin",
    )
    assigned_to = forms.ModelChoiceField(
        label="Atanan IT sorumlusu",
        queryset=User.objects.none(),
        required=False,
        empty_label="Ekip kuyruğunda bırak",
    )
    priority = forms.ChoiceField(label="Öncelik", choices=Issue.Priority.choices)

    def __init__(self, *args, actor, device, **kwargs):
        super().__init__(*args, **kwargs)
        allowed_units = it_units_for(actor)
        self.fields["assigned_unit"].queryset = allowed_units

        if self.is_bound:
            selected_unit_id = self.data.get(self.add_prefix("assigned_unit"), "")
            selected_unit = allowed_units.filter(pk=selected_unit_id).first() if selected_unit_id else None
            self.fields["assigned_to"].queryset = (
                it_assignees_for(actor, unit=selected_unit)
                if selected_unit
                else User.objects.none()
            )
        else:
            selected_unit_id = (
                self.initial.get("assigned_unit")
                if "assigned_unit" in self.initial
                else device.unit_id
            )
            selected_unit = allowed_units.filter(pk=selected_unit_id).first() if selected_unit_id else None
            if selected_unit_id:
                self.initial.setdefault("assigned_unit", selected_unit_id)
            self.fields["assigned_to"].queryset = (
                it_assignees_for(actor, unit=selected_unit)
                if selected_unit
                else it_assignees_for(actor, device=device)
            )

        self.fields["assigned_unit"].help_text = (
            "Önce ekibi seç. Liste, seçilen ekibin aktif IT sorumlularını gösterecek."
            if is_primary_admin(actor)
            else "Yalnızca kendi yetki kapsamındaki ekiplere yönlendirebilirsin."
        )
        self.fields["assigned_to"].help_text = (
            "Kişi seçmezsen kayıt ekibin ortak kuyruğunda kalır."
        )
        if is_primary_admin(actor):
            self.fields["assigned_unit"].help_text += " Farklı birimden gelen arızayı ilgili destek ekibine aktarabilirsin."


class AssignmentTransferForm(forms.Form):
    user = forms.ModelChoiceField(
        label="Yeni kullanıcı",
        queryset=User.objects.none(),
        empty_label="Kullanıcı seçin",
    )
    notes = forms.CharField(
        label="Devir notu",
        required=False,
        max_length=250,
        widget=forms.TextInput(attrs={"placeholder": "Örn. Kullanıcı değişikliği"}),
    )

    def __init__(self, *args, device, actor, current_assignment=None, **kwargs):
        super().__init__(*args, **kwargs)
        candidates = User.objects.filter(is_active=True, role="unit_user")
        if is_it_manager(actor):
            allowed = Q(pk__in=[])
            for department_id, unit_id in actor.scopes.values_list("department_id", "unit_id"):
                if unit_id:
                    allowed |= Q(scopes__department_id=department_id, scopes__unit_id=unit_id)
                    allowed |= Q(scopes__department_id=department_id, scopes__unit__isnull=True)
                else:
                    allowed |= Q(scopes__department_id=department_id)
            candidates = candidates.filter(allowed).distinct()

        allowed_for_device = Q(scopes__department_id=device.department_id)
        if device.unit_id:
            allowed_for_device &= Q(scopes__unit_id=device.unit_id) | Q(scopes__unit__isnull=True)
        else:
            allowed_for_device &= Q(scopes__unit__isnull=True)
        candidates = candidates.filter(allowed_for_device).distinct().order_by("username")
        if current_assignment:
            candidates = candidates.exclude(pk=current_assignment.user_id)
        self.fields["user"].queryset = candidates
