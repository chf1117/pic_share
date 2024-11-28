import os
from pathlib import Path
from pymongo import MongoClient

def clean_uploads():
    # 连接到MongoDB
    client = MongoClient('mongodb://localhost:27017/')
    db = client['your_database_name']
    images_collection = db['images']
    
    # 获取数据库中的所有图片文件名
    db_images = set(img['filename'] for img in images_collection.find({}, {'filename': 1}))
    
    # 获取uploads目录中的所有jpg文件
    uploads_dir = Path('uploads')
    file_images = set(f.name for f in uploads_dir.glob('*.jpg'))
    
    # 找出在文件系统中存在但在数据库中不存在的文件
    orphaned_files = file_images - db_images
    
    # 删除孤立文件
    deleted_count = 0
    for filename in orphaned_files:
        file_path = uploads_dir / filename
        try:
            os.remove(file_path)
            print(f"已删除: {filename}")
            deleted_count += 1
        except Exception as e:
            print(f"删除 {filename} 时出错: {e}")
    
    print(f"\n清理完成:")
    print(f"- 数据库中的图片数量: {len(db_images)}")
    print(f"- 文件系统中的图片数量: {len(file_images)}")
    print(f"- 删除的孤立文件数量: {deleted_count}")

if __name__ == '__main__':
    clean_uploads()
