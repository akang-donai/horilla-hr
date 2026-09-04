"""Page-title / favicon branding via the white_labelling_company context processor."""

from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings

from base.context_processors import white_labelling_company


class BrandNameContextTests(SimpleTestCase):
    def _req(self):
        return MagicMock()

    @override_settings(BRAND_NAME="NIRA", WHITE_LABELLING=True)
    def test_brand_name_wins_over_company_white_label(self):
        ctx = white_labelling_company(self._req())
        self.assertEqual(ctx["white_label_company_name"], "NIRA")
        # No company => templates fall back to the static NIRA favicons.
        self.assertIsNone(ctx["white_label_company"])

    @override_settings(BRAND_NAME=None, WHITE_LABELLING=False)
    def test_no_brand_no_white_label_is_upstream_default(self):
        ctx = white_labelling_company(self._req())
        self.assertEqual(ctx["white_label_company_name"], "Horilla")
        self.assertIsNone(ctx["white_label_company"])
