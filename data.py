#!/usr/bin/python3

# 导入必要的模块
import bsddb3
from io import BytesIO
import re
from lib import autoBytes
import os.path

##################################################################################

# 定义类型映射字典，用于将单字符类型转换为全称
defTypeR = {
    'd': 'define',
    'e': 'enum',
    'E': 'enumerator',
    'f': 'function',
    'l': 'label',
    'M': 'macro',
    'm': 'member',
    's': 'struct',
    't': 'typedef',
    'u': 'union',
    'v': 'variable' }

# 反向映射字典，用于将全称类型转换为单字符
defTypeD = {v: k for k, v in defTypeR.items()}

##################################################################################

# 定义最大ID值
maxId = 999999999

# 定义DefList类，用于处理定义列表
class DefList:
    def __init__(self, data=b''):
        # 初始化数据
        self.data = data

    def iter(self, dummy=False):
        # 遍历数据并解析
        for p in self.data.split(b','):
            p = re.search(b'(\d*)(\w)(\d*)', p)
            id, type, line = p.groups()
            id = int(id)
            type = defTypeR[type.decode()]
            line = int(line)
            yield (id, type, line)
        if dummy:
            yield (maxId, None, None)

    def append(self, id, type, line):
        # 检查类型是否有效
        if type not in defTypeD:
            return
        # 构建新的定义字符串
        p = str(id) + defTypeD[type] + str(line)
        if self.data != b'':
            p = ',' + p
        self.data += p.encode()

    def pack(self):
        # 返回打包后的数据
        return self.data

# 定义PathList类，用于处理路径列表
class PathList:
    def __init__(self, data=b''):
        # 初始化数据
        self.data = data

    def iter(self, dummy=False):
        # 遍历数据并解析
        for p in self.data.split(b'\n'):
            if p == b'': continue
            id, path = p.split(b' ')
            id = int(id)
            path = path.decode()
            yield (id, path)
        if dummy:
            yield (maxId, None)

    def append(self, id, path):
        # 构建新的路径字符串
        p = str(id).encode() + b' ' + path
        self.data = self.data + p + b'\n'

    def pack(self):
        # 返回打包后的数据
        return self.data

# 导入BytesIO模块
from io import BytesIO

# 定义RefList类，用于处理引用列表
class RefList:
    def __init__(self, data=b''):
        # 初始化数据
        self.data = data

    def iter(self, dummy=False):
        # 获取数据大小
        size = len(self.data)
        s = BytesIO(self.data)
        while s.tell() < size:
            line = s.readline()
            line = line[:-1]
            b, c = line.split(b':')
            b = int(b.decode())
            c = c.decode()
            yield (b, c)
        s.close()
        if dummy:
            yield (maxId, None)

    def append(self, id, lines):
        # 构建新的引用字符串
        p = str(id) + ':' + lines + '\n'
        self.data += p.encode()

    def pack(self):
        # 返回打包后的数据
        return self.data

# 定义BsdDB类，用于封装Berkley DB操作
class BsdDB:
    def __init__(self, filename, contentType):
        # 初始化文件名和数据库对象
        self.filename = filename
        self.db = bsddb3.db.DB()
        self.db.open(filename,
            flags=bsddb3.db.DB_CREATE,  # 创建数据库文件
            dbtype=bsddb3.db.DB_BTREE)  # 使用B树类型
        self.ctype = contentType

    def exists(self, key):
        # 检查键是否存在
        key = autoBytes(key)
        return self.db.exists(key)

    def get(self, key):
        # 获取键对应的值
        key = autoBytes(key)
        p = self.db.get(key)
        p = self.ctype(p)
        return p

    def put(self, key, val):
        # 插入或更新键值对
        key = autoBytes(key)
        val = autoBytes(val)
        if type(val) is not bytes:
            val = val.pack()
        self.db.put(key, val)

# 定义DB类，用于管理多个Berkley DB实例
class DB:
    def __init__(self, dir):
        # 检查目录是否存在
        if os.path.isdir(dir):
            self.dir = dir
        else:
            raise FileNotFoundError

        # 初始化各个数据库实例
        # 初始化变量数据库，键值对中的值为整数
        self.vars = BsdDB(dir + '/variables.db', lambda x: int(x.decode()))
        # 初始化blob数据库，键值对中的值为整数
        self.blob = BsdDB(dir + '/blobs.db', lambda x: int(x.decode()))
        # 初始化哈希数据库，键值对中的值为原始字节
        self.hash = BsdDB(dir + '/hashes.db', lambda x: x)
        # 初始化文件名数据库，键值对中的值为解码后的字符串
        self.file = BsdDB(dir + '/filenames.db', lambda x: x.decode())
        # 初始化版本数据库，键值对中的值为PathList对象
        self.vers = BsdDB(dir + '/versions.db', PathList)
        # 初始化定义数据库，键值对中的值为DefList对象
        self.defs = BsdDB(dir + '/definitions.db', DefList)
        # 初始化引用数据库，键值对中的值为RefList对象
        self.refs = BsdDB(dir + '/references.db', RefList)