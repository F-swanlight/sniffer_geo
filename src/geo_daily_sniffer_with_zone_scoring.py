#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
地球科学RSS监控系统 - 带区域评分的每日监控器
GeoScience RSS Sniffer with Zone Scoring - Daily Monitor

功能改进版本：
1. 单次推送最多6条内容（从原来的3条增加到6条）
2. 不显示文章摘要
3. 当文章超过6条时，分两次推送，第二次推送不超过6条
4. 当当日新文章不足6条时，自动从之前未推送的队列中补充文章

Author: F-swanlight
Date: 2025-01-20
"""

import os
import sys
import json
import time
import logging
import requests
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import pickle

# 添加配置路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'config'))

# 核心常量配置
MAX_DAILY_PUSH = 6  # 修改：从3改为6，单次最多推送6条内容
MAX_SECOND_PUSH = 6  # 第二次推送最多6条
MIN_ARTICLES_FOR_PUSH = 1  # 最少推送文章数量

# 数据持久化文件
HISTORICAL_QUEUE_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'historical_queue.pkl')
PUSHED_ARTICLES_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'pushed_articles.pkl')

@dataclass
class Article:
    """文章数据结构"""
    title: str
    link: str
    summary: str
    published: str
    source: str
    keywords_matched: List[str]
    score: float = 0.0
    zone_score: float = 0.0
    is_pushed: bool = False
    push_date: Optional[str] = None

class RSSMonitor:
    """RSS监控器主类"""
    
    def __init__(self):
        self.setup_logging()
        self.load_config()
        self.historical_queue: List[Article] = []
        self.pushed_articles: List[str] = []  # 存储已推送文章的链接
        self.load_historical_data()
        
    def setup_logging(self):
        """设置日志"""
        log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'sniffer.log'), encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_config(self):
        """加载配置"""
        try:
            import config
            self.wechat_webhook = getattr(config, 'WECHAT_WEBHOOK', '')
            self.rss_feeds = getattr(config, 'RSS_FEEDS', self.get_default_feeds())
            self.keywords = getattr(config, 'KEYWORDS', self.get_default_keywords())
        except ImportError:
            self.logger.warning("配置文件不存在，使用默认配置")
            self.wechat_webhook = ''
            self.rss_feeds = self.get_default_feeds()
            self.keywords = self.get_default_keywords()
            
    def get_default_feeds(self) -> List[str]:
        """获取默认RSS源"""
        return [
            "https://www.nature.com/ngeo.rss",
            "https://www.sciencemag.org/rss/current.xml",
            "https://pubs.geoscienceworld.org/rss/geology/current.xml",
            "https://www.frontiersin.org/research-topics/rss",
        ]
        
    def get_default_keywords(self) -> List[str]:
        """获取默认关键词"""
        return [
            "carbonate", "碳酸盐岩", "limestone", "dolomite",
            "microbialite", "微生物矿化", "stromatolite", "thrombolite",
            "natural hydrogen", "天然氢", "hydrogen seepage",
            "geochemistry", "地球化学", "isotope", "同位素",
            "sedimentology", "沉积学", "paleontology", "古生物学",
        ]
        
    def load_historical_data(self):
        """加载历史数据"""
        data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        # 加载历史队列
        if os.path.exists(HISTORICAL_QUEUE_FILE):
            try:
                with open(HISTORICAL_QUEUE_FILE, 'rb') as f:
                    queue_data = pickle.load(f)
                    self.historical_queue = [Article(**item) if isinstance(item, dict) else item for item in queue_data]
                self.logger.info(f"加载历史队列: {len(self.historical_queue)} 篇文章")
            except Exception as e:
                self.logger.error(f"加载历史队列失败: {e}")
                self.historical_queue = []
                
        # 加载已推送文章列表
        if os.path.exists(PUSHED_ARTICLES_FILE):
            try:
                with open(PUSHED_ARTICLES_FILE, 'rb') as f:
                    self.pushed_articles = pickle.load(f)
                self.logger.info(f"加载已推送文章记录: {len(self.pushed_articles)} 篇")
            except Exception as e:
                self.logger.error(f"加载已推送文章记录失败: {e}")
                self.pushed_articles = []
                
    def save_historical_data(self):
        """保存历史数据"""
        try:
            # 保存历史队列
            with open(HISTORICAL_QUEUE_FILE, 'wb') as f:
                queue_data = [asdict(article) for article in self.historical_queue]
                pickle.dump(queue_data, f)
                
            # 保存已推送文章列表
            with open(PUSHED_ARTICLES_FILE, 'wb') as f:
                pickle.dump(self.pushed_articles, f)
                
            self.logger.info("历史数据保存成功")
        except Exception as e:
            self.logger.error(f"保存历史数据失败: {e}")
            
    def fetch_rss_articles(self) -> List[Article]:
        """获取RSS文章"""
        all_articles = []
        today = datetime.now().date()
        
        for feed_url in self.rss_feeds:
            try:
                self.logger.info(f"正在获取RSS源: {feed_url}")
                
                # 设置请求头
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                response = requests.get(feed_url, headers=headers, timeout=30)
                response.raise_for_status()
                
                feed = feedparser.parse(response.content)
                source_name = feed.feed.get('title', feed_url)
                
                for entry in feed.entries:
                    # 检查发布时间（只处理今日文章）
                    pub_date = self.parse_publish_date(entry)
                    if pub_date and pub_date.date() != today:
                        continue
                        
                    # 检查关键词匹配
                    matched_keywords = self.check_keywords(entry)
                    if not matched_keywords:
                        continue
                        
                    # 跳过已推送的文章
                    if entry.link in self.pushed_articles:
                        continue
                        
                    article = Article(
                        title=entry.title,
                        link=entry.link,
                        summary=entry.get('summary', ''),
                        published=pub_date.isoformat() if pub_date else '',
                        source=source_name,
                        keywords_matched=matched_keywords,
                        score=len(matched_keywords),
                        zone_score=self.calculate_zone_score(entry, matched_keywords)
                    )
                    
                    all_articles.append(article)
                    
            except Exception as e:
                self.logger.error(f"获取RSS源失败 {feed_url}: {e}")
                continue
                
        self.logger.info(f"今日共获取到 {len(all_articles)} 篇符合条件的新文章")
        return all_articles
        
    def parse_publish_date(self, entry) -> Optional[datetime]:
        """解析发布时间"""
        try:
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                return datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                return datetime(*entry.updated_parsed[:6])
            elif hasattr(entry, 'published'):
                from dateutil.parser import parse
                return parse(entry.published)
        except Exception:
            pass
        return None
        
    def check_keywords(self, entry) -> List[str]:
        """检查关键词匹配"""
        content = f"{entry.title} {entry.get('summary', '')}".lower()
        matched = []
        
        for keyword in self.keywords:
            if keyword.lower() in content:
                matched.append(keyword)
                
        return matched
        
    def calculate_zone_score(self, entry, matched_keywords: List[str]) -> float:
        """计算区域评分"""
        base_score = len(matched_keywords)
        
        # 根据来源加权
        source_weights = {
            'nature': 3.0,
            'science': 3.0,
            'geology': 2.5,
            'earth': 2.0,
            'geochemistry': 2.0,
        }
        
        source = entry.get('source', '').lower()
        weight = 1.0
        for key, value in source_weights.items():
            if key in source:
                weight = value
                break
                
        return base_score * weight
        
    def format_article_for_push(self, article: Article) -> str:
        """格式化文章用于推送（移除摘要部分）"""
        # 修改：移除摘要部分，只保留标题和链接
        return f"{article.title}\n{article.link}"
        
    def get_backfill_articles(self, needed_count: int) -> List[Article]:
        """从历史队列中获取补充文章"""
        if needed_count <= 0:
            return []
            
        # 过滤未推送的文章，按评分排序
        available_articles = [
            article for article in self.historical_queue
            if not article.is_pushed and article.link not in self.pushed_articles
        ]
        
        # 按总评分降序排序
        available_articles.sort(key=lambda x: x.zone_score + x.score, reverse=True)
        
        # 取所需数量
        backfill_articles = available_articles[:needed_count]
        
        self.logger.info(f"从历史队列中补充了 {len(backfill_articles)} 篇文章")
        return backfill_articles
        
    def process_daily_articles(self) -> Tuple[List[List[Article]], Dict[str, int]]:
        """处理每日文章，返回推送批次和关键词统计"""
        # 获取今日新文章
        today_articles = self.fetch_rss_articles()
        
        # 更新历史队列
        self.historical_queue.extend(today_articles)
        
        # 按评分排序今日文章
        today_articles.sort(key=lambda x: x.zone_score + x.score, reverse=True)
        
        push_batches = []
        
        if len(today_articles) <= MAX_DAILY_PUSH:
            # 当日文章不足MAX_DAILY_PUSH条，需要补充
            needed_count = MAX_DAILY_PUSH - len(today_articles)
            backfill_articles = self.get_backfill_articles(needed_count)
            
            # 合并文章列表
            combined_articles = today_articles + backfill_articles
            
            if combined_articles:
                push_batches.append(combined_articles)
                
        else:
            # 当日文章超过MAX_DAILY_PUSH条，需要分批推送
            # 第一批：前MAX_DAILY_PUSH条
            first_batch = today_articles[:MAX_DAILY_PUSH]
            push_batches.append(first_batch)
            
            # 第二批：剩余文章，但不超过MAX_SECOND_PUSH条
            remaining_articles = today_articles[MAX_DAILY_PUSH:]
            if remaining_articles:
                second_batch = remaining_articles[:MAX_SECOND_PUSH]
                push_batches.append(second_batch)
                
        # 统计关键词
        keyword_stats = self.calculate_keyword_stats(today_articles)
        
        return push_batches, keyword_stats
        
    def calculate_keyword_stats(self, articles: List[Article]) -> Dict[str, int]:
        """计算关键词统计"""
        stats = {}
        for article in articles:
            for keyword in article.keywords_matched:
                stats[keyword] = stats.get(keyword, 0) + 1
        return stats
        
    def send_wechat_message(self, content: str) -> bool:
        """发送微信消息"""
        if not self.wechat_webhook:
            self.logger.warning("未配置微信Webhook，跳过推送")
            return False
            
        try:
            payload = {
                "msgtype": "text",
                "text": {
                    "content": content
                }
            }
            
            response = requests.post(
                self.wechat_webhook,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            if result.get('errcode') == 0:
                self.logger.info("微信推送成功")
                return True
            else:
                self.logger.error(f"微信推送失败: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"微信推送异常: {e}")
            return False
            
    def create_push_message(self, articles: List[Article], batch_num: int, total_batches: int, keyword_stats: Dict[str, int] = None) -> str:
        """创建推送消息"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 消息头部
        if total_batches > 1:
            header = f"【地质前沿每日推送】{today} (第{batch_num}/{total_batches}批)"
        else:
            header = f"【地质前沿每日推送】{today}"
            
        content_lines = [header, ""]
        content_lines.append(f"🔬 今日精选文章 ({len(articles)}篇):")
        content_lines.append("")
        
        # 文章列表
        for i, article in enumerate(articles, 1):
            article_text = self.format_article_for_push(article)
            content_lines.append(f"{i}. {article_text}")
            content_lines.append("")
            
        # 只在最后一批添加关键词统计
        if batch_num == total_batches and keyword_stats:
            content_lines.append("【今日热点词汇排行】")
            sorted_keywords = sorted(keyword_stats.items(), key=lambda x: x[1], reverse=True)
            for keyword, count in sorted_keywords[:10]:  # 只显示前10个
                content_lines.append(f"{keyword}: {count}")
                
        return "\n".join(content_lines)
        
    def mark_articles_as_pushed(self, articles: List[Article]):
        """标记文章为已推送"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        for article in articles:
            article.is_pushed = True
            article.push_date = today
            
            # 添加到已推送列表
            if article.link not in self.pushed_articles:
                self.pushed_articles.append(article.link)
                
        # 清理历史队列中的已推送文章（保留最近30天的记录）
        self.cleanup_historical_queue()
        
    def cleanup_historical_queue(self):
        """清理历史队列"""
        cutoff_date = datetime.now() - timedelta(days=30)
        
        # 保留未推送的文章和最近30天的已推送文章
        cleaned_queue = []
        for article in self.historical_queue:
            if not article.is_pushed:
                cleaned_queue.append(article)
            elif article.push_date:
                try:
                    push_date = datetime.fromisoformat(article.push_date)
                    if push_date >= cutoff_date:
                        cleaned_queue.append(article)
                except:
                    pass
                    
        self.historical_queue = cleaned_queue
        
        # 清理已推送文章列表（保留最近1000条记录）
        if len(self.pushed_articles) > 1000:
            self.pushed_articles = self.pushed_articles[-1000:]
            
    def run_daily_check(self):
        """执行每日检查"""
        self.logger.info("开始执行每日RSS监控检查")
        
        try:
            # 处理每日文章
            push_batches, keyword_stats = self.process_daily_articles()
            
            if not push_batches:
                self.logger.info("今日没有符合条件的文章需要推送")
                return
                
            # 分批推送
            total_batches = len(push_batches)
            for batch_num, articles in enumerate(push_batches, 1):
                # 创建推送消息
                message = self.create_push_message(
                    articles, 
                    batch_num, 
                    total_batches, 
                    keyword_stats if batch_num == total_batches else None
                )
                
                # 发送推送
                success = self.send_wechat_message(message)
                
                if success:
                    # 标记为已推送
                    self.mark_articles_as_pushed(articles)
                    self.logger.info(f"第{batch_num}批推送成功，包含{len(articles)}篇文章")
                else:
                    self.logger.error(f"第{batch_num}批推送失败")
                    
                # 批次间延迟
                if batch_num < total_batches:
                    time.sleep(5)
                    
            # 保存数据
            self.save_historical_data()
            
            self.logger.info(f"每日检查完成，共推送{sum(len(batch) for batch in push_batches)}篇文章")
            
        except Exception as e:
            self.logger.error(f"每日检查执行失败: {e}")
            raise

def main():
    """主函数"""
    try:
        monitor = RSSMonitor()
        monitor.run_daily_check()
    except Exception as e:
        logging.error(f"程序执行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()