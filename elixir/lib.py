#!/usr/bin/env python3

#  This file is part of Elixir, a source code cross-referencer.
#
#  Copyright (C) 2017  Mikaël Bouillot
#  <mikael.bouillot@bootlin.com>
#
#  Elixir is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Elixir is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with Elixir.  If not, see <http://www.gnu.org/licenses/>.

import subprocess, os

# 获取当前文件所在目录的父目录的绝对路径
CURRENT_DIR = os.path.abspath(os.path.dirname(os.path.abspath(__file__)) + '/..')

# 调用脚本并返回输出
# 参数:
#   *args: 传递给脚本的参数
#   env: 环境变量字典
# 返回:
#   脚本的输出
def script(*args, env=None):
    # 将脚本路径与传递的参数组合
    args = (os.path.join(CURRENT_DIR, 'script.sh'),) + args
    # 检查是否支持 subprocess.run 方法
    # Python 3.5+ 支持 subprocess.run 方法
    # 在这之前不支持 subprocess.run 方法，使用 subprocess.check_output 替代
    if hasattr(subprocess, 'run'):
        # 使用 subprocess.run 执行脚本并捕获输出
        p = subprocess.run(args, stdout=subprocess.PIPE, env=env)
        # 获取标准输出
        p = p.stdout
    else:
        # 如果不支持 subprocess.run，使用 subprocess.check_output
        p = subprocess.check_output(args)
    # 返回脚本输出
    return p

# 调用脚本并将输出按行分割成列表
# 参数:
#   *args: 传递给脚本的参数
#   env: 环境变量字典
# 返回:
#   脚本输出的行列表
def scriptLines(*args, env=None):
    # 调用 script 函数获取脚本输出
    p = script(*args, env=env)
    # 将输出按行分割
    p = p.split(b'\n')
    # 删除最后一行（通常是空行）
    del p[-1]
    # 返回行列表
    return p

# 解码特殊字符
# 参数:
#   bstr: 需要解码的字节字符串
# 返回:
#   解码后的字节字符串
def unescape(bstr):
    # 定义替换表
    subs = (
        ('\1','\n'),
    )
    # 遍历替换表并进行替换
    for a,b in subs:
        a = a.encode()
        b = b.encode()
        bstr = bstr.replace(a, b)
    # 返回解码后的字节字符串
    return bstr

# 将字节对象解码为字符串
# 参数:
#   byte_object: 需要解码的字节对象
# 返回:
#   解码后的字符串
def decode(byte_object):
    # 尝试使用 utf-8 解码
    try:
        return byte_object.decode('utf-8')
    # 如果解码失败，使用 iso-8859-1 解码
    except UnicodeDecodeError:
        return byte_object.decode('iso-8859-1')

# 不希望被视为标识符的令牌列表
# 通常用于非常频繁的变量名和通过 #define 重新定义的内容
# TODO: 允许每个项目有自己的黑名单
blacklist = (
    b'NULL',
    b'__',
    b'adapter',
    b'addr',
    b'arg',
    b'attr',
    b'base',
    b'bp',
    b'buf',
    b'buffer',
    b'c',
    b'card',
    b'char',
    b'chip',
    b'cmd',
    b'codec',
    b'const',
    b'count',
    b'cpu',
    b'ctx',
    b'data',
    b'default',
    b'define',
    b'desc',
    b'dev',
    b'driver',
    b'else',
    b'end',
    b'endif',
    b'entry',
    b'err',
    b'error',
    b'event',
    b'extern',
    b'failed',
    b'flags',
    b'h',
    b'host',
    b'hw',
    b'i',
    b'id',
    b'idx',
    b'if',
    b'index',
    b'info',
    b'inline',
    b'int',
    b'irq',
    b'j',
    b'len',
    b'length',
    b'list',
    b'lock',
    b'long',
    b'mask',
    b'mode',
    b'msg',
    b'n',
    b'name',
    b'net',
    b'next',
    b'offset',
    b'ops',
    b'out',
    b'p',
    b'pdev',
    b'port',
    b'priv',
    b'ptr',
    b'q',
    b'r',
    b'rc',
    b'rdev',
    b'reg',
    b'regs',
    b'req',
    b'res',
    b'result',
    b'ret',
    b'return',
    b'retval',
    b'root',
    b's',
    b'sb',
    b'size',
    b'sizeof',
    b'sk',
    b'skb',
    b'spec',
    b'start',
    b'state',
    b'static',
    b'status',
    b'struct',
    b't',
    b'tmp',
    b'tp',
    b'type',
    b'val',
    b'value',
    b'vcpu',
    b'x'
)

blacklist_ts = (
    b'import',
    b'export',
    b'from',
    b'type',
    b'boolean',
    b'string',
    b'return',
    b'const',
    b'let',
    b'interface',
    b'class',
    b'extends',
    b'implements',
    b'public',
    b'private',
    b'protected',
    b'static',
    b'abstract',
    b'async',
    b'await',
    b'new',
    b'super',
    b'any',
    b'unknown',
    b'never',
    b'void',
    b'null',
    b'undefined',
    b'number',
    b'bigint',
    b'symbol',
    b'object',
    b'keyof',
    b'unique',
    b'infer',
    b'is',
    b'asserts',
    b'module',
    b'namespace',
    b'enum',
    b'as',
    b'of',
    b'assert',
    b'yield',
    b'break',
    b'case',
    b'catch',
    b'continue',
    b'default',
    b'delete',
    b'do',
    b'else',
    b'finally',
    b'for',
    b'function',
    b'if',
    b'in',
    b'instanceof',
    b'new',
    b'return',
    b'throw',
    b'try',
    b'var',
    b'while',
    b'with',
    b'package',
    b'protected',
    b'internal',
    b'declare',
    b'global',
    b'typeof',
)

# 判断一个字节字符串是否为有效的标识符
# 参数:
#   bstr: 需要判断的字节字符串
# 返回:
#   如果是有效标识符返回 True，否则返回 False
def isIdent(bstr, family):
    # 添加拦截以处理TS
    if family == 'TS':
        if bstr in blacklist_ts:
            return False
        return True

    # 检查长度是否小于 2 或在黑名单中或以 ~ 开头
    if (len(bstr) < 2 or
        bstr in blacklist or
        bstr.startswith(b'~')):
        return False
    else:
        return True

# 将不同类型的参数转换为字节字符串
# 参数:
#   arg: 需要转换的参数
# 返回:
#   转换后的字节字符串
def autoBytes(arg):
    # 如果参数是字符串，编码为字节字符串
    if type(arg) is str:
        arg = arg.encode()
    # 如果参数是整数，转换为字符串再编码为字节字符串
    elif type(arg) is int:
        arg = str(arg).encode()
    # 返回转换后的字节字符串
    return arg

# 获取数据目录
# 返回:
#   数据目录的路径
def getDataDir():
    try:
        # 从环境变量中获取数据目录
        dir=os.environ['LXR_DATA_DIR']
    except KeyError:
        # 如果环境变量未设置，打印错误信息并退出程序
        print(argv[0] + ': LXR_DATA_DIR needs to be set')
        exit(1)
    # 返回数据目录
    return dir

# 获取仓库目录
# 返回:
#   仓库目录的路径
def getRepoDir():
    try:
        # 从环境变量中获取仓库目录
        dir=os.environ['LXR_REPO_DIR']
    except KeyError:
        # 如果环境变量未设置，打印错误信息并退出程序
        print(argv[0] + ': LXR_REPO_DIR needs to be set')
        exit(1)
    # 返回仓库目录
    return dir

# 获取当前项目的名称
def currentProject():
    # 返回 getDataDir() 所在目录的基名，即项目名称
    return os.path.basename(os.path.dirname(getDataDir()))

# 列出 Elixir 支持的所有家族
families = ['A', 'B', 'C', 'D', 'K', 'M', 'TS']

# 检查给定的家族是否有效
def validFamily(family):
    # 如果家族在 families 列表中，则返回 True，否则返回 False
    return family in families

# 根据文件名确定文件所属的家族
def getFileFamily(filename):
    # 分离文件名和扩展名
    name, ext = os.path.splitext(filename)

    # 检查扩展名是否属于 C 语言或汇编文件
    if ext.lower() in ['.c', '.cc', '.cpp', '.c++', '.cxx', '.h', '.s'] :
        # 返回 'C' 家族
        return 'C' # C file family and ASM
    # 检查扩展名是否属于设备树文件
    elif ext.lower() in ['.dts', '.dtsi'] :
        # 返回 'D' 家族
        return 'D' # Devicetree files
    elif ext.lower() in ['.ts']:
        return 'TS'
    # 检查文件名前 7 个字符是否为 'kconfig' 且扩展名不是 '.rst'
    elif name.lower()[:7] in ['kconfig'] and not ext.lower() in ['.rst']:
        # 返回 'K' 家族
        return 'K' # Kconfig files
    # 检查文件名前 8 个字符是否为 'makefile' 且扩展名不是 '.rst'
    elif name.lower()[:8] in ['makefile'] and not ext.lower() in ['.rst']:
        # 返回 'M' 家族
        return 'M' # Makefiles
    else :
        # 不属于任何已知家族，返回 None
        return None

# 兼容性列表，键为文件家族，值为兼容的家族列表
# 1 字符值表示文件家族
# 2 字符值带 'M' 表示宏家族
compatibility_list = {
    'C': ['C', 'K'],  # C 文件家族兼容 C 和 K 家族
    'K': ['K'],       # K 家族只兼容 K 家族
    'D': ['D', 'CM'], # D 文件家族兼容 D 和 CM 宏家族
    'M': ['K'],       # M 家族兼容 K 家族
    'TS': ['TS'],       # M 家族兼容 K 家族
}

# 检查家族是否兼容
# 第一个参数可以是不同家族的列表
# 第二个参数是用于选择兼容性列表中正确数组的键
def compatibleFamily(file_family, requested_family):
    # 检查 file_family 中是否有任何一个家族在 compatibility_list[requested_family] 中
    return any(item in file_family for item in compatibility_list[requested_family])

# 检查宏是否与请求的家族兼容
# 第一个参数可以是不同家族的列表
# 第二个参数是用于选择兼容性列表中正确数组的键
def compatibleMacro(macro_family, requested_family):
    result = False  # 初始化结果为 False
    for item in macro_family:
        # 将当前家族名后缀加上 'M'
        item += 'M'
        # 检查当前宏家族是否在 compatibility_list[requested_family] 中
        result = result or item in compatibility_list[requested_family]
    # 返回最终结果
    return result
