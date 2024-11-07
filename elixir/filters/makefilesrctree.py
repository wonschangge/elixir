import re
from .utils import Filter, FilterContext, decode_number, encode_number, filename_without_ext_matches

# 过滤器用于处理 Makefiles 中使用 $(srctree) 引用的文件
# $(srctree)/Makefile
# 示例: u-boot/v2023.10/source/Makefile#L1983
class MakefileSrcTreeFilter(Filter):
    # 初始化过滤器
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # 调用父类的初始化方法
        self.makefilesrctree = []  # 存储 Makefile 中引用的文件路径

    # 检查过滤器是否适用于当前上下文
    def check_if_applies(self, ctx) -> bool:
        # 调用父类的方法检查通用条件
        return super().check_if_applies(ctx) and \
            filename_without_ext_matches(ctx.filepath, {'Makefile'})  # 检查文件名是否为 Makefile

    # 转换原始代码，提取 $(srctree) 引用的文件
    def transform_raw_code(self, ctx, code: str) -> str:
        def keep_makefilesrctree(m):
            if ctx.query.query('exist', ctx.tag, '/' + m.group(1)):  # 检查文件是否存在
                self.makefilesrctree.append(m.group(1))  # 将文件路径添加到列表中
                return f'__KEEPMAKEFILESRCTREE__{ encode_number(len(self.makefilesrctree)) }{ m.group(2) }'  # 替换为占位符
            else:
                return m.group(0)  # 文件不存在时保留原内容

        return re.sub('(?:(?<=\s|=)|(?<=-I))(?!/)\$\(srctree\)/((?:[-\w/]+/)?[-\w\.]+)(\s+|\)|$)',
                      keep_makefilesrctree, code, flags=re.MULTILINE)  # 使用正则表达式替换 $(srctree) 引用

    # 反转换格式化后的代码，将占位符替换为实际链接
    def untransform_formatted_code(self, ctx: FilterContext, html: str) -> str:
        def replace_makefilesrctree(m):
            w = self.makefilesrctree[decode_number(m.group(1)) - 1]  # 获取文件路径
            url = ctx.get_absolute_source_url(w)  # 获取文件的绝对 URL
            return f'<a href="{ url }">$(srctree)/{ w }</a>'  # 生成 HTML 链接

        return re.sub('__KEEPMAKEFILESRCTREE__([A-J]+)', replace_makefilesrctree, html, flags=re.MULTILINE)  # 替换占位符

