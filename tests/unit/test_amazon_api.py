# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from unittest.mock import patch, MagicMock
import requests

from app.agent import (
    fetch_amazon_brands,
    RateLimitException,
    APIAuthenticationError,
    TransientServerError
)


def make_mock_response(status_code=200, json_data=None):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    if json_data is not None:
        mock_resp.json.return_value = json_data
    else:
        mock_resp.json.return_value = {}
    
    if status_code >= 400:
        err = requests.exceptions.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = err
    else:
        mock_resp.raise_for_status.return_value = None
    return mock_resp


class TestAmazonAPISchemaAndErrorHandling(unittest.TestCase):

    @patch("requests.get")
    def test_fetch_amazon_brands_success(self, mock_get):
        mock_get.return_value = make_mock_response(
            status_code=200,
            json_data={
                "suggestions": [
                    {"value": "amazon basics batteries"},
                    {"value": "energizer aa batteries"}
                ]
            }
        )
        
        res = fetch_amazon_brands("batteries")
        self.assertIn("audit_metadata", res)
        self.assertEqual(res["audit_metadata"]["keyword"], "batteries")
        self.assertEqual(res["audit_metadata"]["status_code"], 200)
        self.assertIsNone(res["error_log"])
        
        results = res["results"]
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["rank"], 1)
        self.assertEqual(results[0]["value"], "amazon basics batteries")
        self.assertEqual(results[0]["brand_type"], "house_brand")
        
        self.assertEqual(results[1]["rank"], 2)
        self.assertEqual(results[1]["value"], "energizer aa batteries")
        self.assertEqual(results[1]["brand_type"], "third_party")

    @patch("time.sleep", return_value=None)
    @patch("requests.get")
    def test_fetch_amazon_brands_rate_limiting_429(self, mock_get, mock_sleep):
        mock_get.return_value = make_mock_response(status_code=429)
        
        res = fetch_amazon_brands("batteries")
        self.assertEqual(res["audit_metadata"]["status_code"], 429)
        self.assertIn("RateLimitException", res["error_log"])
        self.assertEqual(mock_sleep.call_count, 3)

    @patch("requests.get")
    def test_fetch_amazon_brands_auth_error_403(self, mock_get):
        mock_get.return_value = make_mock_response(status_code=403)
        
        res = fetch_amazon_brands("batteries")
        self.assertEqual(res["audit_metadata"]["status_code"], 403)
        self.assertIn("APIAuthenticationError", res["error_log"])
        self.assertEqual(mock_get.call_count, 2)

    @patch("time.sleep", return_value=None)
    @patch("requests.get")
    def test_fetch_amazon_brands_server_error_502(self, mock_get, mock_sleep):
        mock_get.return_value = make_mock_response(status_code=502)
        
        res = fetch_amazon_brands("batteries")
        self.assertEqual(res["audit_metadata"]["status_code"], 502)
        self.assertIn("TransientServerError", res["error_log"])
        mock_sleep.assert_called_once_with(5.0)

    @patch("requests.get")
    def test_fetch_amazon_brands_empty_suggestions_anomaly(self, mock_get):
        mock_get.return_value = make_mock_response(
            status_code=200,
            json_data={"suggestions": []}
        )
        
        res = fetch_amazon_brands("batteries")
        self.assertEqual(res["audit_metadata"]["status_code"], 200)
        self.assertEqual(res["results"], [])
        self.assertIn("AnomalyWarning", res["error_log"])

    @patch("requests.get")
    def test_fetch_amazon_brands_generic_fallback(self, mock_get):
        mock_get.return_value = make_mock_response(
            status_code=200,
            json_data={
                "suggestions": [
                    {"value": "clothing"},
                    {"value": "electronics"}
                ]
            }
        )
        
        res = fetch_amazon_brands("batteries")
        self.assertEqual(res["audit_metadata"]["status_code"], 200)
        self.assertEqual(res["results"], [])
        self.assertIn("generic category fallbacks", res["error_log"])
