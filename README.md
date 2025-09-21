# 地球科学RSS监控系统 (sniffer_geo)

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📋 项目简介

地球科学RSS监控系统是一个自动化工具，用于监控国际主流地质科学期刊的RSS源，基于预设关键词筛选高质量文章，并每日自动推送到企业微信群。

### 🎯 核心功能

- **多源RSS监控**: 覆盖Nature Geoscience、Science、Geology等顶级期刊
- **智能关键词筛选**: 支持中英文关键词，包括碳酸盐岩、微生物矿化、天然氢等前沿研究领域
- **企业微信推送**: 自动格式化内容并推送到指定微信群
- **热点词汇统计**: 统计每日热门研究方向
- **后台稳定运行**: 支持nohup后台运行和cron定时任务

### 🚀 新增强化功能

- **期刊分区评分系统**: 根据期刊影响因子和分区自动评分文章质量
- **RSS源自动发现**: RSSSourceFinder类自动发现新的期刊RSS源
- **动态短语提取**: 基于TF-IDF的热门趋势短语分析
- **增强错误处理**: 带重试机制的稳定网络请求
- **翻译支持**: 可选的中英文标题翻译功能
- **详细统计数据**: 全面的使用统计和性能监控

### 📊 监控期刊范围

- Nature Geoscience
- Science Magazine
- Geology (GSA)
- Earth and Planetary Science Letters
- Geochimica et Cosmochimica Acta
- Frontiers in Earth Science
- EOS
- AGU Publications
- arXiv (地球物理相关)
- 科学网地球科学频道

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Linux服务器 (推荐Ubuntu)
- 企业微信机器人webhook

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/Ken-Lee-79/sniffer_geo.git
cd sniffer_geo
```

2. **创建虚拟环境**
```bash
python3 -m venv geo_rss_env
source geo_rss_env/bin/activate
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

4. **配置企业微信Webhook**
```bash
cp config/config.py.example config/config.py
# 编辑config.py，填入你的webhook地址
```

5. **运行测试**
```bash
# 运行增强版（推荐）
python src/geo_daily_sniffer_with_zone_scoring.py

# 或运行原版兼容模式
python src/geo_daily_sniffer.py
```

## ⚙️ 配置说明

### config/config.py

```python
# 企业微信机器人Webhook地址
WECHAT_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"

# RSS源列表 (可自定义添加)
RSS_FEEDS = [
    "https://www.nature.com/ngeo.rss",
    "https://www.sciencemag.org/rss/current.xml",
    # ... 更多RSS源
]

# 关键词配置 (支持正则表达式)
KEYWORDS = [
    "碳酸盐岩", "carbonate", 
    "微生物矿化", "microbialite",
    "天然氢", "natural hydrogen",
    # ... 更多关键词
]

# 新增强化配置
# Zone scoring settings
ZONE_SCORING_ENABLED = True
ZONE_WEIGHTS = {
    1: 10.0,  # Top tier journals (Nature, Science)
    2: 7.0,   # High impact journals
    3: 4.0,   # Medium impact journals  
    4: 2.0,   # Lower tier journals
}

# 动态短语提取设置
DYNAMIC_PHRASE_EXTRACTION = True
ENABLE_TRANSLATION = True
ENABLE_DETAILED_STATS = True
```

## 📅 定时运行设置

### 方法一: Cron定时任务 (推荐)

```bash
# 编辑crontab
crontab -e

# 添加每日7:00自动运行（增强版）
0 7 * * * /path/to/geo_rss_env/bin/python /path/to/sniffer_geo/src/geo_daily_sniffer_with_zone_scoring.py >> /path/to/logs/sniffer.log 2>&1
```

### 方法二: 后台持续运行

```bash
# 使用nohup后台运行（增强版）
nohup python src/geo_daily_sniffer_with_zone_scoring.py > logs/sniffer.log 2>&1 &

# 查看运行状态
tail -f logs/sniffer.log
```

## 📊 使用效果

### 推送内容示例
```
【地质前沿每日推送】2025-01-20

🔬 今日精选文章 (3篇):

1. Carbonate platform evolution during the Cambrian explosion ⭐⭐⭐
https://www.nature.com/articles/s41561-024-xxxxx
   译: 寒武纪大爆发期间碳酸盐岩台地演化
来源: Nature Geoscience | 分数: 15.2
匹配关键词: carbonate, evolution

2. Natural hydrogen seepage in ophiolite complexes ⭐⭐
https://www.sciencemag.org/doi/10.1126/science.xxxxx
摘要: 蛇绿岩杂岩中天然氢气渗漏的地球化学特征...

【今日热点短语】
• carbonate platform (0.156)
• hydrogen seepage (0.142)
• geochemical signature (0.128)

【统计信息】
处理文章: 45
RSS源访问: 21
carbonate: 5
hydrogen: 3
geochemistry: 2
```

## 🛠️ 故障排除

### 常见问题

1. **RSS源403错误**: 添加User-Agent头部或配置代理
2. **微信推送失败**: 检查webhook地址和网络连接
3. **筛选结果为空**: 调整关键词或时间过滤条件

### 日志监控

```bash
# 实时查看日志
tail -f logs/sniffer.log

# 查看错误信息
grep ERROR logs/sniffer.log
```

## 📈 扩展功能

- [x] ~~支持多个微信群推送~~ (已实现)
- [x] ~~文章去重和相似度检测~~ (通过分区评分实现)
- [x] ~~期刊质量评估~~ (已实现分区评分系统)
- [ ] 添加邮件通知功能
- [ ] Web界面管理关键词
- [ ] 数据可视化dashboard
- [ ] 更多语言翻译支持
- [ ] 机器学习文章推荐

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 📞 联系方式

- GitHub: [@Ken-Lee-79](https://github.com/Ken-Lee-79)
- 项目链接: [https://github.com/Ken-Lee-79/sniffer_geo](https://github.com/Ken-Lee-79/sniffer_geo)

---

⭐ 如果这个项目对你有帮助，请给个Star支持！
