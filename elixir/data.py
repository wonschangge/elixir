#!/usr/bin/env python3

#  This file is part of Elixir, a source code cross-referencer.
#
#  Copyright (C) 2017--2020 Mikaël Bouillot <mikael.bouillot@bootlin.com>
#  and contributors
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

import bsddb3  # 导入bsddb3模块，用于处理Berkeley DB数据库
import re  # 导入正则表达式模块
from elixir.lib import autoBytes  # 从elixir库中导入autoBytes函数，用于自动转换字节类型
import os  # 导入os模块，用于操作系统相关功能
import os.path  # 导入os.path模块，用于路径操作
import errno  # 导入errno模块，用于错误号定义

# 定义正则表达式，用于解析定义列表中的元素
deflist_regex = re.compile(b'(\d*)(\w)(\d*)(\w),?')
# 定义正则表达式，用于查找宏定义
deflist_macro_regex = re.compile('\dM\d+(\w)')

##################################################################################

# 定义类型映射表，将单个字符映射到完整的类型名称
defTypeR = {
    'c': 'config',
    'd': 'define',
    'e': 'enum',
    'E': 'enumerator',
    'f': 'function',
    'l': 'label',
    'M': 'macro',
    'm': 'member',
    'p': 'prototype',
    's': 'struct',
    't': 'typedef',
    'u': 'union',
    'v': 'variable',
    'x': 'externvar',
    'C': 'constant',
    'G': 'generator',
    'a': 'alias',
}

# 反向类型映射表，将完整的类型名称映射回单个字符
defTypeD = {v: k for k, v in defTypeR.items()}

##################################################################################

# 定义最大ID值
maxId = 999999999

class DefList:
    '''存储一个blob ID、类型（例如"function"）、行号和文件族之间的关联。
       还存储标识符存在的文件族，以便进行更快的测试。'''
    def __init__(self, data=b'#'):
        # 初始化DefList对象，解析data字符串
        self.data, self.families = data.split(b'#')

    def iter(self, dummy=False):
        # 获取所有元素并排序
        entries = deflist_regex.findall(self.data)
        entries.sort(key=lambda x:int(x[0]))
        # 遍历并生成元组 (id, type, line, family)
        for id, type, line, family in entries:
            id = int(id)
            type = defTypeR [type.decode()]
            line = int(line)
            family = family.decode()
            yield id, type, line, family
        if dummy:
            # 如果dummy为True，生成一个虚拟的元组
            yield maxId, None, None, None

    def append(self, id, type, line, family):
        # 检查类型是否有效
        if type not in defTypeD:
            return
        # 构建新的条目字符串
        p = str(id) + defTypeD[type] + str(line) + family
        if self.data != b'':
            p = ',' + p
        self.data += p.encode()
        # 添加文件族
        self.add_family(family)

    def pack(self):
        # 将数据打包成字符串
        return self.data + b'#' + self.families

    def add_family(self, family):
        # 将文件族添加到families列表中
        family = family.encode()
        if not family in self.families.split(b','):
            if self.families != b'':
                family = b',' + family
            self.families += family

    def get_families(self):
        # 获取所有文件族
        return self.families.decode().split(',')

    def get_macros(self):
        # 获取宏定义
        return deflist_macro_regex.findall(self.data.decode()) or ''

class PathList:
    '''存储一个blob ID和文件路径之间的关联。
       由update.py插入，按blob ID排序。'''
    def __init__(self, data=b''):
        self.data = data  # 初始化PathList对象

    def iter(self, dummy=False):
        # 遍历并生成元组 (id, path)
        for p in self.data.split(b'\n')[:-1]:
            id, path = p.split(b' ',maxsplit=1)
            id = int(id)
            path = path.decode()
            yield id, path
        if dummy:
            # 如果dummy为True，生成一个虚拟的元组
            yield maxId, None

    def append(self, id, path):
        # 添加新的条目
        p = str(id).encode() + b' ' + path + b'\n'
        self.data += p

    def pack(self):
        # 将数据打包成字符串
        return self.data

class RefList:
    '''存储从blob ID到行号列表及其对应文件族的映射。'''
    def __init__(self, data=b''):
        self.data = data  # 初始化RefList对象

    def iter(self, dummy=False):
        # 分割所有元素并排序
        entries = [x.split(b':') for x in self.data.split(b'\n')[:-1]]
        entries.sort(key=lambda x:int(x[0]))
        # 遍历并生成元组 (b, c, d)
        for b, c, d in entries:
            b = int(b.decode())
            c = c.decode()
            d = d.decode()
            yield b, c, d
        if dummy:
            # 如果dummy为True，生成一个虚拟的元组
            yield maxId, None, None

    def append(self, id, lines, family):
        # 添加新的条目
        p = str(id) + ':' + lines + ':' + family + '\n'
        self.data += p.encode()

    def pack(self):
        # 将数据打包成字符串
        return self.data

class BsdDB:
    def __init__(self, filename, readonly, contentType, shared=False):
        self.filename = filename  # 数据库文件名
        self.db = bsddb3.db.DB()  # 创建Berkeley DB对象
        flags = bsddb3.db.DB_THREAD if shared else 0  # 设置线程标志

        if readonly:
            flags |= bsddb3.db.DB_RDONLY  # 如果只读，设置只读标志
            self.db.open(filename, flags=flags)  # 打开数据库文件
        else:
            flags |= bsddb3.db.DB_CREATE  # 如果可写，设置创建标志
            self.db.open(filename, flags=flags, mode=0o644, dbtype=bsddb3.db.DB_BTREE)  # 打开或创建数据库文件
        self.ctype = contentType  # 内容类型

    def exists(self, key):
        key = autoBytes(key)  # 转换key为字节类型
        return self.db.exists(key)  # 检查键是否存在

    def get(self, key):
        key = autoBytes(key)  # 转换key为字节类型
        p = self.db.get(key)  # 获取键对应的值
        p = self.ctype(p)  # 解析值
        return p  # 返回解析后的值

    def get_keys(self):
        return self.db.keys()  # 获取所有键

    def put(self, key, val, sync=False):
        key = autoBytes(key)  # 转换key为字节类型
        val = autoBytes(val)  # 转换val为字节类型
        if type(val) is not bytes:
            val = val.pack()  # 如果val不是字节类型，调用pack方法
        self.db.put(key, val)  # 插入键值对
        if sync:
            self.db.sync()  # 同步数据库

    def close(self):
        self.db.close()  # 关闭数据库

class DB:
    def __init__(self, dir, readonly=True, dtscomp=False, shared=False):
        # 检查指定的目录是否存在
        if os.path.isdir(dir):
            self.dir = dir  # 如果存在，将目录路径赋值给实例变量
        else:
            # 如果目录不存在，抛出 FileNotFoundError 异常
            raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), dir)

        ro = readonly  # 设置只读模式标志

        # 初始化变量数据库，存储基本的信息
        self.vars = BsdDB(dir + '/variables.db', ro, lambda x: int(x.decode()), shared=shared)
        
        # 初始化 blob 数据库，将哈希映射到顺序整数序列号
        self.blob = BsdDB(dir + '/blobs.db', ro, lambda x: int(x.decode()), shared=shared)
        
        # 初始化哈希数据库，将序列号映射回哈希
        self.hash = BsdDB(dir + '/hashes.db', ro, lambda x: x, shared=shared)
        
        # 初始化文件名数据库，将序列号映射到文件名
        self.file = BsdDB(dir + '/filenames.db', ro, lambda x: x.decode(), shared=shared)
        
        # 初始化版本数据库
        self.vers = BsdDB(dir + '/versions.db', ro, PathList, shared=shared)
        
        # 初始化定义数据库
        self.defs = BsdDB(dir + '/definitions.db', ro, DefList, shared=shared)
        
        # 初始化引用数据库
        self.refs = BsdDB(dir + '/references.db', ro, RefList, shared=shared)
        
        # 初始化文档注释数据库
        self.docs = BsdDB(dir + '/doccomments.db', ro, RefList, shared=shared)
        
        self.dtscomp = dtscomp  # 设置兼容 DTS 标志
        if dtscomp:
            # 如果启用兼容 DTS，初始化兼容 DTS 数据库
            self.comps = BsdDB(dir + '/compatibledts.db', ro, RefList, shared=shared)
            
            # 初始化兼容 DTS 文档注释数据库
            self.comps_docs = BsdDB(dir + '/compatibledts_docs.db', ro, RefList, shared=shared)
            # 使用 RefList 以防一个标识符有多个文档注释

    def close(self):
        # 关闭变量数据库
        self.vars.close()
        
        # 关闭 blob 数据库
        self.blob.close()
        
        # 关闭哈希数据库
        self.hash.close()
        
        # 关闭文件名数据库
        self.file.close()
        
        # 关闭版本数据库
        self.vers.close()
        
        # 关闭定义数据库
        self.defs.close()
        
        # 关闭引用数据库
        self.refs.close()
        
        # 关闭文档注释数据库
        self.docs.close()
        
        if self.dtscomp:
            # 如果启用兼容 DTS，关闭兼容 DTS 数据库
            self.comps.close()
            
            # 关闭兼容 DTS 文档注释数据库
            self.comps_docs.close()

