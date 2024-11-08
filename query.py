#!/usr/bin/python3

# 导入命令行参数模块
from sys import argv
# 导入自定义模块中的函数
from lib import echo, script, scriptLines
# 导入自定义模块
import lib
# 导入数据处理模块
import data
# 导入操作系统模块
import os

# 尝试从环境变量中获取数据库目录路径
try:
    dbDir = os.environ['LXR_DATA_DIR']
# 如果环境变量未设置，打印错误信息并退出程序
except KeyError:
    print(argv[0] + ': LXR_DATA_DIR 需要被设置')
    exit(1)

# 初始化数据库对象
db = data.DB(dbDir)

# 获取命令行参数中的第一个命令
cmd = argv[1]

# 根据命令执行不同的操作
if cmd == 'versions':
    # 执行列出标签的脚本
    p = script('list-tags')
    # 输出脚本结果
    echo(p)

elif cmd == 'dir':
    # 获取版本号和路径
    version = argv[2]
    path = argv[3]
    # 执行获取目录的脚本
    p = script('get-dir', version, path)
    # 输出脚本结果
    echo(p)

elif cmd == 'file':
    # 获取版本号和路径
    version = argv[2]
    path = argv[3]
    # 获取文件扩展名
    ext = path[-2:]

    # 检查文件是否为 C 或 H 文件
    if ext == '.c' or ext == '.h':
        # 执行文件分词脚本
        tokens = scriptLines('tokenize-file', version, path)
        # 用于交替颜色标记标识符
        even = True
        # 遍历分词结果
        for tok in tokens:
            even = not even
            # 如果是标识符且存在于数据库中，则用红色标记
            if even and db.defs.exists(tok) and lib.isIdent(tok):
                tok = b'\033[31m' + tok + b'\033[0m'
            else:
                tok = lib.unescape(tok)
            # 输出标记后的分词结果
            echo(tok)
    else:
        # 执行获取文件内容的脚本
        p = script('get-file', version, path)
        # 输出文件内容
        echo(p)

elif cmd == 'ident':
    # 获取版本号和标识符
    version = argv[2]
    ident = argv[3]

    # 检查标识符是否存在
    if not db.defs.exists(ident):
        print(argv[0] + ': 未知的标识符: ' + ident)
        exit()

    # 获取版本迭代器
    vers = db.vers.get(version).iter()
    # 获取定义迭代器
    defs = db.defs.get(ident).iter(dummy=True)
    # 获取引用迭代器
    refs = db.refs.get(ident).iter(dummy=True)

    # 获取第一个定义
    id2, type, dline = next(defs)
    # 获取第一个引用
    id3, rlines = next(refs)

    # 存储定义信息
    dBuf = []
    # 存储引用信息
    rBuf = []

    # 遍历版本信息
    for id1, path in vers:
        # 跳过不匹配的定义
        while id1 > id2:
            id2, type, dline = next(defs)
        # 跳过不匹配的引用
        while id1 > id3:
            id3, rlines = next(refs)
        # 如果版本匹配定义，存储定义信息
        if id1 == id2:
            dBuf.append((path, type, dline))
        # 如果版本匹配引用，存储引用信息
        if id1 == id3:
            rBuf.append((path, rlines))

    # 打印定义信息
    print('定义在', len(dBuf), '个文件中:')
    for path, type, dline in sorted(dBuf):
        print(path + ': ' + str(dline) + ' (' + type + ')')

    # 打印引用信息
    print('\n引用在', len(rBuf), '个文件中:')
    for path, rlines in sorted(rBuf):
        print(path + ': ' + rlines)

else:
    # 打印未知子命令的错误信息
    print(argv[0] + ': 未知的子命令: ' + cmd)