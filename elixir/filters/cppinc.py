import re
from .utils import Filter, FilterContext, encode_number, decode_number, extension_matches

# Filters for cpp includes like these:
# #include "file"
# Example: musl/v1.2.5/source/src/dirent/dirfd.c#L2
# #include "__dirent.h"
class CppIncFilter(Filter):
    """
    CppIncFilter 是一个过滤器类，用于处理 C++ 包含指令（#include）。
    它继承自 Filter 类，并实现了对特定文件类型中 #include 指令的识别和转换。
    """

    def __init__(self, *args, **kwargs):
        # 调用父类的构造函数
        super().__init__(*args, **kwargs)
        # 初始化一个列表，用于存储处理过的 #include 指令
        self.cppinc = []

    def check_if_applies(self, ctx) -> bool:
        # 检查当前上下文是否适用于此过滤器
        # 需要满足父类的检查条件，并且文件扩展名在指定集合中
        return super().check_if_applies(ctx) and \
               extension_matches(ctx.filepath, {'dts', 'dtsi', 'c', 'cc', 'cpp', 'c++', 'cxx', 'h', 's'})

    def transform_raw_code(self, ctx, code: str) -> str:
        # 定义一个内部函数，用于处理匹配到的 #include 指令
        def keep_cppinc(m):
            # 将匹配到的文件路径添加到 self.cppinc 列表中
            self.cppinc.append(m.group(3))
            # 替换原始的 #include 指令，使用特殊标记 __KEEPCPPINC__
            return f'{m.group(1)}#include{m.group(2)}"__KEEPCPPINC__{encode_number(len(self.cppinc))}"'

        # 使用正则表达式替换所有匹配的 #include 指令
        return re.sub('^(\s*)#include(\s*)\"(.*?)\"', keep_cppinc, code, flags=re.MULTILINE)

    def untransform_formatted_code(self, ctx: FilterContext, html: str) -> str:
        # 定义一个内部函数，用于将特殊标记 __KEEPCPPINC__ 还原为原始的 #include 指令
        def replace_cppinc(m):
            # 根据编码数字从 self.cppinc 列表中获取原始文件路径
            w = self.cppinc[decode_number(m.group(1)) - 1]
            # 生成 HTML 链接，指向原始文件路径
            url = ctx.get_relative_source_url(w)
            return f'<a href="{url}">{w}</a>'

        # 使用正则表达式替换所有特殊标记 __KEEPCPPINC__
        return re.sub('__KEEPCPPINC__([A-J]+)', replace_cppinc, html, flags=re.MULTILINE)

