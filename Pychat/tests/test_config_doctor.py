import os, unittest
from lmchat.core.config_doctor import diagnose, render
from lmchat.core.providers import ProviderManager

REG = ProviderManager.PROVIDERS


class ConfigDoctorTest(unittest.TestCase):
    def setUp(self):
        # deterministic: no ambient cloud keys
        for v in ("OPENAI_API_KEY", "XAI_API_KEY", "ANTHROPIC_API_KEY",
                  "GEMINI_API_KEY", "GOOGLE_API_KEY"):
            os.environ.pop(v, None)

    def _codes(self, cfg):
        out = {}
        for f in diagnose(cfg, REG):
            out.setdefault(f["provider"], set()).add(f["code"])
        return out

    def test_ok_cleartext_missing_unknown(self):
        cfg = {"providers": {
            "gemma-code": {"type": "ollama", "model": "gemma4:12b"},
            "gpt":        {"type": "openai", "api_key": "sk-secret"},
            "grok":       {"type": "xai"},
            "weird":      {"type": "bogus"},
        }}
        c = self._codes(cfg)
        self.assertIn("OK", c["gemma-code"])
        self.assertIn("CLEARTEXT_KEY", c["gpt"])
        self.assertIn("MISSING_KEY", c["grok"])
        self.assertIn("UNKNOWN_TYPE", c["weird"])

    def test_env_key_satisfies_requirement(self):
        os.environ["XAI_API_KEY"] = "x"
        c = self._codes({"providers": {"grok": {"type": "xai"}}})
        self.assertIn("OK", c["grok"])
        self.assertNotIn("MISSING_KEY", c["grok"])

    def test_no_providers_warns(self):
        c = self._codes({})
        self.assertIn("NO_PROVIDERS", c["(top-level)"])

    def test_render_is_str_and_mentions_codes(self):
        r = render(diagnose({"providers": {"grok": {"type": "xai"}}}, REG))
        self.assertIsInstance(r, str)
        self.assertIn("MISSING_KEY", r)
        self.assertEqual(render([]), "no findings")


if __name__ == "__main__":
    unittest.main()
