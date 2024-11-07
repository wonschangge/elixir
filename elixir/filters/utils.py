import re  # 导入正则表达式模块
import os  # 导入操作系统模块
from dataclasses import dataclass  # 导入数据类装饰器
from typing import Callable, List  # 导入类型提示相关的模块
from ..query import Query  # 从上级模块导入Query类

# Context data used by Filters
# 标签：浏览版本，未加引号
# 家族：文件所属家族
# 路径：文件路径
# get_ident_url: 返回传递的标识符的URL的函数
# get_absolute_source_url: 返回传递的绝对路径文件的URL的函数
# get_relative_source_url: 返回当前文件目录中文件的URL的函数
@dataclass  # 使用数据类装饰器
class FilterContext:
    query: Query  # 查询对象
    tag: str  # 文件标签
    family: str  # 文件家族
    filepath: str  # 文件路径
    get_ident_url: str  # 获取标识符URL的字符串（可能是函数名）
    get_absolute_source_url: Callable[[str], str]  # 获取绝对路径文件URL的函数
    get_relative_source_url: Callable[[str], str]  # 获取相对路径文件URL的函数

# Filter接口/基类
# 过滤器用于向Pygments格式化成HTML的代码中添加额外信息，如链接。
# 过滤器由两部分组成：第一部分在未格式化的代码上运行，转换它以标记有趣的标识符，例如关键字。
# 如何标记标识符取决于过滤器，但重要的是要小心不要破坏格式。
# 第二部分在HTML上运行，用HTML代码替换第一部分留下的标记。
# path_exceptions: 正则表达式列表，如果过滤文件的路径与列表中的某个正则表达式匹配，则禁用过滤器
class Filter:
    def __init__(self, path_exceptions: List[str] = []):  # 初始化方法，接受一个正则表达式列表作为参数
        self.path_exceptions = path_exceptions  # 存储路径例外

    # 返回True如果过滤器可以应用于具有给定路径的文件
    def check_if_applies(self, ctx: FilterContext) -> bool:  # 检查过滤器是否适用于给定上下文
        for p in self.path_exceptions:  # 遍历路径例外列表
            if re.match(p, ctx.filepath):  # 如果文件路径与某个正则表达式匹配
                return False  # 返回False，表示不适用

        return True  # 否则返回True，表示适用

    # 通过转换原始源代码来添加过滤器所需的信息。
    # 已知的标识符通过'\033[31m'和'\033[0m'进行标记。注意这些标记的标识符通常由IdentFilter或KconfigIdentsFilter处理。
    def transform_raw_code(self, ctx: FilterContext, code: str) -> str:  # 转换原始代码的方法
        return code  # 返回转换后的代码

    # 将`transform_raw_code`留下的信息替换为目标HTML
    # html: 代码格式化器生成的HTML输出
    def untransform_formatted_code(self, ctx: FilterContext, html: str) -> str:  # 反转换格式化后的代码
        return html  # 返回反转换后的HTML

# 如果从filepath获取的文件名（去除扩展名）在allowed_filenames_without_ext可迭代对象中，则返回True
def filename_without_ext_matches(filepath: str, allowed_filenames_without_ext) -> bool:  # 检查文件名是否匹配
    filename = os.path.basename(filepath)  # 获取文件名
    filename_without_ext, _ = os.path.splitext(filename)  # 去除文件扩展名
    return filename_without_ext in allowed_filenames_without_ext  # 判断文件名是否在允许的文件名列表中

# 如果从filepath获取的文件扩展名在allowed_extensions可迭代对象中，则返回True
def extension_matches(filepath: str, allowed_extensions) -> bool:  # 检查文件扩展名是否匹配
    _, file_ext_dot = os.path.splitext(filepath)  # 获取文件扩展名
    file_ext = file_ext_dot[1:].lower()  # 去除点并转小写
    return file_ext in allowed_extensions  # 判断扩展名是否在允许的扩展名列表中

# 将整数编码为字符字符串（A-J）
# encode_number(10239) = 'BACDJ'
def encode_number(number):  # 编码数字为字符串
    result = ''  # 初始化结果字符串

    while number != 0:  # 当数字不为0时循环
        number, rem = divmod(number, 10)  # 计算商和余数
        rem = chr(ord('A') + rem)  # 将余数转换为字符
        result = rem + result  # 构建结果字符串

    return result  # 返回编码后的字符串

# 解码由encode_number生成的字符字符串为整数
# decode_number('BACDJ') = 10239
def decode_number(string):  # 解码字符串为数字
    result = ''  # 初始化结果字符串

    while string != '':  # 当字符串不为空时循环
        string, char = string[:-1], string[-1]  # 分离最后一个字符
        char = str(ord(char) - ord('A'))  # 将字符转换为数字
        result = char + result  # 构建结果字符串

    return int(result)  # 返回解码后的整数

