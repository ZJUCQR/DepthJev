"""Privacy and deployment checks that run without models or API calls."""

import io
import json
import os
import sys
import traceback
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image

from depthjev.actions import BY_KEY
from depthjev.jev_client import ChoiceResult, JevClient, JevError, JevResponse
from depthjev.policy import Policy, StepResult, build_response
from depthjev.server import create_app, parse_args


class PrivacyTests(unittest.TestCase):
    def setUp(self):
        self.private_detail = "private-request-detail-for-test"
        self.sentence = "## Now the human instruction is: Navigate to the pot.\n"
        self.image = Image.new("RGB", (8, 8))

    def test_client_preserves_proxy_configuration(self):
        sdk = SimpleNamespace(RetryPolicy=Mock(), TypeSafeClient=Mock())
        with (
            patch.dict(sys.modules, {"typesafe_sdk": sdk}),
            patch.dict(os.environ, {"NO_PROXY": "localhost", "no_proxy": "localhost"}),
        ):
            JevClient(api_key="test-placeholder")
            self.assertEqual(os.environ["NO_PROXY"], "localhost")
            self.assertEqual(os.environ["no_proxy"], "localhost")

    def test_sdk_errors_do_not_disclose_response_details(self):
        client = JevClient.__new__(JevClient)
        client._client = Mock()
        client._client.system_one.side_effect = RuntimeError(self.private_detail)
        try:
            client.ask({}, {})
        except JevError as exc:
            self.assertNotIn(self.private_detail, str(exc))
            self.assertNotIn(self.private_detail, traceback.format_exc())
        else:
            self.fail("Expected an API failure")

    def test_invalid_answer_errors_do_not_disclose_response_details(self):
        answer = SimpleNamespace(choice="move_ahead", probabilities={"move_ahead": self.private_detail})
        client = JevClient.__new__(JevClient)
        client._client = Mock()
        client._client.system_one.return_value = SimpleNamespace(answers={"action": answer})
        try:
            client.ask({}, {})
        except JevError as exc:
            self.assertNotIn(self.private_detail, str(exc))
            self.assertNotIn(self.private_detail, traceback.format_exc())
        else:
            self.fail("Expected an invalid answer")

    def test_unknown_target_errors_do_not_echo_answer(self):
        client = JevClient.__new__(JevClient)
        client.ask = Mock(
            return_value=JevResponse(answers={"target_type": ChoiceResult(self.private_detail, {}, None)})
        )
        client.target_type_question = Mock()
        with self.assertRaises(JevError) as caught:
            client.resolve_target_type("Find the pot")
        self.assertNotIn(self.private_detail, str(caught.exception))

    def test_policy_records_do_not_disclose_model_errors_or_file_paths(self):
        for target_resolution_fails in (False, True):
            for filename in ("private/folder/frame.png", r"C:\private\folder\frame.png"):
                with self.subTest(target_resolution_fails=target_resolution_fails, filename=filename):
                    depth, detector, jev = Mock(), Mock(), Mock()
                    depth.predict.side_effect = RuntimeError(self.private_detail)
                    detector.detect.side_effect = RuntimeError(self.private_detail)
                    target = JevResponse(answers={"target_type": ChoiceResult("Pot", {"Pot": 1.0}, 1.0)})
                    jev.resolve_target_type.return_value = ("Pot", target)
                    if target_resolution_fails:
                        jev.resolve_target_type.side_effect = JevError(self.private_detail)
                    jev.decide.side_effect = JevError(self.private_detail)
                    result = Policy(depth, detector, jev).step(self.image, self.sentence, image_name=filename)
                    self.assertTrue(result.record["fallback"])
                    self.assertNotIn(self.private_detail, json.dumps(result.record))
                    self.assertNotIn(self.private_detail, result.response_text)
                    self.assertEqual(result.record["image_name"], "frame.png")

    def test_server_errors_stay_private_and_keep_a_valid_fallback(self):
        policy = Mock()
        policy.step.side_effect = RuntimeError(self.private_detail)
        request_log = io.StringIO()
        with patch("depthjev.server.open", return_value=request_log):
            app = create_app(policy, "unused.jsonl")
        image_data = io.BytesIO()
        self.image.save(image_data, format="PNG")
        image_data.seek(0)
        with app.test_client() as client, self.assertLogs("depthjev.server", level="ERROR") as captured:
            response = client.post("/process", data={"image": (image_data, "frame.png"), "sentence": self.sentence})
            health = client.get("/health")
        self.assertEqual(response.status_code, 200)
        plan = json.loads(response.get_json()["response"])
        self.assertEqual(plan["executable_plan"][0]["action_id"], BY_KEY["rotate_right"].action_id)
        self.assertIsNotNone(health.get_json()["last_error"])
        for output in (
            response.get_data(as_text=True),
            health.get_data(as_text=True),
            request_log.getvalue(),
            *captured.output,
        ):
            self.assertNotIn(self.private_detail, output)

    def test_server_listens_locally_by_default_and_allows_explicit_remote_access(self):
        self.assertEqual(parse_args([]).host, "127.0.0.1")
        self.assertEqual(parse_args(["--host", "0.0.0.0"]).host, "0.0.0.0")

    def test_log_write_errors_stay_private_and_preserve_the_action(self):
        action = BY_KEY["move_ahead"]
        policy = Mock()
        policy.step.return_value = StepResult(
            action, build_response(action, "target ahead", "move toward target"), {"action": action.key}
        )
        request_log = Mock()
        request_log.write.side_effect = OSError(self.private_detail)
        with patch("depthjev.server.open", return_value=request_log):
            app = create_app(policy, "unused.jsonl")
        image_data = io.BytesIO()
        self.image.save(image_data, format="PNG")
        image_data.seek(0)
        with app.test_client() as client, self.assertLogs("depthjev.server", level="ERROR") as captured:
            response = client.post("/process", data={"image": (image_data, "frame.png"), "sentence": self.sentence})
        self.assertEqual(response.status_code, 200)
        plan = json.loads(response.get_json()["response"])
        self.assertEqual(plan["executable_plan"][0]["action_id"], action.action_id)
        self.assertNotIn(self.private_detail, "\n".join(captured.output))


if __name__ == "__main__":
    unittest.main()
