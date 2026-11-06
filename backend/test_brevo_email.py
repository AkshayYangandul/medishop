"""Mocked Brevo contract tests: no network requests or real email delivery."""
import json
import os
import unittest
from unittest.mock import MagicMock, patch

try:
    import email_service
    import email_sender_service
except ImportError:  # pragma: no cover
    from backend import email_service, email_sender_service


class Response:
    status = 201
    def __enter__(self): return self
    def __exit__(self, *_): return False


class TestBrevoEmail(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"BREVO_API_KEY": "unit-secret"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.sender = {"from_email": "sender-a@example.test", "from_name": "MediShop Test",
                       "reply_to_email": "reply@example.test", "is_verified": True}
        self.engine = MagicMock()

    def capture_request(self, request, timeout):
        self.request = request
        self.timeout = timeout
        return Response()

    def test_brevo_api_request_headers_payload_and_password_recipient(self):
        with patch.object(email_service, "active_sender", return_value=self.sender), \
             patch.object(email_service.urllib.request, "urlopen", side_effect=self.capture_request):
            self.assertTrue(email_service.send_password_reset_email(
                "reset-user@example.test", "reset-token-test", "User", engine=self.engine))
        self.assertEqual(self.request.full_url, "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(self.request.get_header("Api-key"), "unit-secret")
        self.assertEqual(self.timeout, 15)
        data = json.loads(self.request.data)
        self.assertEqual(data["sender"], {"email": "sender-a@example.test", "name": "MediShop Test"})
        self.assertEqual(data["to"], [{"email": "reset-user@example.test"}])
        self.assertEqual(data["replyTo"], {"email": "reply@example.test"})
        self.assertIn("Reset Your MediShop Password", data["subject"])
        self.assertNotIn("unit-secret", self.request.data.decode())

    def test_login_warning_and_lock_keep_affected_user_as_recipient(self):
        with patch.object(email_service, "active_sender", return_value=self.sender), \
             patch.object(email_service.urllib.request, "urlopen", side_effect=self.capture_request):
            self.assertTrue(email_service.send_login_warning_email("warn@example.test", engine=self.engine))
            warning = json.loads(self.request.data)
            self.assertEqual(warning["to"][0]["email"], "warn@example.test")
            self.assertTrue(email_service.send_account_locked_email("locked@example.test", engine=self.engine))
            locked = json.loads(self.request.data)
            self.assertEqual(locked["to"][0]["email"], "locked@example.test")

    def test_all_transactional_workflows_use_brevo_dispatcher(self):
        requests = []
        def capture(request, timeout):
            requests.append((request, json.loads(request.data)))
            return Response()
        with patch.object(email_service, "active_sender", return_value=self.sender), \
             patch.object(email_service.urllib.request, "urlopen", side_effect=capture):
            email_service.send_password_reset_email("reset@example.test", "reset-token", engine=self.engine)
            email_service.send_login_warning_email("warning@example.test", engine=self.engine)
            email_service.send_account_locked_email("locked@example.test", engine=self.engine)
            email_service.send_test_email("test@example.test", self.engine)
        self.assertEqual(len(requests), 4)
        self.assertTrue(all(request.full_url == "https://api.brevo.com/v3/smtp/email"
                            for request, _ in requests))
        self.assertEqual([payload["to"][0]["email"] for _, payload in requests], [
            "reset@example.test", "warning@example.test", "locked@example.test", "test@example.test",
        ])
        self.assertTrue(all(payload["sender"]["email"] == "sender-a@example.test"
                            for _, payload in requests))

    def test_sender_is_resolved_each_send_without_restart(self):
        senders = [dict(self.sender), {**self.sender, "from_email": "sender-b@example.test"}]
        with patch.object(email_service, "active_sender", side_effect=senders), \
             patch.object(email_service.urllib.request, "urlopen", side_effect=self.capture_request):
            email_service.send_login_warning_email("a@example.test", engine=self.engine)
            first = json.loads(self.request.data)["sender"]["email"]
            email_service.send_login_warning_email("b@example.test", engine=self.engine)
            second = json.loads(self.request.data)["sender"]["email"]
        self.assertEqual((first, second), ("sender-a@example.test", "sender-b@example.test"))

    def test_provider_rejection_and_timeout_are_reported_as_failure(self):
        with patch.object(email_service, "active_sender", return_value=self.sender):
            with patch.object(email_service.urllib.request, "urlopen", side_effect=TimeoutError):
                self.assertFalse(email_service.send_login_warning_email("a@example.test", engine=self.engine))
            with patch.object(email_service.urllib.request, "urlopen", side_effect=__import__("urllib.error").error.HTTPError(
                    "https://api.brevo.com/v3/smtp/email", 401, "Unauthorized", {}, None)):
                self.assertFalse(email_service.send_login_warning_email("a@example.test", engine=self.engine))

    def test_unverified_sender_cannot_become_active(self):
        engine = MagicMock()
        conn = MagicMock()
        engine.begin.return_value.__enter__.return_value = conn
        result = MagicMock()
        result.mappings.return_value.first.return_value = {"is_verified": False, "disabled_at": None}
        conn.execute.side_effect = [MagicMock(), result]
        with self.assertRaises(Exception):
            email_sender_service.activate_sender(engine, "sender-id")

    def test_sender_verification_uses_brevo_status_when_api_is_available(self):
        engine = MagicMock()
        conn = MagicMock()
        engine.begin.return_value.__enter__.return_value = conn
        lookup = MagicMock()
        lookup.mappings.return_value.first.return_value = {"sender_email": "sender-a@example.test"}
        conn.execute.side_effect = [lookup, MagicMock()]
        with patch.object(email_sender_service, "brevo_sender_status", return_value=True):
            result = email_sender_service.mark_sender_verified(engine, "id", True)
        self.assertIn("Brevo confirmed", result["message"])
        update_sql = str(conn.execute.call_args_list[1].args[0])
        self.assertIn("verification_method='brevo_api'", update_sql)
        self.assertIn("is_active=IF(disabled_at IS NULL, is_active, 0)", update_sql)

    def test_inactive_sender_from_brevo_cannot_be_confirmed(self):
        engine = MagicMock()
        conn = MagicMock()
        engine.begin.return_value.__enter__.return_value = conn
        lookup = MagicMock()
        lookup.mappings.return_value.first.return_value = {"sender_email": "sender-a@example.test"}
        conn.execute.return_value = lookup
        with patch.object(email_sender_service, "brevo_sender_status", return_value=False):
            with self.assertRaises(Exception):
                email_sender_service.mark_sender_verified(engine, "id", True)

    def test_unavailable_brevo_verification_never_marks_sender_verified(self):
        engine = MagicMock()
        conn = MagicMock()
        engine.begin.return_value.__enter__.return_value = conn
        lookup = MagicMock()
        lookup.mappings.return_value.first.return_value = {"sender_email": "sender-a@example.test"}
        conn.execute.return_value = lookup
        with patch.object(email_sender_service, "brevo_sender_status",
                          side_effect=email_sender_service.BrevoSenderVerificationError("Brevo returned HTTP 403 (permission_denied).")):
            with self.assertRaises(Exception) as raised:
                email_sender_service.mark_sender_verified(engine, "id", True)
        self.assertIn("HTTP 403", str(raised.exception))
        self.assertEqual(conn.execute.call_count, 1)

    def test_unavailable_brevo_check_keeps_previously_verified_sender_inactive(self):
        engine = MagicMock()
        conn = MagicMock()
        engine.begin.return_value.__enter__.return_value = conn
        current = MagicMock()
        current.mappings.return_value.first.return_value = {
            "is_verified": True, "verification_method": "brevo_api", "disabled_at": None,
        }
        sender_email = MagicMock()
        sender_email.scalar_one.return_value = "sender-a@example.test"
        conn.execute.side_effect = [MagicMock(), current, sender_email, MagicMock()]
        with patch.object(email_sender_service, "brevo_sender_status",
                          side_effect=email_sender_service.BrevoSenderVerificationError("Brevo returned HTTP 403 (permission_denied).")):
            with self.assertRaises(Exception) as raised:
                email_sender_service.activate_sender(engine, "id")
        self.assertIn("HTTP 403", str(raised.exception))
        self.assertEqual(conn.execute.call_count, 3)

    def test_sender_requires_fresh_brevo_active_status_to_activate(self):
        engine = MagicMock()
        conn = MagicMock()
        engine.begin.return_value.__enter__.return_value = conn
        current = MagicMock()
        current.mappings.return_value.first.return_value = {
            "is_verified": True, "verification_method": "brevo_api", "disabled_at": None,
        }
        sender_email = MagicMock()
        sender_email.scalar_one.return_value = "sender-a@example.test"
        conn.execute.side_effect = [MagicMock(), current, sender_email, MagicMock(), MagicMock()]
        with patch.object(email_sender_service, "brevo_sender_status", return_value=True):
            result = email_sender_service.activate_sender(engine, "id")
        self.assertIn("updated", result["message"])
        self.assertIn("is_active=1", str(conn.execute.call_args_list[4].args[0]))

    def test_disabled_brevo_verified_sender_can_be_reactivated_after_fresh_check(self):
        engine = MagicMock()
        conn = MagicMock()
        engine.begin.return_value.__enter__.return_value = conn
        target = MagicMock()
        target.mappings.return_value.first.return_value = {
            "is_verified": True, "verification_method": "brevo_api", "disabled_at": "previously-disabled",
        }
        sender_email = MagicMock()
        sender_email.scalar_one.return_value = "sender-a@example.test"
        conn.execute.side_effect = [MagicMock(), target, sender_email, MagicMock(), MagicMock()]
        with patch.object(email_sender_service, "brevo_sender_status", return_value=True) as fresh_check:
            result = email_sender_service.activate_sender(engine, "id")
        self.assertIn("updated", result["message"])
        fresh_check.assert_called_once_with("sender-a@example.test")
        self.assertEqual(str(conn.execute.call_args_list[3].args[0]), "UPDATE email_sender_identities SET is_active=0")
        self.assertIn("is_active=1", str(conn.execute.call_args_list[4].args[0]))
        self.assertIn("disabled_at=NULL", str(conn.execute.call_args_list[4].args[0]))

    def test_sender_reported_inactive_by_brevo_cannot_be_enabled(self):
        engine = MagicMock()
        conn = MagicMock()
        engine.begin.return_value.__enter__.return_value = conn
        target = MagicMock()
        target.mappings.return_value.first.return_value = {
            "is_verified": True, "verification_method": "brevo_api", "disabled_at": "previously-disabled",
        }
        sender_email = MagicMock()
        sender_email.scalar_one.return_value = "sender-a@example.test"
        conn.execute.side_effect = [MagicMock(), target, sender_email, MagicMock()]
        with patch.object(email_sender_service, "brevo_sender_status", return_value=False) as fresh_check:
            with self.assertRaises(Exception) as raised:
                email_sender_service.activate_sender(engine, "id")
        self.assertIn("no longer reports this sender as active", str(raised.exception))
        fresh_check.assert_called_once_with("sender-a@example.test")
        self.assertNotIn("disabled_at=NULL", " ".join(str(call.args[0]) for call in conn.execute.call_args_list))

    def test_sender_activation_switches_from_previous_active_identity(self):
        engine = MagicMock()
        conn = MagicMock()
        engine.begin.return_value.__enter__.return_value = conn
        target = MagicMock()
        target.mappings.return_value.first.return_value = {
            "is_verified": True, "verification_method": "brevo_api", "disabled_at": None,
        }
        sender_email = MagicMock()
        sender_email.scalar_one.return_value = "sender-b@example.test"
        conn.execute.side_effect = [MagicMock(), target, sender_email, MagicMock(), MagicMock()]
        with patch.object(email_sender_service, "brevo_sender_status", return_value=True):
            email_sender_service.activate_sender(engine, "sender-b")
        self.assertEqual(str(conn.execute.call_args_list[3].args[0]), "UPDATE email_sender_identities SET is_active=0")
        self.assertIn("WHERE id=:id", str(conn.execute.call_args_list[4].args[0]))
        self.assertIn("disabled_at=NULL", str(conn.execute.call_args_list[4].args[0]))

    def test_brevo_403_response_is_sanitized_and_actionable(self):
        body = json.dumps({"code": "permission_denied", "message": "api key is not authorized for resource account; unit-secret"}).encode()
        error = __import__("urllib.error").error.HTTPError(
            "https://api.brevo.com/v3/senders", 403, "Forbidden", {}, __import__("io").BytesIO(body)
        )
        with patch.object(email_sender_service.urllib.request, "urlopen", side_effect=error):
            with self.assertLogs(email_sender_service.logger, level="WARNING") as captured:
                with self.assertRaises(email_sender_service.BrevoSenderVerificationError) as raised:
                    email_sender_service.brevo_sender_status("sender-a@example.test")
        detail = raised.exception.detail
        self.assertIn("HTTP 403", detail)
        self.assertIn("permission_denied", detail)
        self.assertIn("GET /v3/senders", detail)
        self.assertNotIn("unit-secret", detail)
        self.assertNotIn("unit-secret", "\n".join(captured.output))

    def test_changing_sender_email_clears_previous_verification_and_active_state(self):
        engine = MagicMock()
        conn = MagicMock()
        engine.begin.return_value.__enter__.return_value = conn
        prior = MagicMock()
        prior.mappings.return_value.first.return_value = {
            "sender_email": "sender-a@example.test", "is_verified": True,
        }
        conn.execute.side_effect = [prior, MagicMock()]
        email_sender_service.update_sender(engine, "id", {
            "sender_email": "sender-b@example.test", "sender_name": "B", "reply_to_email": "reply@example.test",
        })
        update_sql = str(conn.execute.call_args_list[1].args[0])
        update_params = conn.execute.call_args_list[1].args[1]
        self.assertIn("is_verified=IF(:changed, 0, is_verified)", update_sql)
        self.assertIn("is_active=IF(:changed, 0, is_active)", update_sql)
        self.assertTrue(update_params["changed"])

    def test_test_email_uses_brevo_and_active_identity(self):
        with patch.object(email_service, "active_sender", return_value=self.sender), \
             patch.object(email_service.urllib.request, "urlopen", side_effect=self.capture_request):
            result = email_service.send_test_email("admin@example.test", self.engine)
        self.assertEqual(result["status"], "accepted")
        data = json.loads(self.request.data)
        self.assertEqual(data["sender"]["email"], "sender-a@example.test")
        self.assertEqual(data["to"], [{"email": "admin@example.test"}])
        self.assertNotIn("unit-secret", json.dumps(result))

    def test_legacy_provider_environment_value_cannot_change_brevo_dispatch(self):
        with patch.dict(os.environ, {"EMAIL_PROVIDER": "smtp"}), \
             patch.object(email_service, "active_sender", return_value=self.sender), \
             patch.object(email_service.urllib.request, "urlopen", side_effect=self.capture_request):
            self.assertTrue(email_service.send_login_warning_email("staff@example.test", engine=self.engine))
        self.assertEqual(self.request.full_url, "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(json.loads(self.request.data)["to"], [{"email": "staff@example.test"}])

    def test_test_email_rejects_invalid_recipient_before_dispatch(self):
        with patch.object(email_service, "dispatch_transactional_message") as dispatcher:
            with self.assertRaises(Exception) as raised:
                email_service.send_test_email("not-an-email", self.engine)
        self.assertIn("valid recipient", str(raised.exception).lower())
        dispatcher.assert_not_called()

    def test_brevo_test_email_requires_an_active_sender(self):
        with patch.object(email_service, "active_sender", return_value=None), \
             patch.object(email_service.urllib.request, "urlopen") as urlopen:
            with self.assertRaises(Exception) as raised:
                email_service.send_test_email("recipient@example.test", self.engine)
        self.assertIn("active verified sender", str(raised.exception).lower())
        urlopen.assert_not_called()

    def test_brevo_test_email_rejection_is_reported_without_provider_fallback(self):
        error = __import__("urllib.error").error.HTTPError(
            "https://api.brevo.com/v3/smtp/email", 401, "Unauthorized", {}, None
        )
        with patch.object(email_service, "active_sender", return_value=self.sender), \
             patch.object(email_service.urllib.request, "urlopen", side_effect=error) as urlopen:
            with self.assertRaises(Exception) as raised:
                email_service.send_test_email("recipient@example.test", self.engine)
        self.assertIn("HTTP 401", str(raised.exception))
        self.assertEqual(urlopen.call_count, 1)

    def test_provider_test_endpoint_requires_active_admin(self):
        try:
            import main
        except ImportError:
            from backend import main
        try:
            from auth import require_active_admin
        except ImportError:
            from backend.auth import require_active_admin
        route = next(route for route in main.app.routes
                     if getattr(route, "path", "") == "/api/admin/email-settings/test")
        self.assertTrue(any(dependency.call is main.require_active_admin
                            for dependency in route.dependant.dependencies))
        self.assertFalse(any("smtp-settings" in getattr(route, "path", "") for route in main.app.routes))
        with self.assertRaises(Exception) as raised:
            require_active_admin({"id": "pharmacist", "role": "pharmacist", "is_active": True})
        self.assertEqual(raised.exception.status_code, 403)
        admin = {"id": "admin", "role": "admin", "is_active": True}
        self.assertIs(require_active_admin(admin), admin)

    def test_admin_settings_route_is_protected_and_masks_api_key(self):
        try:
            import main
        except ImportError:
            from backend import main
        route = next(route for route in main.app.routes if getattr(route, "path", "") == "/api/admin/email-settings")
        self.assertTrue(any(dependency.call is main.require_active_admin for dependency in route.dependant.dependencies))
        with patch.object(main.email_sender_service, "list_senders", return_value=[]):
            response = main.get_email_settings_endpoint(current_admin={"id": "admin"})
        self.assertEqual(response["provider"], "brevo")
        self.assertTrue(response["brevo_configured"])
        self.assertNotIn("unit-secret", json.dumps(response))


if __name__ == "__main__":
    unittest.main()
