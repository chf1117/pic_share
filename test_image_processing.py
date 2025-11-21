#!/usr/bin/env python3
"""
测试图片处理功能

测试：
1. ImageProcessor 类导入
2. 缩略图生成
3. WebP 转换
"""

import os
import sys
from pathlib import Path

# 测试导入
print("=" * 60)
print("测试 1: 导入模块")
print("=" * 60)

try:
    from utils.image_processor import ImageProcessor
    from utils import save_image, get_image_metadata
    print("✅ 所有模块导入成功")
except Exception as e:
    print(f"❌ 导入失败: {e}")
    sys.exit(1)

# 测试 ImageProcessor 初始化
print("\n" + "=" * 60)
print("测试 2: 初始化 ImageProcessor")
print("=" * 60)

try:
    upload_folder = "uploads"
    processor = ImageProcessor(upload_folder)
    print(f"✅ ImageProcessor 初始化成功")
    print(f"   - 上传目录: {processor.upload_folder}")
    print(f"   - 缩略图目录: {processor.thumbnail_folder}")
    print(f"   - WebP 目录: {processor.webp_folder}")
except Exception as e:
    print(f"❌ 初始化失败: {e}")
    sys.exit(1)

# 检查目录是否创建
print("\n" + "=" * 60)
print("测试 3: 检查目录结构")
print("=" * 60)

directories = [
    processor.upload_folder,
    processor.thumbnail_folder,
    processor.webp_folder
]

for directory in directories:
    if directory.exists():
        print(f"✅ {directory} 存在")
    else:
        print(f"⚠️  {directory} 不存在（将在首次使用时创建）")

# 测试图片处理（如果有测试图片）
print("\n" + "=" * 60)
print("测试 4: 图片处理功能")
print("=" * 60)

# 查找测试图片
test_image = None
for ext in ['.jpg', '.jpeg', '.png']:
    for file in Path('uploads').glob(f'*{ext}'):
        test_image = file
        break
    if test_image:
        break

if test_image and test_image.exists():
    print(f"找到测试图片: {test_image.name}")
    
    try:
        # 测试缩略图生成
        print("\n测试缩略图生成...")
        thumbnail_path = processor.generate_thumbnail(str(test_image))
        if thumbnail_path:
            print(f"✅ 缩略图生成成功: {thumbnail_path}")
            print(f"   文件大小: {Path(thumbnail_path).stat().st_size / 1024:.1f} KB")
        else:
            print("❌ 缩略图生成失败")
        
        # 测试 WebP 转换
        print("\n测试 WebP 转换...")
        webp_path = processor.generate_webp(str(test_image))
        if webp_path:
            print(f"✅ WebP 转换成功: {webp_path}")
            print(f"   文件大小: {Path(webp_path).stat().st_size / 1024:.1f} KB")
        else:
            print("❌ WebP 转换失败")
        
        # 测试完整处理
        print("\n测试完整处理...")
        result = processor.process_image(str(test_image))
        if result['success']:
            print(f"✅ 完整处理成功")
            print(f"   - 原图: {result['original']}")
            print(f"   - 缩略图: {result['thumbnail']}")
            print(f"   - WebP: {result['webp']}")
        else:
            print("❌ 完整处理失败")
            
    except Exception as e:
        print(f"❌ 处理过程出错: {e}")
        import traceback
        traceback.print_exc()
else:
    print("⚠️  未找到测试图片，跳过图片处理测试")
    print("   提示: 将一张图片放到 uploads/ 目录下进行测试")

# 总结
print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
print("\n✅ 所有基础功能正常")
print("\n下一步:")
print("1. 启动 MongoDB: mongod")
print("2. 运行 Flask 应用: python app.py")
print("3. 访问 http://localhost:5000")
print("4. 测试上传功能")
