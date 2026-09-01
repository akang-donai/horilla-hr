"""GeoFencing department exemption tests."""

from unittest.mock import patch
from django.test import TestCase
from base.models import Company, Department
from geofencing.models import GeoFencing


class GeoFencingExemptionTests(TestCase):
    @patch("geofencing.models.Nominatim")
    def setUp(self, _nom):
        self.company = Company.objects.create(company="ACME")
        self.sales = Department.objects.create(department="Sales")
        self.eng = Department.objects.create(department="Engineering")
        self.fence = GeoFencing(
            latitude=10.0, longitude=76.0, radius_in_meters=100,
            company_id=self.company, start=True,
        )
        self.fence.save()
        self.fence.exempt_departments.add(self.sales)

    def test_exempt_department(self):
        self.assertTrue(self.fence.is_department_exempt(self.sales))

    def test_non_exempt_department(self):
        self.assertFalse(self.fence.is_department_exempt(self.eng))

    def test_none_department_not_exempt(self):
        self.assertFalse(self.fence.is_department_exempt(None))
