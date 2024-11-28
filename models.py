# 导入数据库对象
from app import db

# 定义用户模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)  # 用户ID
    username = db.Column(db.String(150), unique=True, nullable=False)  # 用户名
    password = db.Column(db.String(150), nullable=False)  # 密码
