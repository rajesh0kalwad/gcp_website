import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from backend import main


class FakeVariable:
    def getvalue(self):
        return 741


class FakeCursor:
    def __init__(self, rows=()):
        self.rows = rows
        self.binds = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def var(self, _type):
        return FakeVariable()

    def execute(self, _sql, **binds):
        self.binds = binds

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.committed = True


class BackendTests(unittest.TestCase):
    def test_inquiry_requires_valid_email_and_service(self):
        with self.assertRaises(ValidationError):
            main.InquiryRequest(
                name="Taylor",
                email="not-an-email",
                service_slug="transport",
                message="Please contact me about transport.",
            )
        with self.assertRaises(ValidationError):
            main.InquiryRequest(
                name="Taylor",
                email="taylor@example.com",
                service_slug="unknown",
                message="Please contact me about this service.",
            )

    def test_inquiry_is_saved_and_returns_database_id(self):
        inquiry = main.InquiryRequest(
            name="Taylor",
            email="taylor@example.com",
            service_slug="transport",
            message="Please contact me about transport.",
        )
        cursor = FakeCursor()
        connection = FakeConnection(cursor)

        with patch("backend.main.connect_to_oracle", return_value=connection):
            result = main.create_inquiry(inquiry)

        self.assertEqual(result.inquiry_id, 741)
        self.assertEqual(cursor.binds["service_slug"], "transport")
        self.assertTrue(connection.committed)

    def test_database_errors_are_reported_as_service_unavailable(self):
        inquiry = main.InquiryRequest(
            name="Taylor",
            email="taylor@example.com",
            service_slug="consultation",
            message="I would like to arrange a consultation.",
        )

        with patch(
            "backend.main.connect_to_oracle",
            side_effect=RuntimeError("Oracle is not configured"),
        ):
            with self.assertRaises(HTTPException) as raised:
                main.create_inquiry(inquiry)

        self.assertEqual(raised.exception.status_code, 503)

    def test_services_are_read_from_oracle(self):
        cursor = FakeCursor(
            [("transport", "Transport", "Dependable transport.")]
        )
        connection = FakeConnection(cursor)

        with patch("backend.main.connect_to_oracle", return_value=connection):
            result = main.list_services()

        self.assertEqual(
            result,
            [
                {
                    "slug": "transport",
                    "title": "Transport",
                    "description": "Dependable transport.",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
