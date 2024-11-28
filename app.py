import os
from datetime import datetime
import time
import piexif
from pathlib import Path
from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_from_directory, session
from flask_pymongo import PyMongo
from werkzeug.utils import secure_filename
from bson import ObjectId
import logging
from PIL import Image
from utils import save_image, get_image_metadata

# 创建Flask应用
app = Flask(__name__)

# 配置应用的密钥和MongoDB数据库
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['MONGO_URI'] = 'mongodb://localhost:27017/your_database_name'

# 使用 pathlib 处理路径，确保跨平台兼容性
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path('uploads')
app.config['UPLOAD_FOLDER'] = str(BASE_DIR / UPLOAD_DIR)
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB

# 确保上传文件夹存在
upload_path = Path(app.config['UPLOAD_FOLDER'])
upload_path.mkdir(parents=True, exist_ok=True)

# 记录上传文件夹路径
app.logger.info(f"Upload folder: {upload_path.as_posix()}")

# 允许的文件扩展名
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILES = 20  # 最大文件数量

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 初始化MongoDB
mongo = PyMongo(app)

# 确保索引存在
mongo.db.images.create_index([("tags", 1)])
mongo.db.images.create_index([("is_public", 1)])  # 保持原有字段
mongo.db.images.create_index([("username", 1)])
mongo.db.images.create_index([("photo_time", -1)])  # 添加拍摄时间索引

# 设置日志级别
app.logger.setLevel(logging.INFO)

def get_photo_time(image_path):
    """从图片中获取拍摄时间，优先使用EXIF数据，如果没有则使用文件修改时间"""
    try:
        image = Image.open(image_path)
        if hasattr(image, '_getexif') and image._getexif() is not None:
            exif_dict = image._getexif()
            # 尝试从不同的EXIF标签中获取时间
            date_tags = [
                36867,  # DateTimeOriginal
                36868,  # DateTimeDigitized
                306,    # DateTime
            ]
            
            for tag in date_tags:
                if tag in exif_dict:
                    try:
                        date_str = exif_dict[tag].strip()
                        # 尝试解析不同的日期格式
                        try:
                            # 标准格式 'YYYY:MM:DD HH:MM:SS'
                            return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                        except ValueError:
                            try:
                                # 替代格式 'YYYY-MM-DD HH:MM:SS'
                                return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                # 其他可能的格式...
                                pass
                    except Exception as e:
                        app.logger.error(f"Error parsing EXIF date from tag {tag}: {str(e)}")
                        continue
            
            # 如果上面的标签都没有找到，尝试使用 piexif
            try:
                exif_data = piexif.load(image.info['exif'])
                if piexif.ExifIFD.DateTimeOriginal in exif_data['Exif']:
                    date_str = exif_data['Exif'][piexif.ExifIFD.DateTimeOriginal].decode('utf-8')
                    return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                elif piexif.ExifIFD.DateTimeDigitized in exif_data['Exif']:
                    date_str = exif_data['Exif'][piexif.ExifIFD.DateTimeDigitized].decode('utf-8')
                    return datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
            except Exception as e:
                app.logger.error(f"Error reading EXIF data using piexif: {str(e)}")
    
    except Exception as e:
        app.logger.error(f"Error reading EXIF data from {image_path}: {str(e)}")
    
    # 如果无法获取EXIF数据，使用文件的修改时间
    try:
        mtime = Path(image_path).stat().st_mtime
        return datetime.fromtimestamp(mtime)
    except Exception as e:
        app.logger.error(f"Error getting file modification time: {str(e)}")
        return datetime.now()  # 如果所有方法都失败，返回当前时间

# 用户注册路由
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':  # 处理POST请求
        username = request.form['username']  # 获取用户名
        password = request.form['password']  # 获取密码
        # 在MongoDB中插入用户
        mongo.db.users.insert_one({'username': username, 'password': password})
        flash('您的账户已创建！', 'success')  # 显示成功消息
        return redirect(url_for('login'))  # 重定向到登录页面
    return render_template('register.html')  # 渲染注册页面

# 用户登录路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':  # 处理POST请求
        username = request.form['username']  # 获取用户名
        password = request.form['password']  # 获取密码
        # 在MongoDB中查找用户
        user = mongo.db.users.find_one({'username': username, 'password': password})
        if user:  # 验证用户名和密码
            session['username'] = username  # 将用户名存入session
            flash('登录成功！', 'success')  # 显示成功消息
            return redirect(url_for('home'))  # 重定向到主页
        else:
            flash('登录失败，请检查用户名和密码', 'danger')  # 显示错误消息
    return render_template('login.html')  # 渲染登录页面

# 登出路由
@app.route('/logout')
def logout():
    session.pop('username', None)  # 从session中移除用户名
    flash('您已成功登出！', 'success')
    return redirect(url_for('home'))

# 主页面路由
@app.route('/')
def home():
    return render_template('index.html')

# 获取公开图片API
@app.route('/api/public_images')
def get_public_images():
    """获取公开图片列表，支持分页、标签过滤和排序"""
    try:
        page = int(request.args.get('page', 1))
        tag = request.args.get('tag', '')
        sort = request.args.get('sort', 'likes')  # 默认按点赞数排序
        year = request.args.get('year', '')  # 年份参数
        is_private = request.args.get('private', '').lower() == 'true'  # 获取私密模式参数
        
        app.logger.info(f"Received request - username: {session.get('username')}, private_mode: {is_private}")

        # 构建查询条件
        query = {}
        if tag:
            query['tags'] = tag

        # 如果指定了年份，使用聚合管道按月份分组
        if year:
            try:
                year = int(year)
                start_date = datetime(year, 1, 1)
                end_date = datetime(year + 1, 1, 1)
                query['photo_time'] = {
                    '$gte': start_date,
                    '$lt': end_date
                }
                
                # 添加私密模式条件
                if is_private:
                    query['is_public'] = False
                else:
                    query['is_public'] = True
                
                app.logger.info(f"Year query conditions: {query}")
                
                # 先获取符合条件的图片
                images = list(mongo.db.images.find(query).sort([('photo_time', -1)]))
                app.logger.info(f"Found {len(images)} images for year {year}")
                
                # 手动按月份分组
                months = {}
                for image in images:
                    if isinstance(image.get('photo_time'), datetime):
                        month = image['photo_time'].month
                    else:
                        # 如果photo_time不是datetime类型，尝试转换
                        try:
                            if isinstance(image.get('photo_time'), str):
                                image['photo_time'] = datetime.strptime(image['photo_time'], '%Y-%m-%d %H:%M:%S')
                            month = image['photo_time'].month
                        except (ValueError, TypeError, AttributeError):
                            app.logger.error(f"Invalid photo_time format for image {image.get('_id')}")
                            continue
                    
                    if month not in months:
                        months[month] = []
                    
                    # 处理ObjectId
                    image['_id'] = str(image['_id'])
                    # 添加文件URL
                    image_path = str(Path('uploads') / image['filename'])
                    image['url'] = f"/{image_path.replace(os.sep, '/')}"
                    # 格式化photo_time
                    image['photo_time'] = image['photo_time'].strftime('%Y-%m-%d %H:%M:%S')
                    
                    months[month].append(image)
                
                # 转换为按月份分组的列表
                result = [{'_id': month, 'images': images} for month, images in sorted(months.items(), reverse=True)]
                
                return jsonify({
                    'by_month': True,
                    'year': year,
                    'data': result
                })
                
            except ValueError as e:
                app.logger.error(f"Invalid year format: {e}")
                return jsonify({'error': str(e)}), 400

        # 如果没有指定年份，使用原来的逻辑
        # 根据私密模式设置查询条件
        if is_private:
            query['is_public'] = False
        else:
            query['is_public'] = True
            
        app.logger.info(f"Query conditions: {query}")

        if sort == 'likes':
            sort_key = [('likes', -1)]
        elif sort == 'date':
            sort_key = [('photo_time', -1)]
        else:
            sort_key = [('_id', -1)]

        # 获取分页数据
        skip = (page - 1) * 18
        images = list(mongo.db.images.find(query).sort(sort_key).skip(skip).limit(18))
        app.logger.info(f"Found {len(images)} images")
        
        # 记录每张图片的公开状态
        for img in images:
            app.logger.info(f"Image {img.get('filename')}: is_public={img.get('is_public')}")

        # 处理ObjectId和添加文件URL
        for image in images:
            image['_id'] = str(image['_id'])
            image_path = str(Path('uploads') / image['filename'])
            image['url'] = f"/{image_path.replace(os.sep, '/')}"
            if isinstance(image.get('photo_time'), datetime):
                image['photo_time'] = image['photo_time'].strftime('%Y-%m-%d %H:%M:%S')

        return jsonify({
            'data': images
        })
                
    except Exception as e:
        app.logger.error(f"Error in get_public_images: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 获取所有年份API
@app.route('/api/years')
def get_years():
    """获取所有图片的年份列表"""
    try:
        # 获取私密模式参数
        is_private = request.args.get('private', '').lower() == 'true'
        app.logger.info(f"Getting years for private mode: {is_private}")
        
        # 构建查询条件
        match_stage = {
            '$match': {
                'is_public': False if is_private else True
            }
        }
        
        # 从数据库中获取所有不同的年份
        pipeline = [
            match_stage,
            {
                "$project": {
                    "year": {"$year": {"$toDate": "$photo_time"}}
                }
            },
            {
                "$group": {
                    "_id": "$year"
                }
            },
            {
                "$sort": {"_id": -1}  # 降序排列
            }
        ]
        
        years = list(mongo.db.images.aggregate(pipeline))
        # 提取年份并转换为列表
        year_list = [year["_id"] for year in years]
        app.logger.info(f"Found years: {year_list} for private mode: {is_private}")
        return jsonify({"success": True, "years": year_list})
    except Exception as e:
        app.logger.error(f"Error getting years: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

# 上传页面路由
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': '没有文件被上传'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': '不支持的文件类型'}), 400
        
        try:
            # 保存文件
            file_path = save_image(file, app.config['UPLOAD_FOLDER'])
            
            # 获取元数据
            metadata = get_image_metadata(file_path)
            
            # 保存到数据库
            image_data = {
                'filename': Path(file_path).name,
                'path': file_path,
                'upload_time': datetime.now(),
                'photo_time': metadata.get('photo_time', datetime.now()),  # 使用拍摄时间
                'year': metadata.get('year', datetime.now().year),  # 年份
                'month': metadata.get('month', datetime.now().month),  # 月份
                'metadata': metadata,
                'is_public': True,  # 默认设置为公开
                'likes': 0,
                'tags': []
            }
            
            mongo.db.images.insert_one(image_data)
            
            return jsonify({
                'message': '文件上传成功',
                'filename': Path(file_path).name
            })
            
        except Exception as e:
            app.logger.error(f"上传文件时发生错误: {str(e)}")
            return jsonify({'error': '上传文件时发生错误'}), 500

    return render_template('upload.html')

# 管理页面路由
@app.route('/manage')
def manage():
    return render_template('manage.html')

# 获取图片列表API
@app.route('/api/images')
def get_images():
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 12))
    tag = request.args.get('tag', '')
    privacy = request.args.get('privacy', 'all')
    
    # 构建查询条件
    query = {}
    if tag:
        query['tags'] = tag
    if privacy != 'all':
        query['is_public'] = privacy == 'public'
    
    # 获取总数
    total = mongo.db.images.count_documents(query)
    
    # 获取分页数据
    images = list(mongo.db.images.find(query)
                 .sort('upload_time', -1)
                 .skip((page - 1) * size)
                 .limit(size))
    
    app.logger.debug(f'获取到的图片数据: {images}')
    
    # 转换ObjectId为字符串
    for image in images:
        image['_id'] = str(image['_id'])
        # 确保is_public字段存在
        if 'is_public' not in image:
            image['is_public'] = False
        # 确保tags字段存在
        if 'tags' not in image:
            image['tags'] = []
        # 确保likes字段存在
        if 'likes' not in image:
            image['likes'] = 0
        # 确保photo_time字段存在，如果不存在则使用upload_time
        if 'photo_time' not in image and 'upload_time' in image:
            image['photo_time'] = image['upload_time']
            app.logger.debug(f'使用upload_time作为photo_time: {image["photo_time"]}')
        
        # 将datetime对象转换为ISO格式字符串
        if 'photo_time' in image:
            app.logger.debug(f'处理前的photo_time: {image["photo_time"]} 类型: {type(image["photo_time"])}')
            if image['photo_time']:
                try:
                    if isinstance(image['photo_time'], str):
                        # 如果已经是字符串，尝试解析它
                        dt = datetime.fromisoformat(image['photo_time'].replace('Z', '+00:00'))
                        image['photo_time'] = dt.isoformat()
                    else:
                        image['photo_time'] = image['photo_time'].isoformat()
                    app.logger.debug(f'处理后的photo_time: {image["photo_time"]}')
                except Exception as e:
                    app.logger.error(f'转换photo_time时出错: {e}')
                    image['photo_time'] = None
        
        if 'upload_time' in image and image['upload_time']:
            try:
                if isinstance(image['upload_time'], str):
                    dt = datetime.fromisoformat(image['upload_time'].replace('Z', '+00:00'))
                    image['upload_time'] = dt.isoformat()
                else:
                    image['upload_time'] = image['upload_time'].isoformat()
            except Exception as e:
                app.logger.error(f'转换upload_time时出错: {e}')
                image['upload_time'] = None
    
    app.logger.debug(f'处理后的图片数据: {images}')
    
    return jsonify({
        'success': True,
        'images': images,
        'total': total
    })

# 更新图片信息API
@app.route('/api/update_image/<image_id>', methods=['POST'])
def update_image(image_id):
    """更新图片信息"""
    try:
        data = request.get_json()
        
        # 验证用户权限
        image = mongo.db.images.find_one({'_id': ObjectId(image_id)})
        if not image or ('username' in session and image.get('username') != session['username']):
            return jsonify({'error': '没有权限修改此图片'}), 403
        
        update_data = {}
        if 'tags' in data:
            update_data['tags'] = data['tags']
        if 'is_public' in data:
            update_data['is_public'] = data['is_public']  # 只使用 is_public 字段
        
        # 更新数据库
        result = mongo.db.images.update_one(
            {'_id': ObjectId(image_id)},
            {'$set': update_data}
        )
        
        if result.modified_count > 0:
            return jsonify({'success': True, 'message': '更新成功'})
        else:
            return jsonify({'error': '更新失败'}), 400
            
    except Exception as e:
        app.logger.error(f"Error updating image {image_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 删除图片API
@app.route('/api/images', methods=['DELETE'])
def delete_images():
    image_ids = request.json.get('image_ids', [])
    if not image_ids:
        return jsonify({'error': '没有选择要删除的图片'}), 400
    
    # 获取要删除的图片信息
    images = list(mongo.db.images.find({'_id': {'$in': [ObjectId(id) for id in image_ids]}}))
    
    # 删除文件
    for image in images:
        try:
            os.remove(image['path'])
        except OSError:
            pass  # 忽略文件不存在的错误
    
    # 从数据库中删除记录
    result = mongo.db.images.delete_many({'_id': {'$in': [ObjectId(id) for id in image_ids]}})
    
    return jsonify({
        'message': f'成功删除 {result.deleted_count} 张图片',
        'deleted_count': result.deleted_count
    })

# 获取所有标签API
@app.route('/api/tags')
def get_tags():
    # 获取所有不重复的标签
    tags = mongo.db.images.distinct('tags')
    return jsonify(tags)

# 点赞API
@app.route('/api/like/<image_id>', methods=['POST'])
def like_image(image_id):
    try:
        # 获取图片信息
        image = mongo.db.images.find_one({'_id': ObjectId(image_id)})
        if not image:
            return jsonify({'error': '图片不存在'}), 404
            
        # 更新点赞数
        current_likes = image.get('likes', 0)
        new_likes = current_likes + 1
        
        # 更新数据库
        mongo.db.images.update_one(
            {'_id': ObjectId(image_id)},
            {'$set': {'likes': new_likes}}
        )
        
        return jsonify({
            'success': True,
            'liked': True,
            'likes': new_likes
        })
        
    except Exception as e:
        app.logger.error(f'Error handling like for image {image_id}: {str(e)}')
        return jsonify({'error': str(e)}), 500

# 提供图片文件访问
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """提供图片文件访问"""
    try:
        # 添加错误日志以帮助调试
        app.logger.info(f"Attempting to serve file: {filename}")
        app.logger.info(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
        
        # 使用 pathlib.Path 处理路径
        file_path = Path(app.config['UPLOAD_FOLDER']) / filename
        app.logger.info(f"Full file path: {file_path.as_posix()}")
        
        if not file_path.exists():
            app.logger.error(f"File not found: {file_path}")
            return "File not found", 404
            
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        app.logger.error(f"Error serving file {filename}: {str(e)}")
        return "Error serving file", 500

# 批量删除图片
@app.route('/api/images/batch-delete', methods=['POST'])
def batch_delete_images():
    """批量删除图片"""
    try:
        data = request.get_json()
        image_ids = data.get('image_ids', [])
        
        if not image_ids:
            return jsonify({'error': '没有选择要删除的图片'}), 400
            
        # 获取要删除的图片信息
        images = list(mongo.db.images.find({'_id': {'$in': [ObjectId(id) for id in image_ids]}}))
        
        # 删除文件
        for image in images:
            file_path = Path(app.config['UPLOAD_FOLDER']) / image['filename']
            try:
                if file_path.exists():
                    file_path.unlink()
            except Exception as e:
                app.logger.error(f"删除文件失败 {file_path}: {str(e)}")
        
        # 从数据库中删除记录
        result = mongo.db.images.delete_many({'_id': {'$in': [ObjectId(id) for id in image_ids]}})
        
        return jsonify({
            'message': f'成功删除 {result.deleted_count} 张图片',
            'deleted_count': result.deleted_count
        })
    except Exception as e:
        app.logger.error(f"批量删除图片时发生错误: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 批量更新标签
@app.route('/api/images/batch-tags', methods=['POST'])
def batch_update_tags():
    """批量更新图片标签"""
    try:
        data = request.get_json()
        image_ids = data.get('image_ids', [])
        tags = data.get('tags', [])
        
        if not image_ids:
            return jsonify({'error': '没有选择要更新的图片'}), 400
            
        if not tags:
            return jsonify({'error': '没有提供标签'}), 400
        
        # 更新数据库中的标签
        result = mongo.db.images.update_many(
            {'_id': {'$in': [ObjectId(id) for id in image_ids]}},
            {'$set': {'tags': tags}}
        )
        
        return jsonify({
            'success': True,
            'message': f'成功更新 {result.modified_count} 张图片的标签'
        })
    except Exception as e:
        app.logger.error(f"批量更新标签时发生错误: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 批量更新公开状态
@app.route('/api/images/batch-public', methods=['POST'])
def batch_update_public():
    """批量更新图片公开状态"""
    try:
        data = request.get_json()
        image_ids = data.get('image_ids', [])
        is_public = data.get('is_public', True)
        
        if not image_ids:
            return jsonify({'error': '未选择任何图片'}), 400
            
        # 验证用户权限
        if 'username' not in session:
            return jsonify({'error': '请先登录'}), 401
            
        # 将ObjectId字符串转换为ObjectId对象
        object_ids = [ObjectId(id) for id in image_ids]
        
        # 更新数据库
        result = mongo.db.images.update_many(
            {'_id': {'$in': object_ids}},  # 移除 username 限制
            {'$set': {'is_public': is_public}}  # 只使用 is_public 字段
        )
        
        if result.modified_count > 0:
            return jsonify({
                'success': True,
                'message': f'成功更新{result.modified_count}张图片的公开状态'
            })
        else:
            return jsonify({'error': '未找到可更新的图片'}), 404
            
    except Exception as e:
        app.logger.error(f"Error in batch_update_public: {str(e)}")
        return jsonify({'error': str(e)}), 500

# 更新所有图片的拍摄时间
@app.route('/api/update_all_photo_times')
def update_all_photo_times():
    """更新所有图片的拍摄时间"""
    try:
        # 获取所有图片记录
        images = list(mongo.db.images.find())
        updated_count = 0
        error_count = 0
        error_details = []
        
        for image in images:
            try:
                # 使用 pathlib.Path 处理文件路径
                file_path = Path(app.config['UPLOAD_FOLDER']) / image['filename']
                
                if not file_path.exists():
                    error_msg = f"文件不存在: {file_path}"
                    app.logger.error(error_msg)
                    error_count += 1
                    error_details.append(error_msg)
                    continue
                
                # 获取照片拍摄时间
                photo_time = get_photo_time(str(file_path))
                
                # 更新数据库记录
                mongo.db.images.update_one(
                    {'_id': image['_id']},
                    {'$set': {'photo_time': photo_time}}
                )
                updated_count += 1
                app.logger.info(f"Updated photo time for {image['filename']}: {photo_time}")
                
            except Exception as e:
                error_msg = f"更新 {image['filename']} 时出错: {str(e)}"
                app.logger.error(error_msg)
                error_count += 1
                error_details.append(error_msg)
        
        message = f'更新完成：成功 {updated_count} 个，失败 {error_count} 个'
        if error_details:
            message += '\n\n错误详情：\n' + '\n'.join(error_details[:5])  # 只显示前5个错误
            if len(error_details) > 5:
                message += f'\n... 等共 {len(error_details)} 个错误'
        
        return jsonify({
            'success': updated_count > 0,  # 只要有更新成功的就返回true
            'message': message,
            'updated_count': updated_count,
            'error_count': error_count,
            'has_errors': error_count > 0
        })
        
    except Exception as e:
        app.logger.error(f"Error in update_all_photo_times: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'更新过程中发生错误: {str(e)}',
            'error': str(e)
        }), 500

# 主程序入口
if __name__ == '__main__':
    try:
        # 设置日志级别
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # 获取本机IP地址
        import socket
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        
        # 输出访问地址
        app.logger.info(f"Starting server...")
        app.logger.info(f"Local access: http://127.0.0.1:5000")
        app.logger.info(f"Network access: http://{local_ip}:5000")
        
        # 检查端口是否被占用
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 5000))
        if result == 0:
            app.logger.error("Port 5000 is already in use!")
            app.logger.info("Trying to use an alternative port...")
            # 尝试使用备用端口
            port = 5001
        else:
            port = 5000
        sock.close()
        
        # 在所有网络接口上运行，允许局域网访问
        app.run(
            host='0.0.0.0',
            port=port,
            debug=True,
            use_reloader=True,
            threaded=True
        )
    except Exception as e:
        app.logger.error(f"Error starting server: {str(e)}")
        raise
