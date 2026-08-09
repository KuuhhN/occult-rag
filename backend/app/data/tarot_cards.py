"""标准 78 张塔罗牌数据（RWS 体系）

22 张大阿卡纳（Major Arcana）+ 56 张小阿卡纳（Minor Arcana）。
牌意解读不在此处硬编码——由 /tarot/draw 通过 RAG 从知识库
（塔罗冥想等书籍的精排版）检索生成，保证解读有据可依。
"""

# 大阿卡纳：序号 0-21
MAJOR_ARCANA = [
    {"id": 0, "name_cn": "愚者", "name_en": "The Fool"},
    {"id": 1, "name_cn": "魔术师", "name_en": "The Magician"},
    {"id": 2, "name_cn": "女祭司", "name_en": "The High Priestess"},
    {"id": 3, "name_cn": "女皇", "name_en": "The Empress"},
    {"id": 4, "name_cn": "皇帝", "name_en": "The Emperor"},
    {"id": 5, "name_cn": "教皇", "name_en": "The Hierophant"},
    {"id": 6, "name_cn": "恋人", "name_en": "The Lovers"},
    {"id": 7, "name_cn": "战车", "name_en": "The Chariot"},
    {"id": 8, "name_cn": "力量", "name_en": "Strength"},
    {"id": 9, "name_cn": "隐士", "name_en": "The Hermit"},
    {"id": 10, "name_cn": "命运之轮", "name_en": "Wheel of Fortune"},
    {"id": 11, "name_cn": "正义", "name_en": "Justice"},
    {"id": 12, "name_cn": "倒吊人", "name_en": "The Hanged Man"},
    {"id": 13, "name_cn": "死神", "name_en": "Death"},
    {"id": 14, "name_cn": "节制", "name_en": "Temperance"},
    {"id": 15, "name_cn": "恶魔", "name_en": "The Devil"},
    {"id": 16, "name_cn": "高塔", "name_en": "The Tower"},
    {"id": 17, "name_cn": "星星", "name_en": "The Star"},
    {"id": 18, "name_cn": "月亮", "name_en": "The Moon"},
    {"id": 19, "name_cn": "太阳", "name_en": "The Sun"},
    {"id": 20, "name_cn": "审判", "name_en": "Judgement"},
    {"id": 21, "name_cn": "世界", "name_en": "The World"},
]

# 小阿卡纳：4 花色 × 14（王牌-10 + 侍从/骑士/王后/国王）
_SUITS = [
    {"suit_cn": "权杖", "suit_en": "Wands", "element": "火"},
    {"suit_cn": "圣杯", "suit_en": "Cups", "element": "水"},
    {"suit_cn": "宝剑", "suit_en": "Swords", "element": "风"},
    {"suit_cn": "星币", "suit_en": "Pentacles", "element": "土"},
]

_RANK_CN = {1: "王牌", 11: "侍从", 12: "骑士", 13: "王后", 14: "国王"}

MINOR_ARCANA = []
_minor_id = 22
for s in _SUITS:
    for num in range(1, 15):
        if num in _RANK_CN:
            name_cn = f"{s['suit_cn']}{_RANK_CN[num]}"
            name_en = f"{_RANK_CN[num]} of {s['suit_en']}"
        else:
            name_cn = f"{s['suit_cn']}{num}"
            name_en = f"{num} of {s['suit_en']}"
        MINOR_ARCANA.append(
            {"id": _minor_id, "name_cn": name_cn, "name_en": name_en,
             "arcana": "minor", "suit": s["suit_cn"], "element": s["element"]}
        )
        _minor_id += 1

ALL_CARDS = MAJOR_ARCANA + MINOR_ARCANA


def get_card(card_id: int) -> dict:
    """按 id 取牌（不存在返回 None）"""
    for c in ALL_CARDS:
        if c["id"] == card_id:
            return c
    return None


def search_cards(keyword: str) -> list:
    """按中/英文名模糊搜索（供检索 query 构造用）"""
    kw = keyword.lower()
    return [c for c in ALL_CARDS if kw in c["name_cn"].lower() or kw in c["name_en"].lower()]
