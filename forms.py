# 导入Flask-WTF和WTForms模块
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo

# 定义用户注册表单
class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=150)])  # 用户名字段
    password = PasswordField('Password', validators=[DataRequired()])  # 密码字段
    submit = SubmitField('Sign Up')  # 提交按钮

# 定义用户登录表单
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])  # 用户名字段
    password = PasswordField('Password', validators=[DataRequired()])  # 密码字段
    submit = SubmitField('Login')  # 提交按钮
