import re
from urllib.parse import quote
from .utils import Filter, FilterContext, encode_number, decode_number

# 过滤器类，用于在文档中查找与设备树兼容的字符串（B系列）
# syscon
# 示例：linux/v6.9.4/source/Documentation/devicetree/bindings/thermal/brcm,avs-ro-thermal.yaml#L17
# 注意：这也会找到注释、描述和其他可能无关属性中的字符串
class DtsCompDocsFilter(Filter):
    # 初始化方法
    def __init__(self, *args, **kwargs):
        # 调用父类的初始化方法
        super().__init__(*args, **kwargs)
        # 初始化存储 B 系列设备树兼容字符串的列表
        self.dtscompB = []

    # 检查过滤器是否适用于当前上下文
    def check_if_applies(self, ctx) -> bool:
        # 返回是否满足条件：父类检查通过、查询中包含 'dts-comp'、文件路径以 '/Documentation/devicetree/bindings' 开头
        return super().check_if_applies(ctx) and \
            ctx.query.query('dts-comp') and \
            ctx.filepath.startswith('/Documentation/devicetree/bindings')

    # 转换原始代码
    def transform_raw_code(self, ctx, code: str) -> str:
        # 定义一个内部函数，用于保留符合条件的 B 系列设备树兼容字符串
        def keep_dtscompB(m):
            # 获取匹配的文本
            text = m.group(1)

            # 如果查询中存在该字符串，则将其添加到 dtscompB 列表，并返回占位符
            if ctx.query.query('dts-comp-exists', quote(text)):
                self.dtscompB.append(text)
                return f'__KEEPDTSCOMPB__{ encode_number(len(self.dtscompB)) }'
            else:
                # 否则返回原始匹配的文本
                return m.group(0)

        # 使用正则表达式替换代码中的 B 系列设备树兼容字符串
        return re.sub('([\w-]+,?[\w-]+)', keep_dtscompB, code, flags=re.MULTILINE)

    # 反转换格式化后的代码
    def untransform_formatted_code(self, ctx: FilterContext, html: str) -> str:
        # 定义一个内部函数，用于将占位符替换为 HTML 链接
        def replace_dtscompB(m):
            # 解码占位符中的索引
            i = self.dtscompB[decode_number(m.group(1)) - 1]

            # 返回带有链接的 HTML 格式字符串
            return f'<a class="ident" href="{ ctx.get_ident_url(i, "B") }">{ i }</a>'

        # 使用正则表达式替换 HTML 中的占位符
        return re.sub('__KEEPDTSCOMPB__([A-J]+)', replace_dtscompB, html, flags=re.MULTILINE)

