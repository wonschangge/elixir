from typing import List  # 导入List类型提示

from elixir.filters.utils import Filter, FilterContext  # 导入Filter和FilterContext类
from elixir.filters.projects import project_filters, default_filters  # 导入项目过滤器和默认过滤器

# 返回给定项目名称在提供的过滤器上下文下适用的过滤器列表
def get_filters(ctx: FilterContext, project_name: str) -> List[Filter]:
    filter_classes = project_filters.get(project_name, default_filters)  # 获取项目的过滤器类，如果不存在则使用默认过滤器
    filters = []  # 初始化过滤器列表

    for filter_cls in filter_classes:  # 遍历过滤器类
        if type(filter_cls) == tuple and len(filter_cls) == 2:  # 检查是否为二元组
            cls, kwargs = filter_cls  # 解包类和关键字参数
            filters.append(cls(**kwargs))  # 使用关键字参数实例化类并添加到过滤器列表
        elif type(filter_cls) == type:  # 检查是否为类
            filters.append(filter_cls())  # 实例化类并添加到过滤器列表
        else:
            raise ValueError(f"Invalid filter: {filter_cls}, "  # 抛出异常，无效的过滤器
                    "should be either a two element tuple or a type. "  # 应该是二元组或类
                    "Make sure project_filters in project.py is valid.")  # 确保project.py中的project_filters有效

    return [f for f in filters if f.check_if_applies(ctx)]  # 返回适用于当前上下文的过滤器列表

