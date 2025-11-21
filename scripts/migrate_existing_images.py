#!/usr/bin/env python3
"""
批量处理现有图片脚本

功能：
1. 扫描数据库中所有图片记录
2. 为每张图片生成缩略图和 WebP 格式
3. 更新数据库记录
4. 显示处理进度和统计信息
5. 支持断点续传

作者: chf1117
版本: v1.2
日期: 2025-11-11
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
from pymongo import MongoClient
from tqdm import tqdm

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.image_processor import ImageProcessor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ImageMigrator:
    """图片迁移处理器"""
    
    def __init__(self, mongo_uri, db_name, upload_folder, dry_run=False):
        """
        初始化迁移处理器
        
        Args:
            mongo_uri: MongoDB 连接字符串
            db_name: 数据库名称
            upload_folder: 上传文件夹路径
            dry_run: 是否为预览模式
        """
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.upload_folder = Path(upload_folder)
        self.dry_run = dry_run
        
        # 连接数据库
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.images_collection = self.db.images
        
        # 初始化图片处理器
        self.processor = ImageProcessor(str(upload_folder))
        
        # 统计信息
        self.stats = {
            'total': 0,
            'processed': 0,
            'skipped': 0,
            'failed': 0,
            'thumbnail_generated': 0,
            'webp_generated': 0
        }
    
    def get_images_to_process(self, skip_existing=True, force=False):
        """
        获取需要处理的图片列表
        
        Args:
            skip_existing: 跳过已处理的图片
            force: 强制重新处理所有图片
        
        Returns:
            图片记录列表
        """
        query = {}
        
        if skip_existing and not force:
            # 只处理没有缩略图或 WebP 的图片
            query = {
                '$or': [
                    {'has_thumbnail': {'$ne': True}},
                    {'has_webp': {'$ne': True}},
                    {'thumbnail_path': {'$exists': False}},
                    {'webp_path': {'$exists': False}}
                ]
            }
        
        images = list(self.images_collection.find(query))
        self.stats['total'] = len(images)
        
        logger.info(f"找到 {len(images)} 张图片需要处理")
        return images
    
    def process_image(self, image_record):
        """
        处理单张图片
        
        Args:
            image_record: 图片记录
        
        Returns:
            处理结果字典
        """
        image_id = image_record['_id']
        original_path = image_record.get('path')
        
        if not original_path:
            logger.error(f"图片 {image_id} 没有路径信息")
            return {'success': False, 'error': '没有路径信息'}
        
        # 检查原图是否存在
        if not Path(original_path).exists():
            logger.error(f"原图不存在: {original_path}")
            return {'success': False, 'error': '原图不存在'}
        
        result = {
            'success': False,
            'thumbnail_path': None,
            'webp_path': None,
            'thumbnail_generated': False,
            'webp_generated': False
        }
        
        try:
            # 检查是否已有缩略图
            if not image_record.get('has_thumbnail'):
                thumbnail_path = self.processor.generate_thumbnail(original_path)
                if thumbnail_path:
                    result['thumbnail_path'] = thumbnail_path
                    result['thumbnail_generated'] = True
                    self.stats['thumbnail_generated'] += 1
            else:
                result['thumbnail_path'] = image_record.get('thumbnail_path')
                logger.info(f"跳过已有缩略图: {original_path}")
            
            # 检查是否已有 WebP
            if not image_record.get('has_webp'):
                webp_path = self.processor.generate_webp(original_path)
                if webp_path:
                    result['webp_path'] = webp_path
                    result['webp_generated'] = True
                    self.stats['webp_generated'] += 1
            else:
                result['webp_path'] = image_record.get('webp_path')
                logger.info(f"跳过已有 WebP: {original_path}")
            
            result['success'] = True
            
        except Exception as e:
            logger.error(f"处理图片失败 {original_path}: {str(e)}")
            result['error'] = str(e)
        
        return result
    
    def update_database(self, image_id, process_result):
        """
        更新数据库记录
        
        Args:
            image_id: 图片 ID
            process_result: 处理结果
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] 将更新图片 {image_id}")
            return
        
        update_data = {
            'processing_status': 'completed' if process_result['success'] else 'failed'
        }
        
        if process_result.get('thumbnail_path'):
            update_data['thumbnail_path'] = process_result['thumbnail_path']
            update_data['has_thumbnail'] = True
        
        if process_result.get('webp_path'):
            update_data['webp_path'] = process_result['webp_path']
            update_data['has_webp'] = True
        
        # 获取文件大小
        if process_result['success']:
            file_sizes = {}
            
            # 原图大小
            image_record = self.images_collection.find_one({'_id': image_id})
            if image_record and image_record.get('path'):
                original_path = Path(image_record['path'])
                if original_path.exists():
                    file_sizes['original'] = original_path.stat().st_size
            
            # 缩略图大小
            if process_result.get('thumbnail_path'):
                thumbnail_path = Path(process_result['thumbnail_path'])
                if thumbnail_path.exists():
                    file_sizes['thumbnail'] = thumbnail_path.stat().st_size
            
            # WebP 大小
            if process_result.get('webp_path'):
                webp_path = Path(process_result['webp_path'])
                if webp_path.exists():
                    file_sizes['webp'] = webp_path.stat().st_size
            
            if file_sizes:
                update_data['file_sizes'] = file_sizes
        
        try:
            self.images_collection.update_one(
                {'_id': image_id},
                {'$set': update_data}
            )
            logger.debug(f"数据库更新成功: {image_id}")
        except Exception as e:
            logger.error(f"数据库更新失败 {image_id}: {str(e)}")
    
    def run(self, batch_size=10, skip_existing=True, force=False):
        """
        运行迁移任务
        
        Args:
            batch_size: 批处理大小
            skip_existing: 跳过已处理的图片
            force: 强制重新处理
        """
        logger.info("=" * 60)
        logger.info("开始批量处理图片")
        logger.info(f"模式: {'预览模式' if self.dry_run else '正式处理'}")
        logger.info(f"数据库: {self.db_name}")
        logger.info(f"上传目录: {self.upload_folder}")
        logger.info("=" * 60)
        
        # 获取需要处理的图片
        images = self.get_images_to_process(skip_existing, force)
        
        if not images:
            logger.info("没有需要处理的图片")
            return
        
        # 使用进度条处理
        with tqdm(total=len(images), desc="处理进度") as pbar:
            for i, image in enumerate(images):
                try:
                    # 处理图片
                    result = self.process_image(image)
                    
                    if result['success']:
                        # 更新数据库
                        self.update_database(image['_id'], result)
                        self.stats['processed'] += 1
                    else:
                        self.stats['failed'] += 1
                    
                    # 更新进度条
                    pbar.update(1)
                    pbar.set_postfix({
                        '成功': self.stats['processed'],
                        '失败': self.stats['failed']
                    })
                    
                except Exception as e:
                    logger.error(f"处理图片时发生错误: {str(e)}")
                    self.stats['failed'] += 1
                    pbar.update(1)
        
        # 打印统计信息
        self.print_stats()
    
    def print_stats(self):
        """打印统计信息"""
        logger.info("=" * 60)
        logger.info("处理完成！统计信息：")
        logger.info(f"总计: {self.stats['total']} 张")
        logger.info(f"成功: {self.stats['processed']} 张")
        logger.info(f"失败: {self.stats['failed']} 张")
        logger.info(f"生成缩略图: {self.stats['thumbnail_generated']} 个")
        logger.info(f"生成 WebP: {self.stats['webp_generated']} 个")
        logger.info("=" * 60)
        
        # 计算存储空间
        if self.stats['processed'] > 0:
            avg_thumbnail_size = 20  # KB
            avg_webp_size = 500  # KB
            
            total_thumbnail_size = self.stats['thumbnail_generated'] * avg_thumbnail_size / 1024  # MB
            total_webp_size = self.stats['webp_generated'] * avg_webp_size / 1024  # MB
            
            logger.info(f"预计新增存储空间: {total_thumbnail_size + total_webp_size:.1f} MB")
            logger.info(f"  - 缩略图: {total_thumbnail_size:.1f} MB")
            logger.info(f"  - WebP: {total_webp_size:.1f} MB")
    
    def close(self):
        """关闭数据库连接"""
        self.client.close()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='批量处理现有图片')
    parser.add_argument('--mongo-uri', default='mongodb://localhost:27017/',
                        help='MongoDB 连接字符串')
    parser.add_argument('--db-name', default='your_database_name',
                        help='数据库名称')
    parser.add_argument('--upload-folder', default='uploads',
                        help='上传文件夹路径')
    parser.add_argument('--batch-size', type=int, default=10,
                        help='批处理大小')
    parser.add_argument('--skip-existing', action='store_true', default=True,
                        help='跳过已处理的图片')
    parser.add_argument('--force', action='store_true',
                        help='强制重新处理所有图片')
    parser.add_argument('--dry-run', action='store_true',
                        help='预览模式，不实际处理')
    
    args = parser.parse_args()
    
    # 创建日志目录
    Path('logs').mkdir(exist_ok=True)
    
    # 创建迁移处理器
    migrator = ImageMigrator(
        mongo_uri=args.mongo_uri,
        db_name=args.db_name,
        upload_folder=args.upload_folder,
        dry_run=args.dry_run
    )
    
    try:
        # 运行迁移
        migrator.run(
            batch_size=args.batch_size,
            skip_existing=args.skip_existing,
            force=args.force
        )
    except KeyboardInterrupt:
        logger.info("\n用户中断处理")
    except Exception as e:
        logger.error(f"处理过程中发生错误: {str(e)}")
    finally:
        migrator.close()


if __name__ == '__main__':
    main()
