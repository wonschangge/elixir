# 从 ident 模块导入 IdentFilter 类
from .ident import IdentFilter

# 从 cppinc 模块导入 CppIncFilter 类
from .cppinc import CppIncFilter
# 从 cpppathinc 模块导入 CppPathIncFilter 类
from .cpppathinc import CppPathIncFilter

# 从 defconfig 模块导入 DefConfigIdentsFilter 类
from .defconfig import DefConfigIdentsFilter
# 从 configin 模块导入 ConfigInFilter 类
from .configin import ConfigInFilter

# 从 kconfig 模块导入 KconfigFilter 类
from .kconfig import KconfigFilter
# 从 kconfigidents 模块导入 KconfigIdentsFilter 类
from .kconfigidents import KconfigIdentsFilter

# 从 dtsi 模块导入 DtsiFilter 类
from .dtsi import DtsiFilter
# 从 dtscompdocs 模块导入 DtsCompDocsFilter 类
from .dtscompdocs import DtsCompDocsFilter
# 从 dtscompcode 模块导入 DtsCompCodeFilter 类
from .dtscompcode import DtsCompCodeFilter
# 从 dtscompdts 模块导入 DtsCompDtsFilter 类
from .dtscompdts import DtsCompDtsFilter

# 从 makefileo 模块导入 MakefileOFilter 类
from .makefileo import MakefileOFilter
# 从 makefiledtb 模块导入 MakefileDtbFilter 类
from .makefiledtb import MakefileDtbFilter
# 从 makefiledir 模块导入 MakefileDirFilter 类
from .makefiledir import MakefileDirFilter
# 从 makefilesubdir 模块导入 MakefileSubdirFilter 类
from .makefilesubdir import MakefileSubdirFilter
# 从 makefilefile 模块导入 MakefileFileFilter 类
from .makefilefile import MakefileFileFilter
# 从 makefilesrctree 模块导入 MakefileSrcTreeFilter 类
from .makefilesrctree import MakefileSrcTreeFilter
# 从 makefilesubdir 模块再次导入 MakefileSubdirFilter 类
from .makefilesubdir import MakefileSubdirFilter

# 从 ts 模块导入 TsFilter 类
# from .ts import TsFilter

# 定义默认过滤器列表，应用于所有项目
default_filters = [
    DtsCompCodeFilter,  # DTS 组件代码过滤器
    DtsCompDtsFilter,   # DTS 组件 DTS 文件过滤器
    DtsCompDocsFilter,  # DTS 组件文档过滤器
    IdentFilter,        # 标识符过滤器
    CppIncFilter,       # C++ 包含文件过滤器
]

# 定义 Kconfig 文件的通用过滤器列表
common_kconfig_filters = [
    KconfigFilter,          # Kconfig 文件过滤器
    KconfigIdentsFilter,    # Kconfig 标识符过滤器
    DefConfigIdentsFilter,  # DefConfig 标识符过滤器
]

# 定义 Makefile 的通用过滤器列表
common_makefile_filters = [
    MakefileOFilter,        # Makefile 输出文件过滤器
    MakefileDtbFilter,      # Makefile DTB 文件过滤器
    MakefileDirFilter,      # Makefile 目录过滤器
    MakefileFileFilter,     # Makefile 文件过滤器
    MakefileSubdirFilter,   # Makefile 子目录过滤器
    MakefileSrcTreeFilter,  # Makefile 源树过滤器
]

# 定义每个项目的自定义过滤器字典
# 未在字典中列出的项目仅使用默认过滤器
# 使用 `*` 解包上述定义的过滤器列表
# 可以通过将过滤器类和选项字典组合成元组来传递额外选项给过滤器
# 例如：(FilterCls, {"option": True})
# 有关可用选项的信息，请参阅过滤器文件和 utils.py
project_filters = {
    'amazon-freertos': [
        *default_filters,       # 使用默认过滤器
        MakefileSubdirFilter,   # 添加 Makefile 子目录过滤器
    ],
    'arm-trusted-firmware': [
        *default_filters,       # 使用默认过滤器
        CppPathIncFilter,       # 添加 C++ 路径包含文件过滤器
    ],
    'barebox': [
        *default_filters,           # 使用默认过滤器
        DtsiFilter,                 # 添加 DTSI 文件过滤器
        *common_kconfig_filters,    # 添加 Kconfig 文件的通用过滤器
        CppPathIncFilter,           # 添加 C++ 路径包含文件过滤器
        *common_makefile_filters,   # 添加 Makefile 的通用过滤器
    ],
    'coreboot': [
        *default_filters,           # 使用默认过滤器
        DtsiFilter,                 # 添加 DTSI 文件过滤器
        *common_kconfig_filters,    # 添加 Kconfig 文件的通用过滤器
        *common_makefile_filters,   # 添加 Makefile 的通用过滤器
    ],
    'linux': [
        *default_filters,           # 使用默认过滤器
        DtsiFilter,                 # 添加 DTSI 文件过滤器
        *common_kconfig_filters,    # 添加 Kconfig 文件的通用过滤器
        *common_makefile_filters,   # 添加 Makefile 的通用过滤器
        # include/uapi 目录下的文件在 #ifndef __KERNEL__ 时包含用户头文件
        # 我们的解决方案是忽略这些路径中的所有包含文件
        (CppPathIncFilter, {"path_exceptions": {'^/include/uapi/.*'}}),  # 添加带有路径例外的 C++ 路径包含文件过滤器
    ],
    'qemu': [
        *default_filters,           # 使用默认过滤器
        *common_kconfig_filters,    # 添加 Kconfig 文件的通用过滤器
    ],
    'u-boot': [
        *default_filters,           # 使用默认过滤器
        DtsiFilter,                 # 添加 DTSI 文件过滤器
        *common_kconfig_filters,    # 添加 Kconfig 文件的通用过滤器
        CppPathIncFilter,           # 添加 C++ 路径包含文件过滤器
        *common_makefile_filters,   # 添加 Makefile 的通用过滤器
    ],
    'uclibc-ng': [
        *default_filters,           # 使用默认过滤器
        ConfigInFilter,             # 添加 ConfigIn 文件过滤器
    ],
    'zephyr': [
        *default_filters,           # 使用默认过滤器
        DtsiFilter,                 # 添加 DTSI 文件过滤器
        *common_kconfig_filters,    # 添加 Kconfig 文件的通用过滤器
        CppPathIncFilter,           # 添加 C++ 路径包含文件过滤器
    ],
    'vite': [
        IdentFilter
    ],
}
