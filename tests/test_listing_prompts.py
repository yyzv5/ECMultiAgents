"""Tests for listing_prompts — every constant importable + non-empty + content preserved."""

from __future__ import annotations

from backend.prompts.listing_prompts import (
    AUTO_FIX_PROMPT,
    CATEGORY_CHECK_PROMPT,
    COMPLIANCE_CHECK_PROMPT,
    IMAGE_CHECK_PROMPT,
    PLATFORM_RULES,
    TITLE_CHECK_PROMPT,
    VARIATION_CHECK_PROMPT,
)


class TestPlatformRules:
    """PLATFORM_RULES dict 可 import、结构正确。"""

    def test_import_and_is_dict(self):
        assert isinstance(PLATFORM_RULES, dict)
        assert len(PLATFORM_RULES) == 3

    def test_content_preserved(self):
        assert "Amazon" in PLATFORM_RULES
        assert "Shopee" in PLATFORM_RULES
        assert "AliExpress" in PLATFORM_RULES
        assert "200 字符" in PLATFORM_RULES["Amazon"]
        assert "100 字符" in PLATFORM_RULES["Shopee"]
        assert "128 字符" in PLATFORM_RULES["AliExpress"]


class TestTitleCheckPrompt:
    def test_import_and_not_empty(self):
        assert TITLE_CHECK_PROMPT
        assert isinstance(TITLE_CHECK_PROMPT, str)

    def test_content_preserved(self):
        assert "标题审核助手" in TITLE_CHECK_PROMPT
        assert "{platform_rules}" in TITLE_CHECK_PROMPT
        assert "{title}" in TITLE_CHECK_PROMPT


class TestImageCheckPrompt:
    def test_import_and_not_empty(self):
        assert IMAGE_CHECK_PROMPT
        assert isinstance(IMAGE_CHECK_PROMPT, str)

    def test_content_preserved(self):
        assert "图片审核助手" in IMAGE_CHECK_PROMPT
        assert "{image_count}" in IMAGE_CHECK_PROMPT
        assert "{image_urls}" in IMAGE_CHECK_PROMPT


class TestVariationCheckPrompt:
    def test_import_and_not_empty(self):
        assert VARIATION_CHECK_PROMPT
        assert isinstance(VARIATION_CHECK_PROMPT, str)

    def test_content_preserved(self):
        assert "变体审核助手" in VARIATION_CHECK_PROMPT
        assert "{variation_count}" in VARIATION_CHECK_PROMPT
        assert "{variations}" in VARIATION_CHECK_PROMPT


class TestCategoryCheckPrompt:
    def test_import_and_not_empty(self):
        assert CATEGORY_CHECK_PROMPT
        assert isinstance(CATEGORY_CHECK_PROMPT, str)

    def test_content_preserved(self):
        assert "类目审核助手" in CATEGORY_CHECK_PROMPT
        assert "{category}" in CATEGORY_CHECK_PROMPT
        assert "{title}" in CATEGORY_CHECK_PROMPT


class TestComplianceCheckPrompt:
    def test_import_and_not_empty(self):
        assert COMPLIANCE_CHECK_PROMPT
        assert isinstance(COMPLIANCE_CHECK_PROMPT, str)

    def test_content_preserved(self):
        assert "合规审核助手" in COMPLIANCE_CHECK_PROMPT
        assert "知识产权" in COMPLIANCE_CHECK_PROMPT
        assert "{category}" in COMPLIANCE_CHECK_PROMPT


class TestAutoFixPrompt:
    def test_import_and_not_empty(self):
        assert AUTO_FIX_PROMPT
        assert isinstance(AUTO_FIX_PROMPT, str)

    def test_content_preserved(self):
        assert "修复助手" in AUTO_FIX_PROMPT
        assert "{feedback}" in AUTO_FIX_PROMPT
        assert "{issues}" in AUTO_FIX_PROMPT
        assert "{title}" in AUTO_FIX_PROMPT
