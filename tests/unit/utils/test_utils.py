import json
from decimal import Decimal
from unittest import IsolatedAsyncioTestCase, TestCase

from functions.utils import utils


class DefaultResponseTests(IsolatedAsyncioTestCase):
    async def test_returns_json_response_for_successful_async_creation(self):
        async def handler(value):
            return {"status": True, "message": "created", "data": {"value": value}}

        response = await utils.default_response(handler, [123], is_creation=True)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(json.loads(response.body), {"message": "created", "data": {"value": 123}})

    async def test_returns_dict_response_for_business_failure(self):
        def handler():
            return {"status": False, "message": "bad request", "data": {}}

        response = await utils.default_response(handler, dict_response=True)

        self.assertEqual(response, {"status": False, "message": "bad request", "data": {}})

    async def test_returns_internal_error_when_callable_raises(self):
        def handler():
            raise RuntimeError("boom")

        response = await utils.default_response(handler)

        self.assertEqual(response.status_code, 500)
        self.assertEqual(json.loads(response.body), {"detail": "Erro interno com o servidor."})


class UtilsTests(TestCase):
    def test_update_default_dict_normalizes_supported_types(self):
        payload = {
            "meta": '{"a": 1}',
            "amount": Decimal("9.99"),
            "paid_at": "2026-01-15",
            "createdAt": "2026-01-10T12:30:00",
        }

        result = utils.update_default_dict(payload, json_targets=["meta"], decimal_targets=["amount"], date_targets=["paid_at"])

        self.assertEqual(result["meta"], {"a": 1})
        self.assertEqual(result["amount"], 9.99)
        self.assertEqual(result["paid_at"], "2026-01-15")
        self.assertEqual(result["createdAt"], "2026-01-10T12:30:00")

    def test_generate_temp_code_returns_six_digits(self):
        code = utils.generate_temp_code()

        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())
