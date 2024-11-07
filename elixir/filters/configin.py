import re
from .utils import Filter, FilterContext, decode_number, encode_number, filename_without_ext_matches

# Filters for Config.in includes
# source "path/file"
# Example: uclibc-ng/v1.0.47/source/extra/Configs/Config.in#L176
class ConfigInFilter(Filter):
    """
    ConfigInFilter 是一个继承自 Filter 的类，用于处理特定文件中的配置项。
    """
    def __init__(self, *args, **kwargs):
        # 调用父类的构造函数
        super().__init__(*args, **kwargs)
        # 初始化一个空列表，用于存储配置项
        self.configin = []

    def check_if_applies(self, ctx) -> bool:
        # 检查当前上下文是否适用此过滤器，并且文件名是否符合要求
        return super().check_if_applies(ctx) and \
               filename_without_ext_matches(ctx.filepath, {'Config'})

    def transform_raw_code(self, ctx, code: str) -> str:
        # 定义一个内部函数，用于处理匹配到的配置项
        def keep_configin(m):
            # 将匹配到的配置项添加到 self.configin 列表中
            self.configin.append(m.group(4))
            # 替换原始代码中的配置项为特殊标记
            return f'{ m.group(1) }{ m.group(2) }{ m.group(3) }"__KEEPCONFIGIN__{ encode_number(len(self.configin)) }"'
        
        # 使用正则表达式替换代码中的配置项
        return re.sub('^(\s*)(source)(\s*)\"(.*)\"', keep_configin, code, flags=re.MULTILINE)

    def untransform_formatted_code(self, ctx: FilterContext, html: str) -> str:
        # 定义一个内部函数，用于将特殊标记还原为原始配置项
        def replace_configin(m):
            # 从 self.configin 列表中获取对应的配置项
            w = self.configin[decode_number(m.group(1)) - 1]
            # 生成 HTML 链接
            return f'<a href="{ ctx.get_absolute_source_url(w) }">{ w }</a>'
        
        # 使用正则表达式将特殊标记还原为原始配置项
        return re.sub('__KEEPCONFIGIN__([A-J]+)', replace_configin, html, flags=re.MULTILINE)

