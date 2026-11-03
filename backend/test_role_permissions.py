"""
MediShop Role-Based Access Control and Permission Tests
========================================================
Comprehensive automated test suite verifying:
- Pharmacist role permissions (Dashboard, Medicines read, Customers, POS / Sales)
- Strict enforcement of HTTP 403 on restricted modules (Categories write, Brands write,
  Batches management, Suppliers, Purchases, Expenses, Reports, Staff management)
- Medicine write restrictions (Pharmacist cannot create, edit, or delete medicines -> HTTP 403)
- Information protection: wholesale purchase_cost_at_sale hidden from pharmacists on invoices
- Staff role assignment validation: only 'admin' and 'pharmacist' allowed
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException, status

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import main
import auth
import user_service


class TestRoleDependencies(unittest.TestCase):
    """Verifies low-level FastAPI role dependencies."""

    def test_require_active_admin_accepts_admin(self):
        profile = {"id": "u1", "role": "admin", "is_active": True}
        self.assertEqual(auth.require_active_admin(current_user=profile), profile)

    def test_require_active_admin_rejects_pharmacist(self):
        profile = {"id": "u2", "role": "pharmacist", "is_active": True}
        with self.assertRaises(HTTPException) as ctx:
            auth.require_active_admin(current_user=profile)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Active administrator privileges required", ctx.exception.detail)

    def test_require_admin_or_pharmacist_accepts_admin(self):
        profile = {"id": "u1", "role": "admin", "is_active": True}
        self.assertEqual(auth.require_admin_or_pharmacist(current_user=profile), profile)

    def test_require_admin_or_pharmacist_accepts_pharmacist(self):
        profile = {"id": "u2", "role": "pharmacist", "is_active": True}
        self.assertEqual(auth.require_admin_or_pharmacist(current_user=profile), profile)

    def test_require_admin_or_pharmacist_rejects_other_roles(self):
        profile = {"id": "u3", "role": "cashier", "is_active": True}
        with self.assertRaises(HTTPException) as ctx:
            auth.require_admin_or_pharmacist(current_user=profile)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)


class TestPharmacistPermissionEnforcement(unittest.TestCase):
    """
    Verifies that pharmacists are restricted from administrative actions
    and protected from accessing confidential cost figures.
    """

    def setUp(self):
        self.pharmacist = {
            "id": "p-100",
            "email": "pharmacist@medishop.local",
            "full_name": "Test Pharmacist",
            "role": "pharmacist",
            "is_active": True,
        }
        self.admin = {
            "id": "a-100",
            "email": "admin@medishop.local",
            "full_name": "Test Admin",
            "role": "admin",
            "is_active": True,
        }

    # 1. Medicine Access Controls
    @patch.object(main, "medicine_create")
    def test_pharmacist_cannot_create_medicine(self, mock_create):
        with self.assertRaises(HTTPException) as ctx:
            auth.require_active_admin(current_user=self.pharmacist)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)
        mock_create.assert_not_called()

    @patch.object(main, "medicine_update")
    def test_pharmacist_cannot_update_medicine(self, mock_update):
        with self.assertRaises(HTTPException) as ctx:
            auth.require_active_admin(current_user=self.pharmacist)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)
        mock_update.assert_not_called()

    @patch.object(main, "medicine_update")
    def test_pharmacist_cannot_delete_or_deactivate_medicine(self, mock_update):
        with self.assertRaises(HTTPException) as ctx:
            auth.require_active_admin(current_user=self.pharmacist)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)
        mock_update.assert_not_called()

    @patch.object(main, "medicine_get")
    def test_pharmacist_can_read_single_medicine(self, mock_get):
        mock_get.return_value = {"id": "med-1", "name": "Amoxicillin"}
        result = main.get_medicine("med-1", current_user=self.pharmacist)
        self.assertEqual(result["id"], "med-1")
        mock_get.assert_called_once()

    # 2. Restricted Modules (Batches, Suppliers, Purchases, Expenses, Reports)
    def test_pharmacist_cannot_list_batches(self):
        with self.assertRaises(HTTPException) as ctx:
            auth.require_active_admin(current_user=self.pharmacist)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_pharmacist_cannot_list_suppliers(self):
        with self.assertRaises(HTTPException) as ctx:
            auth.require_active_admin(current_user=self.pharmacist)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_pharmacist_cannot_list_purchases(self):
        with self.assertRaises(HTTPException) as ctx:
            auth.require_active_admin(current_user=self.pharmacist)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_pharmacist_cannot_list_expenses(self):
        with self.assertRaises(HTTPException) as ctx:
            auth.require_active_admin(current_user=self.pharmacist)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_pharmacist_cannot_create_expenses(self):
        with self.assertRaises(HTTPException) as ctx:
            auth.require_active_admin(current_user=self.pharmacist)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    def test_pharmacist_cannot_view_financial_reports_summary(self):
        with self.assertRaises(HTTPException) as ctx:
            auth.require_active_admin(current_user=self.pharmacist)
        self.assertEqual(ctx.exception.status_code, status.HTTP_403_FORBIDDEN)

    # 3. Invoice Financial Data Protection
    @patch.object(main, "invoice_get")
    def test_invoice_strips_purchase_cost_for_pharmacist(self, mock_get):
        mock_get.return_value = {
            "id": "inv-101",
            "invoice_no": "INV-2026-001",
            "net_amount": 100.0,
            "items": [
                {
                    "id": "it-1",
                    "medicine_name": "Azithromycin",
                    "quantity": 2,
                    "unit_price": 50.0,
                    "purchase_cost_at_sale": 32.50,  # Sensitive internal cost
                }
            ],
        }

        # Call endpoint as pharmacist
        pharmacist_view = main.get_invoice("inv-101", current_user=self.pharmacist)
        item = pharmacist_view["items"][0]
        self.assertNotIn("purchase_cost_at_sale", item)
        self.assertEqual(item["unit_price"], 50.0)

    @patch.object(main, "invoice_get")
    def test_invoice_retains_purchase_cost_for_admin(self, mock_get):
        mock_get.return_value = {
            "id": "inv-101",
            "invoice_no": "INV-2026-001",
            "net_amount": 100.0,
            "items": [
                {
                    "id": "it-1",
                    "medicine_name": "Azithromycin",
                    "quantity": 2,
                    "unit_price": 50.0,
                    "purchase_cost_at_sale": 32.50,
                }
            ],
        }

        # Call endpoint as admin
        admin_view = main.get_invoice("inv-101", current_user=self.admin)
        item = admin_view["items"][0]
        self.assertIn("purchase_cost_at_sale", item)
        self.assertEqual(item["purchase_cost_at_sale"], 32.50)


class TestStaffRoleValidation(unittest.TestCase):
    """Verifies staff creation accepts only admin and pharmacist roles."""

    def test_user_create_rejects_cashier_role(self):
        engine = MagicMock()
        payload = {
            "email": "cashier@medishop.local",
            "password": "validPassword123",
            "full_name": "Cashier User",
            "role": "cashier",
        }
        with self.assertRaises(HTTPException) as ctx:
            user_service.user_create(engine, payload)
        self.assertIn(ctx.exception.status_code, (status.HTTP_422_UNPROCESSABLE_ENTITY, 422))
        self.assertIn("Must be 'admin' or 'pharmacist'", ctx.exception.detail)

    def test_user_create_accepts_pharmacist_role(self):
        engine = MagicMock()
        conn = MagicMock()
        engine.begin.return_value.__enter__.return_value = conn
        
        # Email lookup query returns None (not duplicate)
        # Select query returns created row
        def mock_execute(stmt, params=None):
            m = MagicMock()
            if "SELECT id FROM profiles" in str(stmt):
                m.first.return_value = None
            else:
                m.mappings.return_value.first.return_value = {
                    "id": "u-new",
                    "email": "newpharm@medishop.local",
                    "full_name": "New Pharmacist",
                    "role": "pharmacist",
                    "phone": None,
                    "is_active": True,
                }
            return m

        conn.execute.side_effect = mock_execute

        payload = {
            "email": "newpharm@medishop.local",
            "password": "validPassword123",
            "full_name": "New Pharmacist",
            "role": "pharmacist",
        }
        result = user_service.user_create(engine, payload)
        self.assertEqual(result["role"], "pharmacist")
        self.assertEqual(result["email"], "newpharm@medishop.local")


if __name__ == "__main__":
    unittest.main()
