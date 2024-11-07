import re
from .utils import Filter, FilterContext, encode_number, decode_number, extension_matches

# 用于在C语言系列文件中过滤DT兼容字符串
# 查找被Query.query('file')识别的名为'compatible'的属性和变量的赋值
# .compatible = "device"
# 示例: u-boot/v2023.10/source/drivers/phy/nop-phy.c#L84
class DtsCompCodeFilter(Filter):
    """
    一个用于处理C语言系列代码文件中DT（设备树）兼容字符串的过滤器类。
    
    参数:
    *args: 传递给父类的可变参数列表。
    **kwargs: 传递给父类的关键字参数字典。
    """
    def __init__(self, *args, **kwargs):
        # 调用父类的初始化方法
        super().__init__(*args, **kwargs)
        # 初始化存储兼容字符串的列表
        self.dtscompC = []

    def check_if_applies(self, ctx) -> bool:
        # 检查当前上下文是否适用于此过滤器
        # 需要满足以下条件：
        # 1. 父类的检查条件通过
        # 2. 当前查询包含'dts-comp'
        # 3. 文件扩展名匹配C语言系列文件
        return super().check_if_applies(ctx) and \
            ctx.query.query('dts-comp') and \
            extension_matches(ctx.filepath, {'c', 'cc', 'cpp', 'c++', 'cxx', 'h', 's'})

    def transform_raw_code(self, ctx, code: str) -> str:
        """
        转换原始代码，保留与'compatible'属性相关的字符串。

        参数:
        ctx: 上下文对象
        code: 原始代码字符串

        返回:
        转换后的代码字符串
        """
        # 如果源文件中没有可能赋值给'compatible'属性的字符串，则直接返回原代码
        compatible_search = re.search('\.(\033\[31m)?compatible(\033\[0m)?\s*=', code, flags=re.MULTILINE)
        if compatible_search is None:
            return code

        def keep_dtscompC(m):
            # 将匹配到的兼容字符串添加到列表中
            self.dtscompC.append(m.group(4))
            # 替换匹配到的字符串为特殊标记
            return f'{ m.group(1) }"__KEEPDTSCOMPC__{ encode_number(len(self.dtscompC)) }"'

        # 使用正则表达式替换所有与'compatible'属性相关的字符串
        return re.sub('(\s*{*\s*\.(\033\[31m)?compatible(\033\[0m)?\s*=\s*)\"(.+?)\"',
                      keep_dtscompC, code, flags=re.MULTILINE)

    def untransform_formatted_code(self, ctx: FilterContext, html: str) -> str:
        """
        反转换格式化后的代码，恢复与'compatible'属性相关的字符串。

        参数:
        ctx: 上下文对象
        html: 格式化后的HTML字符串

        返回:
        恢复后的HTML字符串
        """
        def replace_dtscompC(m):
            # 解码特殊标记并恢复原始字符串
            i = self.dtscompC[decode_number(m.group(1)) - 1]
            # 生成带有链接的HTML代码
            return f'<a class="ident" href="{ ctx.get_ident_url(i, "B") }">{ i }</a>'

        # 使用正则表达式替换所有特殊标记为原始字符串
        return re.sub('__KEEPDTSCOMPC__([A-J]+)', replace_dtscompC, html, flags=re.MULTILINE)

