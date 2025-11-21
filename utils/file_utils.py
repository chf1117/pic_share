"""
文件处理工具模块

功能：
1. 安全保存上传的图片文件
2. 生成缩略图和 WebP 格式
3. 获取图片 EXIF 元数据

作者: chf1117
版本: v1.2
日期: 2025-11-11
"""

from pathlib import Path
import os
import piexif
from PIL import Image
from werkzeug.utils import secure_filename
import logging
from datetime import datetime
from .image_processor import ImageProcessor

logger = logging.getLogger(__name__)


def save_image(file, upload_folder, generate_variants=True):
    """
    安全地保存上传的图片文件，并生成缩略图和 WebP 格式
    
    Args:
        file: FileStorage对象
        upload_folder: 上传文件夹路径
        generate_variants: 是否生成缩略图和 WebP（默认 True）
    
    Returns:
        包含所有文件路径的字典:
        {
            'original_path': 原图路径,
            'thumbnail_path': 缩略图路径（可能为 None）,
            'webp_path': WebP 路径（可能为 None）,
            'filename': 文件名,
            'file_sizes': {
                'original': 原图大小,
                'thumbnail': 缩略图大小,
                'webp': WebP 大小
            }
        }
    """
    try:
        # 保留原始文件名，但确保安全
        filename = secure_filename(file.filename)
        # 使用pathlib处理路径
        upload_path = Path(upload_folder)
        save_path = upload_path / filename
        
        # 如果文件已存在，添加数字后缀
        counter = 1
        while save_path.exists():
            stem = save_path.stem
            # 如果文件名已经有数字后缀，移除它
            if stem.endswith(f'_{counter-1}'):
                stem = stem.rsplit('_', 1)[0]
            new_name = f"{stem}_{counter}{save_path.suffix}"
            save_path = save_path.with_name(new_name)
            counter += 1
            
        # 保存原图
        file.save(str(save_path))
        logger.info(f"Successfully saved image to {save_path.as_posix()}")
        
        # 初始化返回结果
        result = {
            'original_path': str(save_path),
            'thumbnail_path': None,
            'webp_path': None,
            'filename': save_path.name,
            'file_sizes': {
                'original': save_path.stat().st_size,
                'thumbnail': 0,
                'webp': 0
            }
        }
        
        # 生成缩略图和 WebP
        if generate_variants:
            try:
                processor = ImageProcessor(upload_folder)
                processed = processor.process_image(str(save_path))
                
                result['thumbnail_path'] = processed.get('thumbnail')
                result['webp_path'] = processed.get('webp')
                
                # 更新文件大小
                if result['thumbnail_path']:
                    result['file_sizes']['thumbnail'] = Path(result['thumbnail_path']).stat().st_size
                if result['webp_path']:
                    result['file_sizes']['webp'] = Path(result['webp_path']).stat().st_size
                
                logger.info(
                    f"Image processing completed: {filename} "
                    f"(thumbnail: {bool(result['thumbnail_path'])}, "
                    f"webp: {bool(result['webp_path'])})"
                )
            except Exception as e:
                logger.error(f"Error generating variants for {filename}: {str(e)}")
                # 继续执行，不影响原图保存
        
        return result
        
    except Exception as e:
        logger.error(f"Error saving image: {str(e)}")
        raise


def get_image_metadata(image_path):
    """
    获取图片的EXIF元数据，包括拍摄时间
    
    Args:
        image_path: 图片文件路径
    
    Returns:
        包含元数据的字典
    """
    try:
        image_path = Path(image_path)
        metadata = {}
        
        if not image_path.exists():
            logger.error(f"Image file not found: {image_path.as_posix()}")
            return metadata
            
        with Image.open(image_path) as img:
            metadata['size'] = img.size
            metadata['format'] = img.format
            metadata['created'] = image_path.stat().st_ctime
            metadata['modified'] = image_path.stat().st_mtime
            
            # 设置默认拍摄时间为文件修改时间
            photo_time = datetime.fromtimestamp(image_path.stat().st_mtime)
            
            if 'exif' in img.info:
                try:
                    exif_dict = piexif.load(img.info['exif'])
                    # 优先使用原始拍摄时间
                    if piexif.ExifIFD.DateTimeOriginal in exif_dict['Exif']:
                        date_str = exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal].decode()
                        photo_time = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                    # 其次使用数字化时间
                    elif piexif.ExifIFD.DateTimeDigitized in exif_dict['Exif']:
                        date_str = exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized].decode()
                        photo_time = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                    # 最后使用图片创建时间
                    elif piexif.ImageIFD.DateTime in exif_dict['0th']:
                        date_str = exif_dict['0th'][piexif.ImageIFD.DateTime].decode()
                        photo_time = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                except (ValueError, KeyError) as e:
                    logger.warning(f"Error parsing EXIF date for {image_path.name}: {str(e)}")
            
            # 保存拍摄时间
            metadata['photo_time'] = photo_time
            metadata['year'] = photo_time.year
            metadata['month'] = photo_time.month
                    
        return metadata
        
    except Exception as e:
        logger.error(f"Error getting image metadata: {str(e)}")
        return {}
