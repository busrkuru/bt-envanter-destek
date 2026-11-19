from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import AssignmentHistory, Device, DeviceType
from organization.models import Department, Unit, UserScope
from support.models import Issue


User = get_user_model()


class ReportAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username="main-admin",
            password="test-password",
            role=User.Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        cls.manager = User.objects.create_user(
            username="it-manager",
            password="test-password",
            role=User.Role.IT_MANAGER,
            is_staff=True,
        )
        cls.unit_user = User.objects.create_user(
            username="unit-user",
            password="test-password",
            role=User.Role.UNIT_USER,
        )

        cls.department_a = Department.objects.create(name="Departman A", code="DEPT-A")
        cls.department_b = Department.objects.create(name="Departman B", code="DEPT-B")
        cls.unit_a = Unit.objects.create(department=cls.department_a, name="Birim A", code="UNIT-A")
        cls.unit_b = Unit.objects.create(department=cls.department_b, name="Birim B", code="UNIT-B")
        UserScope.objects.create(user=cls.manager, department=cls.department_a, unit=cls.unit_a)

        device_type = DeviceType.objects.create(name="Bilgisayar")
        cls.device_a = Device.objects.create(
            asset_tag="ASSET-A",
            device_type=device_type,
            department=cls.department_a,
            unit=cls.unit_a,
            created_by=cls.admin,
        )
        cls.device_b = Device.objects.create(
            asset_tag="ASSET-B",
            device_type=device_type,
            department=cls.department_b,
            unit=cls.unit_b,
            created_by=cls.admin,
        )
        AssignmentHistory.objects.create(
            device=cls.device_a,
            user=cls.unit_user,
            assigned_by=cls.admin,
        )

        cls.issue_a = Issue.objects.create(
            device=cls.device_a,
            reported_by=cls.unit_user,
            title="Issue in department A",
            description="Visible only to its reporter and authorized IT staff.",
        )
        cls.issue_b = Issue.objects.create(
            device=cls.device_b,
            reported_by=cls.admin,
            title="Issue in department B",
            description="Outside the IT manager's scope.",
        )

    def test_unit_user_is_forbidden_from_reports_and_csv_exports(self):
        self.client.force_login(self.unit_user)

        for url_name in (
            "inventory:reports",
            "inventory:export_devices_csv",
            "inventory:export_issues_csv",
        ):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 403)

    def test_it_manager_reports_and_device_export_are_scope_limited(self):
        self.client.force_login(self.manager)

        reports_response = self.client.get(reverse("inventory:reports"))
        self.assertEqual(reports_response.status_code, 200)
        self.assertContains(reports_response, "Departman A")
        self.assertNotContains(reports_response, "Departman B")

        csv_response = self.client.get(reverse("inventory:export_devices_csv"))
        self.assertEqual(csv_response.status_code, 200)
        self.assertContains(csv_response, "ASSET-A")
        self.assertNotContains(csv_response, "ASSET-B")

    def test_it_manager_issue_export_is_scope_limited(self):
        self.client.force_login(self.manager)

        response = self.client.get(reverse("inventory:export_issues_csv"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Issue in department A")
        self.assertNotContains(response, "Issue in department B")

    def test_unit_user_cannot_open_another_users_device(self):
        self.client.force_login(self.unit_user)

        response = self.client.get(
            reverse("inventory:device_detail", kwargs={"device_id": self.device_b.pk})
        )

        self.assertEqual(response.status_code, 404)

    def test_primary_admin_can_open_reports_and_exports(self):
        self.client.force_login(self.admin)

        for url_name in (
            "inventory:reports",
            "inventory:export_devices_csv",
            "inventory:export_issues_csv",
        ):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)
