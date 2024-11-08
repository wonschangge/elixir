#!/usr/bin/python3

# 导入命令行参数模块
from sys import argv
# 导入自定义库中的函数
from lib import echo, script, scriptLines
# 导入自定义库
import lib
# 导入数据处理模块
import data
# 导入操作系统模块
import os
# 从数据处理模块中导入路径列表类
from data import PathList

# 尝试从环境变量中获取数据库目录
try:
    dbDir = os.environ['LXR_DATA_DIR']
# 如果环境变量未设置，输出错误信息并退出程序
except KeyError:
    print (argv[0] + ': LXR_DATA_DIR needs to be set')
    exit (1)

# 初始化数据库对象
db = data.DB (dbDir)

# 更新 Blob ID 的函数
def updateBlobIDs (tag):
    # 检查数据库中是否存在 numBlobs 变量，存在则获取其值，否则初始化为 0
    if db.vars.exists ('numBlobs'):
        idx = db.vars.get ('numBlobs')
    else:
        idx = 0
    
    # 获取指定标签下的所有 Blob 列表
    blobs = scriptLines ('list-blobs', '-f', tag)

    # 存储新添加的 Blob ID 列表
    newBlobs = []
    # 遍历所有 Blob
    for blob in blobs:
        # 分割 Blob 信息，获取哈希值和文件名
        hash, filename = blob.split (b' ')
        # 如果数据库中不存在该哈希值，则添加新的 Blob 信息
        if not db.blob.exists (hash):
            db.blob.put (hash, idx)
            db.hash.put (idx, hash)
            db.file.put (idx, filename)
            newBlobs.append (idx)
            idx += 1
    # 更新 numBlobs 变量
    db.vars.put ('numBlobs', idx)
    # 返回新添加的 Blob ID 列表
    return newBlobs

# 更新版本信息的函数
def updateVersions (tag):
    # 获取指定标签下的所有 Blob 列表
    blobs = scriptLines ('list-blobs', '-p', tag)
    # 存储 Blob 信息的缓冲区
    buf = []

    # 遍历所有 Blob
    for blob in blobs:
        # 分割 Blob 信息，获取哈希值和路径
        hash, path = blob.split (b' ')
        # 获取 Blob 对应的 ID
        idx = db.blob.get (hash)
        # 将 Blob 信息添加到缓冲区
        buf.append ((idx, path))

    # 对缓冲区进行排序
    buf = sorted (buf)
    # 创建路径列表对象
    obj = PathList()
    # 遍历排序后的缓冲区，将信息添加到路径列表对象中
    for idx, path in buf:
        obj.append (idx, path)
    # 更新数据库中的版本信息
    db.vers.put (tag, obj)

# 更新定义信息的函数
def updateDefinitions (blobs):
    # 遍历所有 Blob
    for blob in blobs:
        # 每处理 100 个 Blob 输出一次进度信息
        if (blob % 100 == 0): print ('D:', blob)
        # 获取 Blob 对应的哈希值和文件名
        hash = db.hash.get (blob)
        filename = db.file.get (blob)

        # 获取文件扩展名
        ext = filename[-2:]
        # 如果文件不是 .c 或 .h 文件，则跳过
        if not (ext == b'.c' or ext == b'.h'): continue

        # 解析文件中的定义信息
        lines = scriptLines ('parse-defs', hash, filename)
        # 遍历解析结果
        for l in lines:
            # 分割定义信息，获取标识符、类型和行号
            ident, type, line = l.split (b' ')
            type = type.decode()
            line = int (line.decode())

            # 如果数据库中已存在该标识符，则获取其定义列表，否则创建新的定义列表
            if db.defs.exists (ident):
                obj = db.defs.get (ident)
            else:
                obj = data.DefList()

            # 将定义信息添加到定义列表中
            obj.append (blob, type, line)
            # 更新数据库中的定义信息
            db.defs.put (ident, obj)

# 更新引用信息的函数
def updateReferences (blobs):
    # 遍历所有 Blob
    for blob in blobs:
        # 每处理 100 个 Blob 输出一次进度信息
        if (blob % 100 == 0): print ('R:', blob)
        # 获取 Blob 对应的哈希值和文件名
        hash = db.hash.get (blob)
        filename = db.file.get (blob)

        # 获取文件扩展名
        ext = filename[-2:]
        # 如果文件不是 .c 或 .h 文件，则跳过
        if not (ext == b'.c' or ext == b'.h'): continue

        # 对文件进行分词处理
        tokens = scriptLines ('tokenize-file', '-b', hash)
        even = True
        lineNum = 1
        idents = {}
        # 遍历分词结果
        for tok in tokens:
            even = not even
            if even:
                # 如果数据库中存在该标识符且是有效的标识符，则记录其行号
                if db.defs.exists (tok) and lib.isIdent (tok):
                    if tok in idents:
                        idents[tok] += ',' + str(lineNum)
                    else:
                        idents[tok] = str(lineNum)
            else:
                # 更新行号
                lineNum += tok.count (b'\1')

        # 遍历记录的标识符及其行号
        for ident, lines in idents.items():
            # 如果数据库中已存在该标识符，则获取其引用列表，否则创建新的引用列表
            if db.refs.exists (ident):
                obj = db.refs.get (ident)
            else:
                obj = data.RefList()

            # 将引用信息添加到引用列表中
            obj.append (blob, lines)
            # 更新数据库中的引用信息
            db.refs.put (ident, obj)

# 主程序
tagBuf = [] # 标签缓冲区
# 获取所有标签
for tag in scriptLines ('list-tags'):
    # 如果数据库中不存在该标签，则将其添加到标签缓冲区
    if not db.vers.exists (tag):
        tagBuf.append (tag)

# 输出找到的新标签数量
print ('Found ' + str(len(tagBuf)) + ' new tags')

# 遍历所有新标签
for tag in tagBuf:
    # 输出当前处理的标签
    print (tag.decode(), end=': ')
    # 更新 Blob ID 信息
    newBlobs = updateBlobIDs (tag)
    # 输出新添加的 Blob 数量
    print (str(len(newBlobs)) + ' new blobs')
    # 更新版本信息
    updateVersions (tag)
    # 更新定义信息
    updateDefinitions (newBlobs)
    # 更新引用信息
    updateReferences (newBlobs)
