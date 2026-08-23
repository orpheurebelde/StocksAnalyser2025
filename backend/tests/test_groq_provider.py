import os
import sys
import types
import unittest
from unittest.mock import patch

with patch.dict(sys.modules, {"requests": types.ModuleType("requests")}):
    from core.ai.groq_provider import DEFAULT_GROQ_MODEL, GroqProvider


class GroqProviderTests(unittest.TestCase):
    def test_uses_supported_default_model(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=True):
            provider = GroqProvider()

        self.assertEqual(DEFAULT_GROQ_MODEL, "openai/gpt-oss-120b")
        self.assertEqual(provider.model_name, DEFAULT_GROQ_MODEL)

    def test_environment_can_override_model(self):
        with patch.dict(
            os.environ,
            {"GROQ_API_KEY": "test-key", "GROQ_MODEL": "custom/model"},
            clear=True,
        ):
            provider = GroqProvider()

        self.assertEqual(provider.model_name, "custom/model")


if __name__ == "__main__":
    unittest.main()
