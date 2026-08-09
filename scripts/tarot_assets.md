# 塔罗牌面资源映射表（v0.4.1）

## 图片资源（不入 Git——版权策略见 README「塔罗牌面版权」）

### 目录结构
```
frontend/public/images/tarot/
├── major/    # 22 张大阿卡纳（card_id 0-21）
│   ├── major-00.jpg  愚者
│   ├── major-01.jpg  魔术师
│   └── ... major-21.jpg  世界
└── minor/    # 56 张小阿卡纳（card_id 22-77）
    ├── minor-022.jpg  权杖王牌
    ├── minor-023.jpg  权杖2
    └── ... minor-077.jpg  星币国王
```

### 命名规则（对齐后端 card_id，前端 cardImageUrl 直接映射）
- 大阿卡纳：`major-{card_id:02d}.jpg`（0-21）
- 小阿卡纳：`minor-{card_id:03d}.jpg`（22-77）
- 后端 `app/data/tarot_cards.py` 的 `ALL_CARDS` 数组顺序 = card_id 顺序

### 当前来源
- **RWS 1909 公版**（当前全部 78 张）：下载自 GitHub `lalesleon13-hash/Tarot`
  （public domain Rider-Waite 牌面），脚本 `scripts/fetch_tarot_assets.py` 可复现
- **JOJO 第三季大阿卡纳（用户计划替换）**：覆盖 `major/major-XX.jpg` 即可，
  文件名不变则前端零改动。JOJO 与塔罗对应关系：
  | card_id | 牌 | JOJO 替身 |
  |---|---|---|
  | 00 | 愚者 | 空条承太郎（星之白金） |
  | 06 | 恋人 | 花京院典明（绿色法皇） |
  | 16 | 高塔 | 穆罕默德·阿布德尔（红色魔术师） |
  | 20 | 审判 | 伊奇（愚者） |
  | 21 | 世界 | DIO（世界） |
  （完整 22 张对应表可参考 JoJo 维基 "Stardust Crusaders Tarot" 条目）
