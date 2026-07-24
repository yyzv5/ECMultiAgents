"""Listing Agent Prompt 模板 + 平台规则字典。

M7.7 — Prompt 模板已统一抽出到 prompts/listing_prompts.py。

所有常量为字符串格式，供 listing_agent/graph.py import 使用。
"""

PLATFORM_RULES: dict[str, str] = {
    "Amazon": (
        "Amazon 平台规则:\n"
        "- 标题长度不超过 200 字符,禁止全大写、促销词(如 'Best Seller'/'#1')、特殊符号堆砌\n"
        "- 图片数量 1-9 张,主图必须纯白背景(255,255,255),禁止文字/水印/边框\n"
        "- 变体必须基于真实 SKU 差异(如 color/size),禁止用变体伪装关键词\n"
        "- 类目需选择最底层 leaf node,匹配商品实物形态\n"
        "- 禁止违规词:医疗功效词、对比词(如 'better than')、未授权品牌词"
    ),
    "Shopee": (
        "Shopee 平台规则:\n"
        "- 标题长度不超过 100 字符,鼓励本地化语言(按上架站点)\n"
        "- 图片数量 1-8 张,推荐 1:1 正方形,文件 < 5MB\n"
        "- 变体最多 50 个,价格区间合理\n"
        "- 类目必须与商品匹配,错放类目会被下架\n"
        "- 禁止违禁词:医疗、成人、武器、未经认证的保健品宣传词"
    ),
    "AliExpress": (
        "AliExpress 平台规则:\n"
        "- 标题长度不超过 128 字符,关键词精准但禁止堆砌\n"
        "- 图片数量 1-6 张,主图建议 800x800 以上\n"
        "- 变体属性必须与 SKU 一一对应\n"
        "- 类目匹配平台类目树(英文站用英文类目)\n"
        "- 禁止词:品牌侵权、医疗功效、夸大宣传、未授权商标"
    ),
}


TITLE_CHECK_PROMPT = """\
你是跨境电商 Listing 标题审核助手。基于下方平台规则,审核用户商品标题是否合规。
如果发现问题,按 JSON 数组返回每个问题;没有问题则返回空数组 []。
每个问题对象格式:
{{"field": "title", "rule": "<违反的具体规则名>", "detail": "<违规详情>", "suggestion": "<修改建议>"}}

平台规则:
{platform_rules}

商品标题: {title}
商品类目: {category}
商品属性: {attributes}

仅返回 JSON 数组,不要包裹 markdown 代码块或其他文字。"""


IMAGE_CHECK_PROMPT = """\
你是跨境电商 Listing 图片审核助手。基于下方平台规则,审核用户图片链接清单是否合规。
如果发现问题,按 JSON 数组返回每个问题;没有问题则返回空数组 []。
每个问题对象格式:
{{"field": "image_url", "rule": "<违反的具体规则名>", "detail": "<违规详情>", "suggestion": "<修改建议>"}}

平台规则:
{platform_rules}

商品图片链接数量: {image_count}
商品图片链接: {image_urls}

仅返回 JSON 数组,不要包裹 markdown 代码块或其他文字。"""


VARIATION_CHECK_PROMPT = """\
你是跨境电商 Listing 变体审核助手。基于下方平台规则,审核用户提交的变体信息是否完整合理。
如果发现问题,按 JSON 数组返回每个问题;没有问题则返回空数组 []。
每个问题对象格式:
{{"field": "variation", "rule": "<违反的具体规则名>", "detail": "<违规详情>", "suggestion": "<修改建议>"}}

平台规则:
{platform_rules}

变体数量: {variation_count}
变体信息: {variations}

仅返回 JSON 数组,不要包裹 markdown 代码块或其他文字。"""


CATEGORY_CHECK_PROMPT = """\
你是跨境电商 Listing 类目审核助手。基于下方平台规则,判断用户选择的类目与商品是否匹配。
如果发现问题,按 JSON 数组返回每个问题;没有问题则返回空数组 []。
每个问题对象格式:
{{"field": "category", "rule": "<违反的具体规则名>", "detail": "<违规详情>", "suggestion": "<修改建议>"}}

平台规则:
{platform_rules}

商品标题: {title}
商品类目: {category}
商品属性: {attributes}

仅返回 JSON 数组,不要包裹 markdown 代码块或其他文字。"""


COMPLIANCE_CHECK_PROMPT = """\
你是跨境电商 Listing 合规审核助手。基于下方平台规则,审核商品是否存在违规词、
知识产权风险或当地法规违规。
如果发现问题,按 JSON 数组返回每个问题;没有问题则返回空数组 []。
每个问题对象格式:
{{"field": "compliance", "rule": "<违反的具体规则名>", "detail": "<违规详情>", "suggestion": "<修改建议>"}}

平台规则:
{platform_rules}

商品标题: {title}
商品类目: {category}
商品属性: {attributes}

仅返回 JSON 数组,不要包裹 markdown 代码块或其他文字。"""


AUTO_FIX_PROMPT = """\
你是跨境电商 Listing 修复助手。基于下方用户反馈与发现的审核问题,
输出修复后的商品标题。仅输出修复后的标题文本,不要附加解释。

用户反馈: {feedback}
审核问题: {issues}
原标题: {title}

修复后的标题:"""


__all__ = [
    "AUTO_FIX_PROMPT",
    "CATEGORY_CHECK_PROMPT",
    "COMPLIANCE_CHECK_PROMPT",
    "IMAGE_CHECK_PROMPT",
    "PLATFORM_RULES",
    "TITLE_CHECK_PROMPT",
    "VARIATION_CHECK_PROMPT",
]
