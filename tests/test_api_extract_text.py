import unittest
from types import SimpleNamespace

from research.api import _extract_text


class ExtractTextTest(unittest.TestCase):
    def test_extract_text_from_plain_string_response(self) -> None:
        self.assertEqual(_extract_text('{"ok": true}'), '{"ok": true}')

    def test_extract_text_from_dict_response(self) -> None:
        response = {
            "choices": [
                {
                    "message": {
                        "content": '{"ok": true, "source": "dict"}'
                    }
                }
            ]
        }
        self.assertEqual(_extract_text(response), '{"ok": true, "source": "dict"}')

    def test_extract_text_from_output_text_attribute(self) -> None:
        response = SimpleNamespace(output_text='{"ok": true, "source": "output_text"}')
        self.assertEqual(_extract_text(response), '{"ok": true, "source": "output_text"}')

    def test_extract_text_from_choice_text_attribute(self) -> None:
        response = SimpleNamespace(
            choices=[SimpleNamespace(text='{"ok": true, "source": "choice_text"}')]
        )
        self.assertEqual(_extract_text(response), '{"ok": true, "source": "choice_text"}')

    def test_extract_text_from_sse_string_with_content(self) -> None:
        response = '\n'.join([
            'data: {"choices":[{"delta":{"content":"hello"}}]}',
            'data: {"choices":[{"delta":{"content":" world"}}]}',
            'data: [DONE]',
        ])
        self.assertEqual(_extract_text(response), 'hello world')

    def test_extract_text_from_sse_string_without_content(self) -> None:
        response = '\n'.join([
            'data: {"id":"","object":"chat.completion.chunk","choices":[],"usage":{"prompt_tokens":10,"completion_tokens":0,"total_tokens":10}}',
            'data: [DONE]',
        ])
        self.assertEqual(_extract_text(response), '')


if __name__ == "__main__":
    unittest.main()
