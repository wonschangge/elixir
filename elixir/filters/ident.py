import re  # 导入正则表达式模块
from .utils import Filter, FilterContext, encode_number, decode_number  # 从 utils 模块导入必要的工具函数

# 标识符链接过滤器
# 将通过 Query.query('file') 标记的标识符替换为指向标识页面的链接。
# 如果 Query.query('file') 检测到文件属于可以包含索引标识符的家族，
# 它会处理文件，通过向在定义数据库中有条目的标记添加不可打印的标记
# ('\033[31m' + token + b'\033[0m')。此过滤器将这些标记的令牌替换为它们的标识页面链接，
# 除非令牌以 CONFIG_ 开头 - 这些令牌由 Kconfig 过滤器处理。
class IdentFilter(Filter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # 调用父类的构造方法
        self.idents = []  # 初始化一个列表来存储标识符

    def transform_raw_code(self, ctx, code: str) -> str:
        """
        转换原始代码，将标记的标识符替换为占位符。
        
        :param ctx: 上下文对象
        :param code: 原始代码字符串
        :return: 替换后的代码字符串
        """
        def sub_func(m):
            self.idents.append(m.group(1))  # 将匹配的标识符添加到列表中
            return '__KEEPIDENTS__' + encode_number(len(self.idents))  # 返回占位符

        return re.sub('\033\[31m(?!CONFIG_)(.*?)\033\[0m', sub_func, code, flags=re.MULTILINE)  # 使用正则表达式替换标记的标识符

    def untransform_formatted_code(self, ctx: FilterContext, html: str) -> str:
        """
        反转换格式化后的代码，将占位符替换为实际的标识符链接。
        
        :param ctx: 上下文对象
        :param html: 格式化后的 HTML 字符串
        :return: 替换后的 HTML 字符串
        """
        def sub_func(m):
            i = self.idents[decode_number(m.group(2)) - 1]  # 解码占位符并获取对应的标识符
            link = f'<a class="ident" href="{ ctx.get_ident_url(i) }">{ i }</a>'  # 生成标识符链接
            return str(m.group(1) or '') + link  # 返回带有链接的字符串

        return re.sub('__(<.+?>)?KEEPIDENTS__([A-J]+)', sub_func, html, flags=re.MULTILINE)  # 使用正则表达式替换占位符

