"""
图片处理工具模块

功能：
1. 生成保持宽高比的缩略图
2. 转换为 WebP 格式
3. 管理文件路径
4. 错误处理和日志记录

作者: chf1117
版本: v1.2
日期: 2025-11-11
"""

import os
import logging
from pathlib import Path
from PIL import Image
from typing import Tuple, Optional, Dict

logger = logging.getLogger(__name__)


class ImageProcessor:
    """图片处理器类"""
    
    def __init__(self, upload_folder: str):
        """
        初始化图片处理器
        
        Args:
            upload_folder: 上传文件夹路径
        """
        self.upload_folder = Path(upload_folder)
        self.thumbnail_folder = self.upload_folder / 'thumbnails'
        self.webp_folder = self.upload_folder / 'webp'
        
        # 确保目录存在
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保所有必要的目录存在"""
        self.thumbnail_folder.mkdir(parents=True, exist_ok=True)
        self.webp_folder.mkdir(parents=True, exist_ok=True)
        logger.info(f"图片处理目录已创建: {self.thumbnail_folder}, {self.webp_folder}")
    
    def generate_thumbnail(
        self, 
        input_path: str, 
        max_size: int = 200,
        quality: int = 85
    ) -> Optional[str]:
        """
        生成保持宽高比的缩略图
        
        Args:
            input_path: 原图路径
            max_size: 最长边的最大尺寸（默认 200px）
            quality: WebP 质量（1-100，默认 85）
        
        Returns:
            缩略图路径，失败返回 None
        
        示例:
            横向照片 4000x3000 → 200x150px
            竖向照片 3000x4000 → 150x200px
            全景照片 6000x2000 → 200x67px
        """
        try:
            input_path = Path(input_path)
            
            # 检查原图是否存在
            if not input_path.exists():
                logger.error(f"原图不存在: {input_path}")
                return None
            
            # 生成缩略图文件名（保持原文件名，改为 .webp）
            thumbnail_name = input_path.stem + '.webp'
            thumbnail_path = self.thumbnail_folder / thumbnail_name
            
            # 打开图片
            with Image.open(input_path) as img:
                # 转换 RGBA 或 P 模式为 RGB
                if img.mode in ('RGBA', 'LA', 'P'):
                    # 创建白色背景
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 记录原始尺寸
                original_size = img.size
                
                # 使用 thumbnail 方法，自动保持宽高比
                # 最长边不超过 max_size
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
                # 保存为 WebP 格式
                img.save(
                    str(thumbnail_path), 
                    'WEBP', 
                    quality=quality, 
                    method=6  # 最佳压缩
                )
                
                # 记录缩略图尺寸
                thumbnail_size = img.size
                file_size = thumbnail_path.stat().st_size
                
                logger.info(
                    f"缩略图生成成功: {input_path.name} "
                    f"{original_size} → {thumbnail_size} "
                    f"({file_size / 1024:.1f}KB)"
                )
                
                return str(thumbnail_path)
        
        except Exception as e:
            logger.error(f"生成缩略图失败 {input_path}: {str(e)}")
            return None
    
    def generate_webp(
        self, 
        input_path: str, 
        quality: int = 85
    ) -> Optional[str]:
        """
        转换为 WebP 格式（保持原尺寸）
        
        Args:
            input_path: 原图路径
            quality: WebP 质量（1-100，默认 85）
        
        Returns:
            WebP 文件路径，失败返回 None
        """
        try:
            input_path = Path(input_path)
            
            # 检查原图是否存在
            if not input_path.exists():
                logger.error(f"原图不存在: {input_path}")
                return None
            
            # 生成 WebP 文件名
            webp_name = input_path.stem + '.webp'
            webp_path = self.webp_folder / webp_name
            
            # 打开图片
            with Image.open(input_path) as img:
                # 转换 RGBA 或 P 模式为 RGB
                if img.mode in ('RGBA', 'LA', 'P'):
                    # 创建白色背景
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 记录原始尺寸
                original_size = img.size
                original_file_size = input_path.stat().st_size
                
                # 保存为 WebP 格式（保持原尺寸）
                img.save(
                    str(webp_path), 
                    'WEBP', 
                    quality=quality, 
                    method=6  # 最佳压缩
                )
                
                # 记录文件大小
                webp_file_size = webp_path.stat().st_size
                compression_ratio = (1 - webp_file_size / original_file_size) * 100
                
                logger.info(
                    f"WebP 转换成功: {input_path.name} "
                    f"{original_size} "
                    f"{original_file_size / 1024:.1f}KB → {webp_file_size / 1024:.1f}KB "
                    f"(压缩 {compression_ratio:.1f}%)"
                )
                
                return str(webp_path)
        
        except Exception as e:
            logger.error(f"WebP 转换失败 {input_path}: {str(e)}")
            return None
    
    def process_image(
        self, 
        input_path: str,
        thumbnail_size: int = 200,
        quality: int = 85
    ) -> Dict[str, Optional[str]]:
        """
        完整处理图片：生成缩略图和 WebP
        
        Args:
            input_path: 原图路径
            thumbnail_size: 缩略图最长边尺寸
            quality: 图片质量
        
        Returns:
            包含所有路径的字典:
            {
                'original': 原图路径,
                'thumbnail': 缩略图路径,
                'webp': WebP 路径,
                'success': 是否全部成功
            }
        """
        result = {
            'original': str(input_path),
            'thumbnail': None,
            'webp': None,
            'success': False
        }
        
        try:
            # 生成缩略图
            thumbnail_path = self.generate_thumbnail(
                input_path, 
                max_size=thumbnail_size,
                quality=quality
            )
            result['thumbnail'] = thumbnail_path
            
            # 生成 WebP
            webp_path = self.generate_webp(
                input_path,
                quality=quality
            )
            result['webp'] = webp_path
            
            # 判断是否全部成功
            result['success'] = bool(thumbnail_path and webp_path)
            
            if result['success']:
                logger.info(f"图片处理完成: {Path(input_path).name}")
            else:
                logger.warning(
                    f"图片处理部分失败: {Path(input_path).name} "
                    f"(缩略图: {bool(thumbnail_path)}, WebP: {bool(webp_path)})"
                )
        
        except Exception as e:
            logger.error(f"图片处理失败 {input_path}: {str(e)}")
        
        return result
    
    def get_file_sizes(self, paths: Dict[str, Optional[str]]) -> Dict[str, int]:
        """
        获取所有文件的大小
        
        Args:
            paths: 文件路径字典
        
        Returns:
            文件大小字典（字节）
        """
        sizes = {}
        
        for key, path in paths.items():
            if path and Path(path).exists():
                sizes[key] = Path(path).stat().st_size
            else:
                sizes[key] = 0
        
        return sizes
    
    def cleanup_failed_files(self, paths: Dict[str, Optional[str]]):
        """
        清理处理失败的文件
        
        Args:
            paths: 文件路径字典
        """
        for key, path in paths.items():
            if key != 'original' and path:
                try:
                    path_obj = Path(path)
                    if path_obj.exists():
                        path_obj.unlink()
                        logger.info(f"已清理文件: {path}")
                except Exception as e:
                    logger.error(f"清理文件失败 {path}: {str(e)}")


def get_image_dimensions(image_path: str) -> Optional[Tuple[int, int]]:
    """
    获取图片尺寸
    
    Args:
        image_path: 图片路径
    
    Returns:
        (width, height) 或 None
    """
    try:
        with Image.open(image_path) as img:
            return img.size
    except Exception as e:
        logger.error(f"获取图片尺寸失败 {image_path}: {str(e)}")
        return None


def is_image_file(file_path: str) -> bool:
    """
    检查是否为图片文件
    
    Args:
        file_path: 文件路径
    
    Returns:
        是否为图片文件
    """
    try:
        with Image.open(file_path) as img:
            img.verify()
        return True
    except Exception:
        return False


# 便捷函数
def create_image_processor(upload_folder: str) -> ImageProcessor:
    """
    创建图片处理器实例
    
    Args:
        upload_folder: 上传文件夹路径
    
    Returns:
        ImageProcessor 实例
    """
    return ImageProcessor(upload_folder)
