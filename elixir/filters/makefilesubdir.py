from os.path import dirname
import re
from .utils import Filter, FilterContext, decode_number, encode_number, filename_without_ext_matches

# 过滤器用于处理 Makefile 中的目录包含语句，如：
# subdir-y += dir
# 示例：u-boot/v2023.10/source/examples/Makefile#L9
class MakefileSubdirFilter(Filter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # 调用父类的初始化方法
        self.makefilesubdir = []  # 初始化一个列表，用于存储匹配到的子目录

    def check_if_applies(self, ctx) -> bool:
        # 检查当前上下文是否适用于此过滤器
        return super().check_if_applies(ctx) and \
            filename_without_ext_matches(ctx.filepath, {'Makefile'})  # 检查文件名是否为 Makefile

    def transform_raw_code(self, ctx, code: str) -> str:
        # 转换原始代码，保留匹配到的子目录
        def keep_makefilesubdir(m):
            self.makefilesubdir.append(m.group(5))  # 将匹配到的子目录添加到列表中
            n = encode_number(len(self.makefilesubdir))  # 编码子目录的索引
            return f'{ m.group(1) }{ m.group(2) }{ m.group(3) }{ m.group(4) }__KEEPMAKESUBDIR__{ n }{ m.group(6) }'  # 替换匹配到的内容

        return re.sub('(subdir-y)(\s+)(\+=|:=)(\s+)([-\w]+)(\s*|$)', keep_makefilesubdir, code, flags=re.MULTILINE)  # 使用正则表达式进行替换

    def untransform_formatted_code(self, ctx: FilterContext, html: str) -> str:
        # 将转换后的 HTML 代码还原
        def replace_makefilesubdir(m):
            w = self.makefilesubdir[decode_number(m.group(1)) - 1]  # 解码子目录的索引
            filedir = dirname(ctx.filepath)  # 获取文件所在的目录

            if filedir != '/':
                filedir += '/'  # 如果目录不是根目录，添加斜杠

            npath = f'{ filedir }{ w }/Makefile'  # 构建新的路径
            return f'<a href="{ ctx.get_absolute_source_url(npath) }">{ w }</a>'  # 生成超链接

        return re.sub('__KEEPMAKESUBDIR__([A-J]+)', replace_makefilesubdir, html, flags=re.MULTILINE)  # 使用正则表达式进行替换

