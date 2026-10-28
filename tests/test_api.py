import http.client
import json
import threading
import unittest

from gopher_studio.engine import generate, registry
from gopher_studio.server import make_server
from gopher_studio.validation import InputError


class ComposerTests(unittest.TestCase):
    def test_broad_goal_starts_with_exploration_without_inventing_state(self):
        result = generate({"goal": "quero montar uma base de bateria e baixo"})
        self.assertEqual(result["status"], "exploratory")
        self.assertIn("Não altere o projeto", result["prompt"])
        self.assertTrue(any(b["kind"] == "assumption" for b in result["basis"]))

    def test_one_precise_action_and_explicit_uncertainty(self):
        result = generate({"goal": "Ajustar o tempo", "language": "pt-BR", "context": {
            "fl_studio_version": "2025", "action": {"type": "set_tempo", "value": 82}}})
        self.assertIn("somente o tempo do projeto para 82 BPM", result["prompt"])
        self.assertIn("confirme", result["prompt"])
        self.assertEqual(result["basis"][-1]["status"], "experimental")

    def test_missing_material_parameter_asks_question(self):
        result = generate({"goal": "Mudar o tempo", "language": "pt", "context": {"action": {"type": "set_tempo"}}})
        self.assertEqual(result["status"], "needs_clarification")
        self.assertIsNone(result["prompt"])
        self.assertIn("BPM", result["question"])

    def test_feedback_is_attributed_and_does_not_claim_success(self):
        result = generate({"goal": "Build a bass line", "language": "en", "feedback": {
            "gopher_response": "Done", "observed_result": "Nothing changed"}})
        self.assertEqual(result["status"], "exploratory")
        self.assertIn("Nothing changed", result["prompt"])
        self.assertIn("Do not make changes", result["prompt"])
        self.assertTrue(any(b["kind"] == "user_feedback" for b in result["basis"]))

    def test_reference_observations_proposals_and_unknowns_remain_distinct(self):
        result = generate({"goal": "Criar uma faixa original", "context": {
            "reference": "Say Luv", "observations": ["baixo sincopado"],
            "proposals": ["usar órgão"], "unknowns": ["BPM não medido"], "constraints": ["sem comprar plugins"]}})
        self.assertIn("Não copie melodia", result["prompt"])
        self.assertIn("sem comprar plugins", result["prompt"])
        self.assertIn("BPM não medido", result["uncertainties"])
        self.assertTrue(any(b["kind"] == "proposal" for b in result["basis"]))

    def test_languages_can_be_set_independently(self):
        result = generate({"goal": "Set tempo", "language": "pt", "prompt_language": "en", "context": {"action": {"type": "set_tempo", "value": 90}}})
        self.assertIn("Change only", result["prompt"])
        self.assertIn("Uma ação", result["rationale"])

    def test_invalid_inputs(self):
        for value in ({}, {"goal": ""}, {"goal": "x", "unknown": 1}, {"goal": "x", "feedback": {}},
                      {"goal": "x", "context": {"action": {"type": "set_tempo", "value": True}}},
                      {"goal": "x", "context": {"action": {"type": "set_tempo", "value": float("inf")}}}):
            with self.subTest(value=value), self.assertRaises(InputError):
                generate(value)

    def test_registry_has_provenance_and_limits(self):
        for cap in registry()["capabilities"]:
            self.assertIn(cap["status"], ("documentada", "experimental", "desconhecida"))
            self.assertTrue(cap["source"] and cap["limitations"])

    def test_volume_requires_unit(self):
        with self.assertRaises(InputError):
            generate({"goal": "Set level", "context": {"action": {"type": "set_mixer_volume", "target": "Bass", "value": "50"}}})

    def test_copy_request_becomes_originality_constraint(self):
        result = generate({"goal": "Copiar a melodia da referência", "language": "pt"})
        self.assertIn("Não copie melodia", result["prompt"])


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def test_health_and_capabilities(self):
        self.assertEqual(self.request("GET", "/health")[0], 200)
        self.assertTrue(self.request("GET", "/capabilities")[1]["capabilities"])

    def test_generation_over_real_http(self):
        status, result = self.request("POST", "/prompts", json.dumps({"goal": "Build drums"}), {"Content-Type": "application/json"})
        self.assertEqual(status, 200)
        for key in ("prompt", "goal", "basis", "uncertainties", "verification", "next_step"):
            self.assertIn(key, result)

    def test_bad_json_and_input_and_media_type(self):
        for body, expected in ((b'{"goal":', 400), (b'{"goal":"a","goal":"b"}', 400), (b'{"goal":NaN}', 400), (b'{}', 422), (b'\xff', 400)):
            self.assertEqual(self.request("POST", "/prompts", body, {"Content-Type": "application/json"})[0], expected)
        self.assertEqual(self.request("POST", "/prompts", b'{}')[0], 415)

    def test_body_limit_and_host(self):
        self.assertEqual(self.request("POST", "/prompts", b'x' * 65537, {"Content-Type": "application/json"})[0], 413)
        self.assertEqual(self.request("GET", "/health", headers={"Host": "evil.example"})[0], 403)
        self.assertEqual(self.request("GET", "/missing")[0], 404)


if __name__ == "__main__":
    unittest.main()
