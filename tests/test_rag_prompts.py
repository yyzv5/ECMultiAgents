"""Tests for rag_prompts — every constant importable + non-empty + content preserved."""

from __future__ import annotations

from backend.prompts.rag_prompts import (
    GENERATE_ANSWER_PROMPT,
    QUERY_REWRITE_PROMPT,
    VALIDATE_QUESTION_PROMPT,
)


class TestQueryRewritePrompt:
    """QUERY_REWRITE_PROMPT 可 import、非空、内容正确。"""

    def test_import_and_not_empty(self):
        assert QUERY_REWRITE_PROMPT
        assert isinstance(QUERY_REWRITE_PROMPT, str)

    def test_content_preserved(self):
        assert "查询改写专家" in QUERY_REWRITE_PROMPT
        assert "{history}" in QUERY_REWRITE_PROMPT
        assert "{query}" in QUERY_REWRITE_PROMPT


class TestValidateQuestionPrompt:
    """VALIDATE_QUESTION_PROMPT 可 import、非空、内容正确。"""

    def test_import_and_not_empty(self):
        assert VALIDATE_QUESTION_PROMPT
        assert isinstance(VALIDATE_QUESTION_PROMPT, str)

    def test_content_preserved(self):
        assert "跨境电商运营相关" in VALIDATE_QUESTION_PROMPT
        assert "{query}" in VALIDATE_QUESTION_PROMPT
        assert "true 或 false" in VALIDATE_QUESTION_PROMPT


class TestGenerateAnswerPrompt:
    """GENERATE_ANSWER_PROMPT 可 import、非空、内容正确。"""

    def test_import_and_not_empty(self):
        assert GENERATE_ANSWER_PROMPT
        assert isinstance(GENERATE_ANSWER_PROMPT, str)

    def test_content_preserved(self):
        assert "跨境电商运营助手" in GENERATE_ANSWER_PROMPT
        assert "{context}" in GENERATE_ANSWER_PROMPT
        assert "{query}" in GENERATE_ANSWER_PROMPT
