import re
from .utils import Filter, FilterContext, encode_number, decode_number, extension_matches

# Filter for kconfig identifier in defconfigs
# Replaces defconfig identifiers with links to definitions/references
# `CONFIG_OPTION=y`
# Example: u-boot/v2023.10/source/configs/A13-OLinuXino_defconfig#L1
class DefConfigIdentsFilter(Filter):
    """
    DefConfigIdentsFilter 是一个继承自 Filter 类的类，用于处理特定文件中的配置标识。
    """
    def __init__(self, *args, **kwargs):
        # 调用父类的构造函数
        super().__init__(*args, **kwargs)
        # 初始化一个空列表，用于存储配置标识
        self.defconfigidents = []

    def check_if_applies(self, ctx) -> bool:
        # 检查当前上下文是否适用于此过滤器，并且文件路径以 'defconfig' 结尾
        return super().check_if_applies(ctx) and \
               ctx.filepath.endswith('defconfig')

    def transform_raw_code(self, ctx, code: str) -> str:
        # 定义一个内部函数，用于保留配置标识并替换为特殊标记
        def keep_defconfigidents(m):
            # 将匹配到的配置标识添加到列表中
            self.defconfigidents.append(m.group(1))
            # 返回特殊标记，其中包含编码后的索引
            return '__KEEPDEFCONFIGIDENTS__' + encode_number(len(self.defconfigidents))

        # 使用正则表达式查找所有配置标识，并调用 keep_defconfigidents 函数进行替换
        return re.sub('(CONFIG_[\w]+)', keep_defconfigidents, code, flags=re.MULTILINE)

    def untransform_formatted_code(self, ctx: FilterContext, html: str) -> str:
        # 定义一个内部函数，用于将特殊标记还原为原始配置标识
        def replace_defconfigidents(m):
            # 解码索引并获取对应的配置标识
            i = self.defconfigidents[decode_number(m.group(1)) - 1]
            # 生成带有链接的 HTML 标签
            return f'<a class="ident" href="{ ctx.get_ident_url(i, "K") }">{ i }</a>'

        # 使用正则表达式查找所有特殊标记，并调用 replace_defconfigidents 函数进行替换
        return re.sub('__KEEPDEFCONFIGIDENTS__([A-J]+)', replace_defconfigidents, html, flags=re.MULTILINE)

