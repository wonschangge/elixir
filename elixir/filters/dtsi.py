import re  # 导入正则表达式模块
from .utils import Filter, FilterContext, encode_number, decode_number, extension_matches  # 从 utils 模块导入相关工具函数

# Filters for dts includes as follows:
# Replaces include directives in dts/dtsi files with links to source
# /include/ "file"
# Example: u-boot/v2023.10/source/arch/powerpc/dts/t1023si-post.dtsi#L12
class DtsiFilter(Filter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)  # 调用父类的初始化方法
        self.dtsi = []  # 初始化一个列表用于存储 dtsi 文件路径

    # 检查过滤器是否适用于当前文件
    def check_if_applies(self, ctx) -> bool:
        return super().check_if_applies(ctx) and \
                extension_matches(ctx.filepath, {'dts', 'dtsi'}) # 调用父类的方法并检查文件扩展名是否为 dts 或 dtsi

    # 转换原始代码，将 include 指令替换为链接
    def transform_raw_code(self, ctx, code: str) -> str:
        def keep_dtsi(m):
            self.dtsi.append(m.group(3))  # 将匹配到的文件路径添加到 dtsi 列表中
            return f'{ m.group(1) }/include/{ m.group(2) }"__KEEPDTSI__{ encode_number(len(self.dtsi)) }"'  # 替换 include 指令为特殊标记

        return re.sub('^(\s*)/include/(\s*)\"(.*?)\"', keep_dtsi, code, flags=re.MULTILINE)  # 使用正则表达式进行替换

    # 反转换已格式化的代码，将特殊标记还原为链接
    def untransform_formatted_code(self, ctx: FilterContext, html: str) -> str:
        def replace_dtsi(m):
            w = self.dtsi[decode_number(m.group(1)) - 1]  # 解码特殊标记并获取对应的文件路径
            return f'<a href="{ ctx.get_relative_source_url(w) }">{ w }</a>'  # 生成 HTML 链接

        return re.sub('__KEEPDTSI__([A-J]+)', replace_dtsi, html, flags=re.MULTILINE)  # 使用正则表达式进行替换

