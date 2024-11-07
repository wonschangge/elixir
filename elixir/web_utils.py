import re
from urllib import parse
import falcon

def validate_project(project):
    # 检查项目名称是否不为空，并且符合正则表达式模式
    if project is not None and re.match(r'^[a-zA-Z0-9_.,:/-]+$', project):
        # 去除项目名称首尾的空白字符并返回
        return project.strip()

# 验证并解码项目参数
class ProjectConverter(falcon.routing.BaseConverter):
    # 转换方法，处理传入的字符串值
    def convert(self, value: str):
        # 解码 URL 编码的字符串
        value = parse.unquote(value)
        # 验证项目名称
        project = validate_project(value)
        # 如果项目名称无效，抛出 HTTP 400 错误
        if project is None:
            raise falcon.HTTPBadRequest('Error', '无效的项目名称')
        # 返回验证后的项目名称
        return project

def validate_version(version):
    # 检查版本号是否不为空，并且符合正则表达式模式
    if version is not None and re.match(r'^[a-zA-Z0-9_.,:/-]+$', version):
        # 去除版本号首尾的空白字符并返回
        return version.strip()

def validate_ident(ident):
    # 检查标识符是否不为空，并且符合正则表达式模式
    if ident is not None and re.match(r'^[A-Za-z0-9_,.+?#-]+$', ident):
        # 去除标识符首尾的空白字符并返回
        return ident.strip()

# 验证并解码标识符参数
class IdentConverter(falcon.routing.BaseConverter):
    # 转换方法，处理传入的字符串值
    def convert(self, value: str):
        # 解码 URL 编码的字符串
        value = parse.unquote(value)
        # 验证标识符
        return validate_ident(value)

