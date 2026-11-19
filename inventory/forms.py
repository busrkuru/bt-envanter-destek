from django import forms
from django.contrib.auth import get_user_model

from support.models import Issue
from organization.access import it_assignees_for, is_it_manager, is_primary_admin

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
    priority = forms.ChoiceField(label="Öncelik", choices=Issue.Priority.choices)
    assigned_to = forms.ModelChoiceField(
        label="Atanan IT sorumlusu",
        queryset=User.objects.none(),
        required=False,
        empty_label="Atama yok",
    )

    def __init__(self, *args, actor, device, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = it_assignees_for(actor, device)
        if is_primary_admin(actor):
            self.fields["assigned_to"].help_text = (
                "Tüm birimlerdeki aktif IT sorumlularına atama yapabilirsin."
            )
        else:
            self.fields["assigned_to"].help_text = (
                "Yalnızca bu cihazın birim kapsamındaki aktif IT sorumluları listelenir."
            )


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
