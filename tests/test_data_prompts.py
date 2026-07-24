"""Tests for data_prompts — every constant importable + non-empty + content preserved."""

from __future__ import annotations

from backend.prompts.data_prompts import (
    CLASSIFY_ANALYSIS_TYPE_PROMPT,
    ERROR_RESPONSE_PROMPT,
    EXTRACT_INTENT_PROMPT,
    FIX_SQL_PROMPT,
    GENERATE_REPORT_PROMPT,
    TEXT_TO_SQL_PROMPT,
)


class TestClassifyAnalysisTypePrompt:
    def test_import_and_not_empty(self):
        assert CLASSIFY_ANALYSIS_TYPE_PROMPT
        assert isinstance(CLASSIFY_ANALYSIS_TYPE_PROMPT, str)

    def test_content_preserved(self):
        assert "weekly_report" in CLASSIFY_ANALYSIS_TYPE_PROMPT
        assert "monthly_report" in CLASSIFY_ANALYSIS_TYPE_PROMPT
        assert "free_analysis" in CLASSIFY_ANALYSIS_TYPE_PROMPT
        assert "{query}" in CLASSIFY_ANALYSIS_TYPE_PROMPT


class TestExtractIntentPrompt:
    def test_import_and_not_empty(self):
        assert EXTRACT_INTENT_PROMPT
        assert isinstance(EXTRACT_INTENT_PROMPT, str)

    def test_content_preserved(self):
        assert "分析意图提取" in EXTRACT_INTENT_PROMPT
        assert "{query}" in EXTRACT_INTENT_PROMPT


class TestTextToSqlPrompt:
    def test_import_and_not_empty(self):
        assert TEXT_TO_SQL_PROMPT
        assert isinstance(TEXT_TO_SQL_PROMPT, str)

    def test_content_preserved(self):
        assert "SQL专家" in TEXT_TO_SQL_PROMPT
        assert "product_sales" in TEXT_TO_SQL_PROMPT
        assert "ad_performance" in TEXT_TO_SQL_PROMPT
        assert "{intent}" in TEXT_TO_SQL_PROMPT


class TestFixSqlPrompt:
    def test_import_and_not_empty(self):
        assert FIX_SQL_PROMPT
        assert isinstance(FIX_SQL_PROMPT, str)

    def test_content_preserved(self):
        assert "SQL修复专家" in FIX_SQL_PROMPT
        assert "{sql}" in FIX_SQL_PROMPT
        assert "{error}" in FIX_SQL_PROMPT


class TestGenerateReportPrompt:
    def test_import_and_not_empty(self):
        assert GENERATE_REPORT_PROMPT
        assert isinstance(GENERATE_REPORT_PROMPT, str)

    def test_content_preserved(self):
        assert "数据分析报告生成专家" in GENERATE_REPORT_PROMPT
        assert "{query}" in GENERATE_REPORT_PROMPT
        assert "{sql}" in GENERATE_REPORT_PROMPT
        assert "{result}" in GENERATE_REPORT_PROMPT


class TestErrorResponsePrompt:
    def test_import_and_not_empty(self):
        assert ERROR_RESPONSE_PROMPT
        assert isinstance(ERROR_RESPONSE_PROMPT, str)

    def test_content_preserved(self):
        assert "无法自动修复" in ERROR_RESPONSE_PROMPT
        assert "{error}" in ERROR_RESPONSE_PROMPT
        assert "{sql}" in ERROR_RESPONSE_PROMPT
