import re
from .utils import Filter, FilterContext, encode_number, decode_number, extension_matches

# Filters for cpp includes like these:
# #include <file>

# Such filters work typically for standalone projects (like kernels and bootloaders)
# If we make references to other projects, we could
# end up with links to headers which are outside the project
# Example: u-boot/v2023.10/source/env/embedded.c#L16
class CppPathIncFilter(Filter):
    """
    CppPathIncFilter 类继承自 Filter，用于处理 C/C++ 文件中的 #include 指令。
    它会根据文件路径和扩展名判断是否应用过滤器，并在转换原始代码时保留特定的 #include 路径。
    """
    def __init__(self, *args, **kwargs):
        # 调用父类构造函数初始化
        super().__init__(*args, **kwargs)
        # 初始化 cpppathinc 列表，用于存储需要保留的 #include 路径
        self.cpppathinc = []

    def check_if_applies(self, ctx) -> bool:
        # 检查是否应应用此过滤器
        # 检查文件扩展名是否为指定的 C/C++ 相关扩展名之一
        return super().check_if_applies(ctx) and \
                extension_matches(ctx.filepath, {'dts', 'dtsi', 'c', 'cc', 'cpp', 'c++', 'cxx', 'h', 's'})

    def transform_raw_code(self, ctx, code: str) -> str:
        # 定义一个内部函数，用于处理匹配到的 #include 指令
        def keep_cpppathinc(m):
            # 获取匹配对象的各组内容
            m1 = m.group(1)
            m2 = m.group(2)
            inc = m.group(3)
            # 如果路径以 "asm/" 开头，则保留原字符串
            if re.match('^asm/.*', inc):
                return m.group(0)
            else:
                # 否则将路径添加到 cpppathinc 列表中
                self.cpppathinc.append(inc)
                # 替换为特殊标记，其中包含路径的索引
                return f'{ m1 }#include{ m2 }<__KEEPCPPPATHINC__{ encode_number(len(self.cpppathinc)) }>'

        # 使用正则表达式替换所有 #include 指令
        return re.sub('^(\s*)#include(\s*)<(.*?)>', keep_cpppathinc, code, flags=re.MULTILINE)

    def untransform_formatted_code(self, ctx: FilterContext, html: str) -> str:
        # 定义一个内部函数，用于将特殊标记还原为原始的 #include 路径
        def replace_cpppathinc(m):
            # 解码特殊标记中的索引
            w = self.cpppathinc[decode_number(m.group(1)) - 1]
            # 构建包含链接的 HTML 代码
            path = f'/include/{ w }'
            return f'<a href="{ ctx.get_absolute_source_url(path) }">{ w }</a>'

        # 使用正则表达式替换所有特殊标记
        return re.sub('__KEEPCPPPATHINC__([A-J]+)', replace_cpppathinc, html, flags=re.MULTILINE)

