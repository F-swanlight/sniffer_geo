#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
地球科学RSS监控系统 - 增强版
Enhanced Geoscience RSS Monitoring System with Zone Scoring

Features:
- RSSSourceFinder for automatic RSS source discovery
- Zone-based article scoring system for quality prioritization
- Dynamic phrase extraction for trend analysis
- Improved error handling and retry mechanisms
- Enhanced push content formatting with translation support
- Detailed statistics collection

Author: Enhanced by AI Assistant
Date: 2025
"""

import os
import sys
import logging
import json
import csv
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Set
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import feedparser
import requests
import jieba
import numpy as np
from bs4 import BeautifulSoup
from sklearn.feature_extraction.text import TfidfVectorizer
from googletrans import Translator
import pandas as pd
import pytz
from tenacity import retry, stop_after_attempt, wait_exponential
import yaml

# 配置路径
CONFIG_DIR = Path(__file__).parent.parent / "config"
DATA_DIR = Path(__file__).parent.parent / "data"
LOG_DIR = Path(__file__).parent.parent / "logs"

# 确保目录存在
LOG_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# 配置logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'sniffer.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class Article:
    """文章数据结构"""
    title: str
    link: str
    summary: str
    published: datetime
    source: str
    journal_zone: int = 4
    score: float = 0.0
    matched_keywords: List[str] = None
    
    def __post_init__(self):
        if self.matched_keywords is None:
            self.matched_keywords = []

@dataclass 
class JournalInfo:
    """期刊信息数据结构"""
    name: str
    impact_factor: float
    zone: int
    rss_url: str

class RSSSourceFinder:
    """RSS源自动发现器"""
    
    def __init__(self):
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def discover_rss_feeds(self, base_url: str) -> List[str]:
        """从网站发现RSS源"""
        try:
            response = self.session.get(base_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            rss_feeds = []
            
            # 查找RSS链接
            for link in soup.find_all('link', type='application/rss+xml'):
                href = link.get('href')
                if href:
                    if href.startswith('/'):
                        href = base_url.rstrip('/') + href
                    rss_feeds.append(href)
                    
            # 查找常见RSS模式
            common_patterns = ['/rss', '/feed', '/feeds', '.rss', '.xml']
            for pattern in common_patterns:
                test_url = base_url.rstrip('/') + pattern
                if self._test_rss_url(test_url):
                    rss_feeds.append(test_url)
                    
            return list(set(rss_feeds))
            
        except Exception as e:
            logger.warning(f"无法从 {base_url} 发现RSS源: {e}")
            return []
    
    def _test_rss_url(self, url: str) -> bool:
        """测试URL是否为有效的RSS源"""
        try:
            response = self.session.get(url, timeout=5)
            if response.status_code == 200:
                # 简单检查是否包含RSS内容
                content = response.text.lower()
                return 'rss' in content or 'feed' in content or '<item>' in content
        except:
            pass
        return False

class DynamicPhraseExtractor:
    """动态短语提取器"""
    
    def __init__(self, min_length=2, max_length=4):
        self.min_length = min_length
        self.max_length = max_length
        self.vectorizer = TfidfVectorizer(
            ngram_range=(min_length, max_length),
            max_features=1000,
            stop_words='english'
        )
        
    def extract_phrases(self, texts: List[str], top_k=20) -> List[Tuple[str, float]]:
        """从文本中提取热门短语"""
        try:
            if not texts:
                return []
                
            # 预处理文本
            processed_texts = []
            for text in texts:
                # 移除特殊字符，保留字母数字和空格
                clean_text = re.sub(r'[^\w\s]', ' ', text.lower())
                processed_texts.append(clean_text)
            
            # TF-IDF向量化
            tfidf_matrix = self.vectorizer.fit_transform(processed_texts)
            feature_names = self.vectorizer.get_feature_names_out()
            
            # 计算平均TF-IDF分数
            mean_scores = np.array(tfidf_matrix.mean(axis=0)).flatten()
            
            # 获取top k短语
            top_indices = mean_scores.argsort()[-top_k:][::-1]
            phrases = [(feature_names[i], mean_scores[i]) for i in top_indices if mean_scores[i] > 0]
            
            return phrases
            
        except Exception as e:
            logger.error(f"短语提取失败: {e}")
            return []

class TranslationService:
    """翻译服务"""
    
    def __init__(self):
        self.translator = Translator()
        self.cache = {}
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
    def translate_text(self, text: str, target_lang='zh-cn') -> str:
        """翻译文本"""
        if not text or len(text.strip()) == 0:
            return text
            
        # 检查缓存
        cache_key = f"{text[:100]}_{target_lang}"
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        try:
            result = self.translator.translate(text, dest=target_lang)
            translated = result.text
            self.cache[cache_key] = translated
            return translated
        except Exception as e:
            logger.warning(f"翻译失败 '{text[:50]}...': {e}")
            return text

class StatisticsCollector:
    """统计数据收集器"""
    
    def __init__(self):
        self.stats_file = DATA_DIR / "statistics.json"
        self.daily_stats = defaultdict(int)
        self.load_stats()
        
    def load_stats(self):
        """加载历史统计数据"""
        try:
            if self.stats_file.exists():
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    self.historical_stats = json.load(f)
            else:
                self.historical_stats = {}
        except Exception as e:
            logger.error(f"加载统计数据失败: {e}")
            self.historical_stats = {}
    
    def record_event(self, event_type: str, value=1):
        """记录事件"""
        self.daily_stats[event_type] += value
        
    def record_journal_access(self, journal_name: str):
        """记录期刊访问"""
        self.record_event(f"journal_{journal_name}")
        
    def record_keyword_match(self, keyword: str):
        """记录关键词匹配"""
        self.record_event(f"keyword_{keyword}")
        
    def save_daily_stats(self):
        """保存每日统计"""
        today = datetime.now().strftime('%Y-%m-%d')
        self.historical_stats[today] = dict(self.daily_stats)
        
        try:
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.historical_stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存统计数据失败: {e}")
    
    def get_summary(self) -> Dict:
        """获取统计摘要"""
        return {
            'daily_stats': dict(self.daily_stats),
            'total_days': len(self.historical_stats),
            'last_update': datetime.now().isoformat()
        }

class EnhancedGeoSniffer:
    """增强版地球科学RSS监控器"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.journals_info = self._load_journals_info()
        self.rss_finder = RSSSourceFinder()
        self.phrase_extractor = DynamicPhraseExtractor()
        self.translator = TranslationService() if self.config.get('ENABLE_TRANSLATION', False) else None
        self.stats = StatisticsCollector()
        
        # 设置jieba分词
        jieba.setLogLevel(logging.WARNING)
        
        logger.info("增强版地球科学RSS监控器初始化完成")
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """加载配置"""
        if config_path is None:
            config_path = CONFIG_DIR / "config.py"
            
        if not os.path.exists(config_path):
            logger.warning(f"配置文件不存在: {config_path}")
            return self._get_default_config()
            
        try:
            # 动态导入配置模块
            spec = {}
            with open(config_path, 'r', encoding='utf-8') as f:
                exec(f.read(), spec)
            
            # 移除内置变量
            config = {k: v for k, v in spec.items() if not k.startswith('__')}
            logger.info(f"已加载配置文件: {config_path}")
            return config
            
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'WECHAT_WEBHOOK': '',
            'RSS_FEEDS': [],
            'KEYWORDS': ['geology', 'geoscience', 'earth science'],
            'ZONE_SCORING_ENABLED': True,
            'ZONE_WEIGHTS': {1: 10.0, 2: 7.0, 3: 4.0, 4: 2.0},
            'DYNAMIC_PHRASE_EXTRACTION': True,
            'ENABLE_TRANSLATION': False,
            'MAX_RETRIES': 3,
            'RETRY_DELAY': 2,
            'ENABLE_DETAILED_STATS': True
        }
    
    def _load_journals_info(self) -> Dict[str, JournalInfo]:
        """加载期刊信息"""
        journals_file = DATA_DIR / "journals_1-260.csv"
        journals_info = {}
        
        try:
            if journals_file.exists():
                df = pd.read_csv(journals_file)
                for _, row in df.iterrows():
                    journal_info = JournalInfo(
                        name=row['journal_name'],
                        impact_factor=float(row['impact_factor']),
                        zone=int(row['zone']),
                        rss_url=row['rss_url']
                    )
                    journals_info[journal_info.name] = journal_info
                logger.info(f"已加载 {len(journals_info)} 个期刊信息")
            else:
                logger.warning(f"期刊信息文件不存在: {journals_file}")
                
        except Exception as e:
            logger.error(f"加载期刊信息失败: {e}")
            
        return journals_info
    
    def get_rss_sources(self) -> List[Tuple[str, int]]:
        """获取RSS源列表，返回(url, zone)元组"""
        sources = []
        
        if self.config.get('ZONE_SCORING_ENABLED', True) and self.journals_info:
            # 使用期刊信息中的RSS源
            for journal_info in self.journals_info.values():
                sources.append((journal_info.rss_url, journal_info.zone))
        else:
            # 使用配置文件中的RSS源
            for url in self.config.get('RSS_FEEDS', []):
                sources.append((url, 4))  # 默认为zone 4
                
        logger.info(f"获取到 {len(sources)} 个RSS源")
        return sources
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_rss_feed(self, url: str) -> Optional[feedparser.FeedParserDict]:
        """获取RSS feed"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            
            if feed.bozo:
                logger.warning(f"RSS feed解析警告 {url}: {feed.bozo_exception}")
            
            return feed
            
        except Exception as e:
            logger.error(f"获取RSS feed失败 {url}: {e}")
            self.stats.record_event("rss_fetch_error")
            return None
    
    def extract_articles(self, feed: feedparser.FeedParserDict, source_info: Tuple[str, int]) -> List[Article]:
        """从RSS feed中提取文章"""
        articles = []
        url, zone = source_info
        
        try:
            source_name = feed.feed.get('title', url)
            self.stats.record_journal_access(source_name)
            
            for entry in feed.entries:
                try:
                    # 解析发布时间
                    pub_date = self._parse_date(entry)
                    
                    # 过滤24小时内的文章
                    if self._is_recent_article(pub_date):
                        article = Article(
                            title=entry.get('title', ''),
                            link=entry.get('link', ''),
                            summary=entry.get('summary', ''),
                            published=pub_date,
                            source=source_name,
                            journal_zone=zone
                        )
                        articles.append(article)
                        
                except Exception as e:
                    logger.warning(f"解析文章失败: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"提取文章失败: {e}")
            
        return articles
    
    def _parse_date(self, entry) -> datetime:
        """解析文章发布日期"""
        try:
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                return datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                return datetime(*entry.updated_parsed[:6])
            else:
                return datetime.now()
        except:
            return datetime.now()
    
    def _is_recent_article(self, pub_date: datetime, hours=24) -> bool:
        """判断是否为最近的文章"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return pub_date >= cutoff
    
    def filter_articles_by_keywords(self, articles: List[Article]) -> List[Article]:
        """根据关键词过滤文章"""
        keywords = self.config.get('KEYWORDS', [])
        if not keywords:
            return articles
            
        filtered_articles = []
        
        for article in articles:
            text_to_search = f"{article.title} {article.summary}".lower()
            matched_keywords = []
            
            for keyword in keywords:
                if keyword.lower() in text_to_search:
                    matched_keywords.append(keyword)
                    self.stats.record_keyword_match(keyword)
                    
            if matched_keywords:
                article.matched_keywords = matched_keywords
                filtered_articles.append(article)
                
        logger.info(f"关键词过滤后剩余 {len(filtered_articles)} 篇文章")
        return filtered_articles
    
    def calculate_article_scores(self, articles: List[Article]) -> List[Article]:
        """计算文章得分"""
        zone_weights = self.config.get('ZONE_WEIGHTS', {1: 10.0, 2: 7.0, 3: 4.0, 4: 2.0})
        
        for article in articles:
            # 基础分数基于期刊分区
            base_score = zone_weights.get(article.journal_zone, 1.0)
            
            # 关键词匹配奖励
            keyword_bonus = len(article.matched_keywords) * 2.0
            
            # 时间衰减（越新的文章分数越高）
            time_factor = self._calculate_time_factor(article.published)
            
            article.score = base_score + keyword_bonus + time_factor
            
        # 按分数排序
        articles.sort(key=lambda x: x.score, reverse=True)
        return articles
    
    def _calculate_time_factor(self, pub_date: datetime) -> float:
        """计算时间因子"""
        hours_ago = (datetime.now() - pub_date).total_seconds() / 3600
        # 24小时内的文章时间奖励递减
        if hours_ago <= 24:
            return 5.0 * (1 - hours_ago / 24)
        return 0.0
    
    def generate_trending_phrases(self, articles: List[Article]) -> List[Tuple[str, float]]:
        """生成热门短语"""
        if not self.config.get('DYNAMIC_PHRASE_EXTRACTION', False):
            return []
            
        texts = []
        for article in articles:
            texts.append(f"{article.title} {article.summary}")
            
        return self.phrase_extractor.extract_phrases(texts, top_k=20)
    
    def format_message(self, articles: List[Article], trending_phrases: List[Tuple[str, float]]) -> str:
        """格式化推送消息"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        message = f"【地质前沿每日推送】{today}\n\n"
        
        if articles:
            message += f"🔬 今日精选文章 ({len(articles)}篇):\n\n"
            
            for i, article in enumerate(articles[:10], 1):  # 最多显示10篇
                title = article.title
                
                # 翻译标题（如果启用）
                if self.translator and self.config.get('TRANSLATE_TO_CHINESE', False):
                    try:
                        translated_title = self.translator.translate_text(title)
                        if translated_title != title:
                            title = f"{title}\n   译: {translated_title}"
                    except:
                        pass
                
                zone_emoji = {1: "⭐⭐⭐", 2: "⭐⭐", 3: "⭐", 4: ""}
                zone_indicator = zone_emoji.get(article.journal_zone, "")
                
                message += f"{i}. {title} {zone_indicator}\n"
                message += f"   {article.link}\n"
                message += f"   来源: {article.source} | 分数: {article.score:.1f}\n"
                
                if article.matched_keywords:
                    message += f"   匹配关键词: {', '.join(article.matched_keywords)}\n"
                    
                message += "\n"
        else:
            message += "今日暂无匹配的文章\n\n"
        
        # 添加热门短语
        if trending_phrases:
            message += "【今日热点短语】\n"
            for phrase, score in trending_phrases[:10]:
                message += f"• {phrase} ({score:.3f})\n"
            message += "\n"
        
        # 添加统计信息
        if self.config.get('ENABLE_DETAILED_STATS', False):
            stats_summary = self.stats.get_summary()
            message += f"【统计信息】\n"
            message += f"处理文章: {stats_summary['daily_stats'].get('articles_processed', 0)}\n"
            message += f"RSS源访问: {sum(v for k, v in stats_summary['daily_stats'].items() if k.startswith('journal_'))}\n"
            
        return message
    
    def send_wechat_message(self, message: str) -> bool:
        """发送企业微信消息"""
        webhook_url = self.config.get('WECHAT_WEBHOOK', '')
        if not webhook_url:
            logger.warning("未配置企业微信Webhook地址")
            return False
            
        payload = {
            "msgtype": "text",
            "text": {
                "content": message
            }
        }
        
        try:
            response = requests.post(webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get('errcode') == 0:
                logger.info("企业微信消息发送成功")
                self.stats.record_event("wechat_success")
                return True
            else:
                logger.error(f"企业微信消息发送失败: {result}")
                self.stats.record_event("wechat_error")
                return False
                
        except Exception as e:
            logger.error(f"发送企业微信消息异常: {e}")
            self.stats.record_event("wechat_error")
            return False
    
    def run_daily_scan(self):
        """执行每日扫描"""
        logger.info("开始每日RSS扫描")
        start_time = time.time()
        
        try:
            # 获取RSS源
            rss_sources = self.get_rss_sources()
            if not rss_sources:
                logger.warning("没有可用的RSS源")
                return
            
            all_articles = []
            
            # 获取所有文章
            for url, zone in rss_sources:
                logger.info(f"正在处理RSS源: {url}")
                
                feed = self.fetch_rss_feed(url)
                if feed:
                    articles = self.extract_articles(feed, (url, zone))
                    all_articles.extend(articles)
                    self.stats.record_event("rss_success")
                    
                time.sleep(1)  # 避免请求过快
            
            self.stats.record_event("articles_processed", len(all_articles))
            logger.info(f"共获取到 {len(all_articles)} 篇文章")
            
            # 关键词过滤
            filtered_articles = self.filter_articles_by_keywords(all_articles)
            
            # 计算分数并排序
            scored_articles = self.calculate_article_scores(filtered_articles)
            
            # 生成热门短语
            trending_phrases = self.generate_trending_phrases(scored_articles)
            
            # 格式化消息
            message = self.format_message(scored_articles, trending_phrases)
            
            # 发送消息
            if scored_articles or self.config.get('SEND_EMPTY_REPORTS', False):
                self.send_wechat_message(message)
            
            # 保存统计数据
            self.stats.save_daily_stats()
            
            elapsed_time = time.time() - start_time
            logger.info(f"每日扫描完成，耗时 {elapsed_time:.2f} 秒")
            
        except Exception as e:
            logger.error(f"每日扫描失败: {e}")
            self.stats.record_event("scan_error")
            raise

def main():
    """主函数"""
    try:
        # 检查配置文件
        config_file = CONFIG_DIR / "config.py"
        if not config_file.exists():
            logger.warning(f"配置文件不存在: {config_file}")
            logger.info("请复制 config.py.example 为 config.py 并填入正确的配置")
            return
        
        # 创建并运行监控器
        sniffer = EnhancedGeoSniffer()
        sniffer.run_daily_scan()
        
    except KeyboardInterrupt:
        logger.info("用户中断程序")
    except Exception as e:
        logger.error(f"程序运行异常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()