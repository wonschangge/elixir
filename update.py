#!/usr/bin/env python3

#  This file is part of Elixir, a source code cross-referencer.
#
#  Copyright (C) 2017--2020 Mikaël Bouillot <mikael.bouillot@bootlin.com>
#                           Maxime Chretien <maxime.chretien@bootlin.com>
#                           and contributors
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

# 在整个代码中，"idx" 是与 blob 关联的顺序编号。
# 这与 blob 的 Git 哈希值不同。

from sys import argv  # 导入 sys 模块中的 argv
from threading import Thread, Lock, Event, Condition  # 导入线程相关模块

import elixir.lib as lib  # 导入 elixir 库
from elixir.lib import script, scriptLines  # 导入脚本处理函数
import elixir.data as data  # 导入数据处理模块
from elixir.data import PathList  # 导入路径列表类
from find_compatible_dts import FindCompatibleDTS  # 导入查找兼容 DTS 的类

verbose = False  # 控制是否输出详细信息

dts_comp_support = int(script('dts-comp'))  # 获取 DTS 兼容支持级别

compatibles_parser = FindCompatibleDTS()  # 创建查找兼容 DTS 的解析器

db = data.DB(lib.getDataDir(), readonly=False, shared=True, dtscomp=dts_comp_support)  # 初始化数据库

# CPU 线程数（+2 用于版本索引）
cpu = 10
threads_list = []  # 存储线程列表

hash_file_lock = Lock()  # 用于 db.hash 和 db.file 的锁
blobs_lock = Lock()  # 用于 db.blobs 的锁
defs_lock = Lock()  # 用于 db.defs 的锁
refs_lock = Lock()  # 用于 db.refs 的锁
docs_lock = Lock()  # 用于 db.docs 的锁
comps_lock = Lock()  # 用于 db.comps 的锁
comps_docs_lock = Lock()  # 用于 db.comps_docs 的锁
tag_ready = Condition()  # 等待新标签的条件变量

new_idxes = []  # 存储新的 idxes 及其相关事件
bindings_idxes = []  # 存储 DT 绑定文档文件的 idxes
idx_key_mod = 1000000  # idx 键的模数
defs_idxes = {}  # 存储标识符定义，键为 (idx * idx_key_mod + line)

tags_done = False  # 标记所有标签是否已添加到 new_idxes

# 进度变量 [标签, 完成的线程数]
tags_defs = [0, 0]
tags_defs_lock = Lock()
tags_refs = [0, 0]
tags_refs_lock = Lock()
tags_docs = [0, 0]
tags_docs_lock = Lock()
tags_comps = [0, 0]
tags_comps_lock = Lock()
tags_comps_docs = [0, 0]
tags_comps_docs_lock = Lock()

class UpdateIds(Thread):
    def __init__(self, tag_buf):
        Thread.__init__(self, name="UpdateIdsElixir")  # 初始化线程
        self.tag_buf = tag_buf  # 存储标签缓冲区

    def run(self):
        global new_idxes, tags_done, tag_ready  # 声明全局变量
        self.index = 0  # 初始化索引

        for tag in self.tag_buf:
            new_idxes.append((self.update_blob_ids(tag), Event(), Event(), Event(), Event()))  # 更新 blob ids 并添加到 new_idxes

            progress('ids: ' + tag.decode() + ': ' + str(len(new_idxes[self.index][0])) +
                     ' new blobs', self.index + 1)  # 输出进度信息

            new_idxes[self.index][1].set()  # 标记标签已准备好

            self.index += 1  # 增加索引

            # 唤醒等待的线程
            with tag_ready:
                tag_ready.notify_all()

        tags_done = True  # 标记所有标签已处理完毕
        progress('ids: Thread finished', self.index)  # 输出线程完成信息

    def update_blob_ids(self, tag):

        global hash_file_lock, blobs_lock  # 声明全局变量

        if db.vars.exists('numBlobs'):
            idx = db.vars.get('numBlobs')  # 获取当前 blob 数量
        else:
            idx = 0  # 如果不存在则初始化为 0

        # 获取 blob 哈希值和关联的文件名（不带路径）
        blobs = scriptLines('list-blobs', '-f', tag)

        new_idxes = []
        for blob in blobs:
            hash, filename = blob.split(b' ', maxsplit=1)  # 分割哈希值和文件名
            with blobs_lock:
                blob_exist = db.blob.exists(hash)  # 检查 blob 是否已存在
                if not blob_exist:
                    db.blob.put(hash, idx)  # 如果不存在则添加

            if not blob_exist:
                with hash_file_lock:
                    db.hash.put(idx, hash)  # 添加哈希值
                    db.file.put(idx, filename)  # 添加文件名

                new_idxes.append(idx)  # 添加新的 idx
                if verbose:
                    print(f"New blob #{idx} {hash}:{filename}")  # 输出详细信息
                idx += 1  # 增加 idx
        db.vars.put('numBlobs', idx)  # 更新 blob 数量
        return new_idxes  # 返回新的 idxes


class UpdateVersions(Thread):
    def __init__(self, tag_buf):
        Thread.__init__(self, name="UpdateVersionsElixir")  # 初始化线程
        self.tag_buf = tag_buf  # 存储标签缓冲区

    def run(self):
        global new_idxes, tag_ready  # 声明全局变量

        index = 0  # 初始化索引

        while index < len(self.tag_buf):
            if index >= len(new_idxes):
                # 等待新标签
                with tag_ready:
                    tag_ready.wait()
                continue

            tag = self.tag_buf[index]

            new_idxes[index][1].wait()  # 确保标签已准备好

            self.update_versions(tag)  # 更新版本

            new_idxes[index][4].set()  # 标记 UpdateVersions 已处理该标签

            progress('vers: ' + tag.decode() + ' done', index + 1)  # 输出进度信息

            index += 1  # 增加索引

        progress('vers: Thread finished', index)  # 输出线程完成信息

    def update_versions(self, tag):
        global blobs_lock  # 声明全局变量

        # 获取 blob 哈希值和关联的文件路径
        blobs = scriptLines('list-blobs', '-p', tag)
        buf = []

        for blob in blobs:
            hash, path = blob.split(b' ', maxsplit=1)  # 分割哈希值和路径
            with blobs_lock:
                idx = db.blob.get(hash)  # 获取 blob 的 idx
            buf.append((idx, path))  # 添加到缓冲区

        buf = sorted(buf)  # 对缓冲区进行排序
        obj = PathList()  # 创建路径列表对象
        for idx, path in buf:
            obj.append(idx, path)  # 添加路径

            # 存储 DT 绑定文档文件以供后续解析
            if path[:33] == b'Documentation/devicetree/bindings':
                bindings_idxes.append(idx)

            if verbose:
                print(f"Tag {tag}: adding #{idx} {path}")  # 输出详细信息
        db.vers.put(tag, obj, sync=True)  # 更新版本信息


class UpdateDefs(Thread):
    def __init__(self, start, inc):
        # 调用父类Thread的构造函数，设置线程名称为"UpdateDefsElixir"
        Thread.__init__(self, name="UpdateDefsElixir")
        # 初始化索引位置
        self.index = start
        # 初始化增量，相当于定义线程的数量
        self.inc = inc 

    def run(self):
        # 定义全局变量
        global new_idxes, tags_done, tag_ready, tags_defs, tags_defs_lock

        # 当标签处理未完成且当前索引小于新索引列表长度时循环执行
        while not (tags_done and self.index >= len(new_idxes)):
            # 如果当前索引超出新索引列表长度
            if self.index >= len(new_idxes):
                # 等待新的标签
                with tag_ready:
                    tag_ready.wait()
                # 继续下一次循环
                continue

            # 确保标签已准备好
            new_idxes[self.index][1].wait()

            # 获取锁并更新已处理的标签数量
            with tags_defs_lock:
                tags_defs[0] += 1

            # 更新定义
            self.update_definitions(new_idxes[self.index][0])

            # 告知UpdateDefs已处理该标签
            new_idxes[self.index][2].set()

            # 增加索引
            self.index += self.inc

        # 获取锁并更新已完成的线程数量
        with tags_defs_lock:
            tags_defs[1] += 1
            # 打印进度信息
            progress('defs: Thread ' + str(tags_defs[1]) + '/' + str(self.inc) + ' finished', tags_defs[0])


    def update_definitions(self, idxes):
        # 定义全局变量
        global hash_file_lock, defs_lock, tags_defs

        # 遍历索引列表
        for idx in idxes:
            # 每处理1000个索引打印一次进度信息
            if idx % 1000 == 0: 
                progress('defs: ' + str(idx), tags_defs[0])

            # 获取文件哈希和文件名
            with hash_file_lock:
                hash = db.hash.get(idx)
                filename = db.file.get(idx)

            # 获取文件家族
            family = lib.getFileFamily(filename)
            # 如果文件家族为空或为'M'，则跳过
            if family in [None, 'M']: 
                continue

            # 解析定义行
            lines = scriptLines('parse-defs', hash, filename, family)

            # 获取锁并处理定义行
            with defs_lock:
                for l in lines:
                    # 分割行数据
                    ident, type, line = l.split(b' ')
                    # 解码类型和行号
                    type = type.decode()
                    line = int(line.decode())

                    # 更新定义索引
                    defs_idxes[idx*idx_key_mod + line] = ident

                    # 检查标识符是否已存在于数据库中
                    if db.defs.exists(ident):
                        obj = db.defs.get(ident)
                    # 检查标识符是否为有效标识符
                    elif lib.isIdent(ident):
                        obj = data.DefList()
                    else:
                        continue

                    # 添加定义信息
                    obj.append(idx, type, line, family)
                    # 如果开启详细模式，打印定义信息
                    if verbose:
                        print(f"def {type} {ident} in #{idx} @ {line}")
                    # 将定义信息存入数据库
                    db.defs.put(ident, obj)

# 定义一个用于更新引用的线程类
class UpdateRefs(Thread):
    def __init__(self, start, inc):
        # 初始化父类
        Thread.__init__(self, name="UpdateRefsElixir")
        # 设置起始索引和增量
        self.index = start
        self.inc = inc  # 增量相当于引用线程的数量

    def run(self):
        # 全局变量
        global new_idxes, tags_done, tags_refs, tags_refs_lock

        # 循环处理新的索引，直到所有标签处理完成且索引超出范围
        while not (tags_done and self.index >= len(new_idxes)):
            # 如果索引超出范围，等待新标签
            if self.index >= len(new_idxes):
                with tag_ready:
                    tag_ready.wait()
                continue

            # 确保标签已准备好
            new_idxes[self.index][1].wait()
            # 确保 UpdateDefs 已处理该标签
            new_idxes[self.index][2].wait()

            # 更新引用计数
            with tags_refs_lock:
                tags_refs[0] += 1

            # 更新引用
            self.update_references(new_idxes[self.index][0])

            # 增加索引
            self.index += self.inc

        # 更新完成计数
        with tags_refs_lock:
            tags_refs[1] += 1
            progress('refs: Thread ' + str(tags_refs[1]) + '/' + str(self.inc) + ' finished', tags_refs[0])

    def update_references(self, idxes):
        # 全局变量
        global hash_file_lock, defs_lock, refs_lock, tags_refs

        # 处理每个索引
        for idx in idxes:
            # 每处理 1000 个索引，显示进度
            if idx % 1000 == 0: progress('refs: ' + str(idx), tags_refs[0])

            # 获取文件哈希和文件名
            with hash_file_lock:
                hash = db.hash.get(idx)
                filename = db.file.get(idx)

            # 获取文件家族
            family = lib.getFileFamily(filename)
            # 如果家族为 None，跳过当前文件
            if family == None: continue

            # 初始化前缀
            prefix = b''
            # Kconfig 值保存为 CONFIG_<value>
            if family == 'K':
                prefix = b'CONFIG_'

            # 分词文件
            tokens = scriptLines('tokenize-file', '-b', hash, family)
            even = True
            line_num = 1
            idents = {}
            # 获取定义锁以确保线程安全
            with defs_lock:
                # 遍历分词结果
                for tok in tokens:
                    even = not even
                    if even:
                        tok = prefix + tok

                        # 检查标识符是否存在且不在定义索引中
                        if (db.defs.exists(tok) and
                            not ( (idx*idx_key_mod + line_num) in defs_idxes and
                                defs_idxes[idx*idx_key_mod + line_num] == tok ) and
                            (family != 'M' or tok.startswith(b'CONFIG_'))):
                            # 只在 Makefile 中索引 CONFIG_???
                            if tok in idents:
                                idents[tok] += ',' + str(line_num)
                            else:
                                idents[tok] = str(line_num)

                    else:
                        # 更新行号
                        line_num += tok.count(b'\1')

            # 获取引用锁以确保线程安全
            with refs_lock:
                # 遍历标识符及其行号
                for ident, lines in idents.items():
                    # 检查标识符是否已存在于数据库中
                    if db.refs.exists(ident):
                        obj = db.refs.get(ident)
                    else:
                        obj = data.RefList()

                    # 将当前引用添加到对象中
                    obj.append(idx, lines, family)
                    # 如果开启了详细模式，打印引用信息
                    if verbose:
                        print(f"ref: {ident} in #{idx} @ {lines}")
                    # 将更新后的对象存回数据库
                    db.refs.put(ident, obj)


# 定义一个用于更新文档的线程类
class UpdateDocs(Thread):
    def __init__(self, start, inc):
        # 初始化父类
        Thread.__init__(self, name="UpdateDocsElixir")
        # 设置起始索引和增量
        self.index = start
        self.inc = inc  # 增量相当于文档线程的数量

    def run(self):
        # 全局变量
        global new_idxes, tags_done, tags_docs, tags_docs_lock

        # 循环处理新的索引，直到所有标签处理完成且索引超出范围
        while not (tags_done and self.index >= len(new_idxes)):
            # 如果索引超出范围，等待新标签
            if self.index >= len(new_idxes):
                with tag_ready:
                    tag_ready.wait()
                continue

            # 确保标签已准备好
            new_idxes[self.index][1].wait()

            # 更新文档计数
            with tags_docs_lock:
                tags_docs[0] += 1

            # 更新文档注释
            self.update_doc_comments(new_idxes[self.index][0])

            # 增加索引
            self.index += self.inc

        # 更新完成计数
        with tags_docs_lock:
            tags_docs[1] += 1
            progress('docs: Thread ' + str(tags_docs[1]) + '/' + str(self.inc) + ' finished', tags_docs[0])

    def update_doc_comments(self, idxes):
        # 全局变量
        global hash_file_lock, docs_lock, tags_docs

        # 处理每个索引
        for idx in idxes:
            # 每处理 1000 个索引，显示进度
            if idx % 1000 == 0: progress('docs: ' + str(idx), tags_docs[0])

            # 获取文件哈希和文件名
            with hash_file_lock:
                hash = db.hash.get(idx)
                filename = db.file.get(idx)

            # 获取文件家族
            family = lib.getFileFamily(filename)
            # 如果家族为 None 或 'M'，跳过当前文件
            if family in [None, 'M']: continue

            # 解析文档注释
            lines = scriptLines('parse-docs', hash, filename)
            # 获取文档锁以确保线程安全
            with docs_lock:
                # 遍历解析后的每一行
                for l in lines:
                    # 将行分割为标识符和行号
                    ident, line = l.split(b' ')
                    # 将行号解码并转换为整数
                    line = int(line.decode())

                    # 检查标识符是否已存在于数据库中
                    if db.docs.exists(ident):
                        obj = db.docs.get(ident)
                    else:
                        obj = data.RefList()

                    # 将当前文档注释添加到对象中
                    obj.append(idx, str(line), family)
                    # 如果开启了详细模式，打印文档注释信息
                    if verbose:
                        print(f"doc: {ident} in #{idx} @ {line}")
                    # 将更新后的对象存回数据库
                    db.docs.put(ident, obj)


class UpdateComps(Thread):
    def __init__(self, start, inc):
        # 调用父类Thread的构造函数，设置线程名称
        Thread.__init__(self, name="UpdateCompsElixir")
        # 初始化索引，从start开始
        self.index = start
        # 初始化增量，相当于组件线程的数量
        self.inc = inc 

    def run(self):
        # 声明全局变量
        global new_idxes, tags_done, tags_comps, tags_comps_lock

        # 当标签未处理完且索引未超出范围时循环
        while not (tags_done and self.index >= len(new_idxes)):
            # 如果索引超出范围
            if self.index >= len(new_idxes):
                # 等待新标签
                with tag_ready:
                    tag_ready.wait()
                # 继续下一次循环
                continue

            # 确保标签已准备好
            new_idxes[self.index][1].wait() 

            # 获取锁并更新已处理的标签数量
            with tags_comps_lock:
                tags_comps[0] += 1

            # 更新兼容性信息
            self.update_compatibles(new_idxes[self.index][0])

            # 标记UpdateComps已处理该标签
            new_idxes[self.index][3].set() 

            # 更新索引
            self.index += self.inc

        # 获取锁并更新已完成的线程数量
        with tags_comps_lock:
            tags_comps[1] += 1
            # 打印进度信息
            progress('comps: Thread ' + str(tags_comps[1]) + '/' + str(self.inc) + ' finished', tags_comps[0])

    def update_compatibles(self, idxes):
        # 声明全局变量
        global hash_file_lock, comps_lock, tags_comps

        # 遍历索引列表
        for idx in idxes:
            # 每1000个索引打印一次进度信息
            if idx % 1000 == 0: 
                progress('comps: ' + str(idx), tags_comps[0])

            # 获取文件哈希和文件名
            with hash_file_lock:
                hash = db.hash.get(idx)
                filename = db.file.get(idx)

            # 获取文件家族
            family = lib.getFileFamily(filename)
            # 如果家族为空或特定值则跳过
            if family in [None, 'K', 'M']: 
                continue

            # 解析兼容性信息
            lines = compatibles_parser.run(scriptLines('get-blob', hash), family)
            # 初始化兼容性字典
            comps = {}
            # 遍历解析结果
            for l in lines:
                # 分割标识符和行号
                ident, line = l.split(' ')

                # 合并相同标识符的行号
                if ident in comps:
                    comps[ident] += ',' + str(line)
                else:
                    comps[ident] = str(line)

            # 获取锁并更新数据库中的兼容性信息
            with comps_lock:
                for ident, lines in comps.items():
                    # 如果标识符已存在则获取现有对象，否则创建新对象
                    if db.comps.exists(ident):
                        obj = db.comps.get(ident)
                    else:
                        obj = data.RefList()

                    # 添加索引、行号和家族信息
                    obj.append(idx, lines, family)
                    # 如果开启详细模式则打印日志
                    if verbose:
                        print(f"comps: {ident} in #{idx} @ {line}")
                    # 更新数据库
                    db.comps.put(ident, obj)


# 定义更新兼容性文档的线程类
class UpdateCompsDocs(Thread):
    def __init__(self, start, inc):
        # 初始化线程
        Thread.__init__(self, name="UpdateCompsDocsElixir")
        self.index = start
        self.inc = inc  # 等于兼容性文档线程的数量

    def run(self):
        global new_idxes, tags_done, tags_comps_docs, tags_comps_docs_lock

        # 当没有新标签且索引超出范围时退出循环
        while not (tags_done and self.index >= len(new_idxes)):
            if self.index >= len(new_idxes):
                # 等待新标签
                with tag_ready:
                    tag_ready.wait()
                continue

            # 确保标签已准备好
            new_idxes[self.index][1].wait()
            new_idxes[self.index][3].wait()
            new_idxes[self.index][4].wait()

            # 更新处理的标签数量
            with tags_comps_docs_lock:
                tags_comps_docs[0] += 1

            # 更新兼容性绑定
            self.update_compatibles_bindings(new_idxes[self.index][0])

            # 增加索引
            self.index += self.inc

        # 更新完成的线程数量
        with tags_comps_docs_lock:
            tags_comps_docs[1] += 1
            progress('comps_docs: Thread ' + str(tags_comps_docs[1]) + '/' + str(self.inc) + ' finished', tags_comps_docs[0])

    def update_compatibles_bindings(self, idxes):
        global hash_file_lock, comps_lock, comps_docs_lock, tags_comps_docs, bindings_idxes

        # 遍历索引列表
        for idx in idxes:
            if idx % 1000 == 0: 
                progress('comps_docs: ' + str(idx), tags_comps_docs[0])

            # 跳过非绑定文档文件
            if not idx in bindings_idxes: 
                continue

            # 获取文件哈希值
            with hash_file_lock:
                hash = db.hash.get(idx)

            # 设置文件家族
            family = 'B'
            # 解析兼容性信息
            lines = compatibles_parser.run(scriptLines('get-blob', hash), family)
            # 初始化兼容性文档字典
            comps_docs = {}
            with comps_lock:
                for l in lines:
                    # 分割标识符和行号
                    ident, line = l.split(' ')

                    # 如果标识符已存在于字典中，则追加行号
                    if db.comps.exists(ident):
                        if ident in comps_docs:
                            comps_docs[ident] += ',' + str(line)
                        else:
                            comps_docs[ident] = str(line)

            # 获取锁以更新数据库
            with comps_docs_lock:
                for ident, lines in comps_docs.items():
                    # 检查标识符是否已存在于数据库中
                    if db.comps_docs.exists(ident):
                        obj = db.comps_docs.get(ident)
                    else:
                        obj = data.RefList()

                    # 更新对象并添加到数据库
                    obj.append(idx, lines, family)
                    if verbose:
                        print(f"comps_docs: {ident} in #{idx} @ {line}")
                    db.comps_docs.put(ident, obj)


# 定义进度打印函数
def progress(msg, current):
    print('{} - {} ({:.1%})'.format(project, msg, current/num_tags))


# 主程序

# 检查线程数参数
if len(argv) >= 2 and argv[1].isdigit() :
    cpu = int(argv[1])

    # 最少使用5个线程
    if cpu < 5 :
        cpu = 5

# 分配线程给各个函数
# There are more (or equal) refs threads than others
# There are more (or equal) defs threads than docs or comps threads
# Example : if cpu=6 : defs=1, refs=2, docs=1, comps=1, comps_docs=1
#           if cpu=7 : defs=2, refs=2, docs=1, comps=1, comps_docs=1
#           if cpu=8 : defs=2, refs=3, docs=1, comps=1, comps_docs=1
#           if cpu=11: defs=2, refs=3, docs=2, comps=2, comps_docs=2
quo, rem = divmod(cpu, 5)
num_th_refs = quo
num_th_defs = quo
num_th_docs = quo

# 如果启用了DT绑定支持，则为每个线程分配一个线程
if dts_comp_support:
    num_th_comps = quo
    num_th_comps_docs = quo
else :
    num_th_comps = 0
    num_th_comps_docs = 0
    rem += 2*quo

# 分配剩余的线程
quo, rem = divmod(rem, 2)
num_th_defs += quo
num_th_refs += quo + rem

# 获取新标签列表
tag_buf = []
for tag in scriptLines('list-tags'):
    if not db.vers.exists(tag):
        tag_buf.append(tag)

# 计算新标签数量
num_tags = len(tag_buf)
project = lib.currentProject()

# 打印项目和新标签数量
print(project + ' - found ' + str(num_tags) + ' new tags')

# 如果没有新标签，退出程序
if not num_tags:
    exit(0)

# 添加更新ID和版本的线程
threads_list.append(UpdateIds(tag_buf))
threads_list.append(UpdateVersions(tag_buf))

# 定义定义线程
for i in range(num_th_defs):
    threads_list.append(UpdateDefs(i, num_th_defs))
# 定义引用线程
for i in range(num_th_refs):
    threads_list.append(UpdateRefs(i, num_th_refs))
# 定义文档线程
for i in range(num_th_docs):
    threads_list.append(UpdateDocs(i, num_th_docs))
# 定义兼容性线程
for i in range(num_th_comps):
    threads_list.append(UpdateComps(i, num_th_comps))
# 定义兼容性文档线程
for i in range(num_th_comps_docs):
    threads_list.append(UpdateCompsDocs(i, num_th_comps_docs))


# 开始处理标签
threads_list[0].start()

# 等待第一个标签准备就绪
with tag_ready:
    tag_ready.wait()

# 启动剩余的线程
for i in range(1, len(threads_list)):
    threads_list[i].start()

# 确保所有线程完成
for i in range(len(threads_list)):
    threads_list[i].join()
