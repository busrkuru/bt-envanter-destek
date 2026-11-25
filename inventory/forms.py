from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from pathlib import Path

from support.models import Issue, IssueParticipant
from organization.access import it_assignees_for, it_units_for, is_it_manager, is_primary_admin
from organization.models import Unit

User = get_user_model()


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class IssueAttachmentFilesField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            if self.required:
                raise forms.ValidationError(self.error_messages["required"], code="required")
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        if len(files) > 5:
            raise forms.ValidationError("Bir seferde en fazla 5 dosya yükleyebilirsin.")

        cleaned_files = []
        total_size = 0
        for uploaded_file in files:
            clean_file = super().clean(uploaded_file, initial)
            extension = Path(clean_file.name).suffix.lower()
            if extension not in {".jpg", ".jpeg", ".png", ".webp", ".pdf"}:
                raise forms.ValidationError("Yalnızca JPG, PNG, WEBP veya PDF dosyaları kabul edilir.")
            if clean_file.size > 10 * 1024 * 1024:
                raise forms.ValidationError(f"{clean_file.name}: dosya boyutu 10 MB sınırını aşamaz.")

            signature = clean_file.read(16)
            clean_file.seek(0)
            valid_signature = (
                (extension in {".jpg", ".jpeg"} and signature.startswith(b"\xff\xd8\xff"))
                or (extension == ".png" and signature.startswith(b"\x89PNG\r\n\x1a\n"))
                or (extension == ".webp" and signature.startswith(b"RIFF") and signature[8:12] == b"WEBP")
                or (extension == ".pdf" and signature.startswith(b"%PDF-"))
            )
            if not valid_signature:
                raise forms.ValidationError(f"{clean_file.name}: dosya uzantısı ve içeriği eşleşmiyor.")
            total_size += clean_file.size
            cleaned_files.append(clean_file)

        if total_size > 25 * 1024 * 1024:
            raise forms.ValidationError("Bir seferde yüklenen dosyaların toplamı 25 MB sınırını aşamaz.")
        return cleaned_files


class IssueCreateForm(forms.ModelForm):
    attachments = IssueAttachmentFilesField(
        label="Fotoğraf veya dosya",
        required=False,
        help_text="JPG, PNG, WEBP veya PDF. En fazla 5 dosya, dosya başına 10 MB. Mac'te ⌘ tuşunu, Windows'ta Ctrl tuşunu basılı tutarak birden fazla dosya seçebilirsin.",
        widget=MultipleFileInput(attrs={"accept": ".jpg,.jpeg,.png,.webp,.pdf", "data-multiple-file-input": "true"}),
    )

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


class IssueAttachmentForm(forms.Form):
    attachments = IssueAttachmentFilesField(
        label="Dosyalar",
        required=True,
        help_text="JPG, PNG, WEBP veya PDF. En fazla 5 dosya, dosya başına 10 MB. Mac'te ⌘ tuşunu, Windows'ta Ctrl tuşunu basılı tutarak birden fazla dosya seçebilirsin.",
        widget=MultipleFileInput(attrs={"accept": ".jpg,.jpeg,.png,.webp,.pdf", "data-multiple-file-input": "true"}),
    )

    def __init__(self, *args, allow_internal=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.allow_internal = allow_internal
        if allow_internal:
            self.fields["is_internal"] = forms.BooleanField(
                label="Yalnızca IT ekibi görsün",
                required=False,
                initial=False,
            )


class IssueInternalNoteForm(forms.Form):
    message = forms.CharField(
        label="IT iç notu",
        max_length=2000,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Bu notu yalnızca IT ekibi görebilir.",
            }
        ),
    )

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if not message:
            raise forms.ValidationError("İç not boş olamaz.")
        return message


class IssuePublicCommentForm(forms.Form):
    message = forms.CharField(
        label="Yanıt / ek bilgi",
        max_length=2000,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Talep hakkında ek bilgi veya yanıt yazın.",
            }
        ),
    )

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if not message:
            raise forms.ValidationError("Mesaj boş olamaz.")
        return message


class IssueParticipantForm(forms.Form):
    participants = forms.ModelMultipleChoiceField(
        label="Birimden katılımcılar",
        queryset=User.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Seçilen kişiler bu talebi ve kullanıcıya açık yanıtları görebilir. IT iç notları gizli kalır.",
    )

    def __init__(self, *args, issue, **kwargs):
        super().__init__(*args, **kwargs)
        unit_id = issue.device.unit_id
        candidates = User.objects.none()
        if unit_id:
            candidates = User.objects.filter(
                is_active=True,
                role=User.Role.UNIT_USER,
                scopes__unit_id=unit_id,
            ).exclude(pk=issue.reported_by_id).distinct().order_by("last_name", "first_name", "username")
        self.fields["participants"].queryset = candidates
        self.fields["participants"].initial = IssueParticipant.objects.filter(
            issue=issue,
            user__in=candidates,
        ).values_list("user_id", flat=True)


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
        current_team = kwargs.pop("current_team", None)
        super().__init__(*args, **kwargs)
        allowed_units = it_units_for(actor)
        if not is_primary_admin(actor):
            allowed_units = allowed_units.filter(pk=current_team.pk) if current_team else Unit.objects.none()
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
            "Cihazın birimi varsayılan ilk ekiptir. Başka ekibe aktardığında yeni ekip işi devralır; admin kaydı izlemeye devam eder."
            if is_primary_admin(actor)
            else "Ekipler arası aktarımı admin yapar. Burada mevcut ekibin kuyruğunu ve sorumlusunu yönetebilirsin."
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
