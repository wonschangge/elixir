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

# 在整个代码中，“idx”是指与blob关联的顺序号。
# 这与该blob的Git哈希不同。

from sys import argv  # 导入sys模块中的argv，用于获取命令行参数
from threading import Thread, Lock, Event, Condition  # 导入线程相关模块

import elixir.lib as lib  # 导入elixir库中的lib模块
from elixir.lib import script, scriptLines  # 从lib模块导入script和scriptLines函数
import elixir.data as data  # 导入elixir库中的data模块
from elixir.data import PathList  # 从data模块导入PathList类
from find_compatible_dts import FindCompatibleDTS  # 从find_compatible_dts模块导入FindCompatibleDTS类

verbose = False  # 定义一个全局变量verbose，用于控制是否打印详细信息

dts_comp_support = int(script('dts-comp'))  # 调用script函数并转换为整数，设置dts_comp_support变量

compatibles_parser = FindCompatibleDTS()  # 创建FindCompatibleDTS对象

db = data.DB(lib.getDataDir(), readonly=False, shared=True, dtscomp=dts_comp_support)  # 创建数据库对象

# CPU线程数（+2用于版本索引）
cpu = 10  # 设置CPU线程数为10
threads_list = []  # 初始化线程列表

hash_file_lock = Lock()  # 创建锁，用于db.hash和db.file的同步
blobs_lock = Lock()  # 创建锁，用于db.blobs的同步
defs_lock = Lock()  # 创建锁，用于db.defs的同步
refs_lock = Lock()  # 创建锁，用于db.refs的同步
docs_lock = Lock()  # 创建锁，用于db.docs的同步
comps_lock = Lock()  # 创建锁，用于db.comps的同步
comps_docs_lock = Lock()  # 创建锁，用于db.comps_docs的同步
tag_ready = Condition()  # 创建条件变量，用于等待新标签

new_idxes = []  # 存储新的idxes及其相关的Event对象
bindings_idxes = []  # 存储DT绑定文档文件的idxes
idx_key_mod = 1000000  # 定义一个模数，用于生成唯一的键
defs_idxes = {}  # 存储标识符定义，键为(idx * idx_key_mod + line)

tags_done = False  # 标记所有标签是否已添加到new_idxes

# 进度变量 [标签, 完成的线程数]
tags_defs = [0, 0]  # 定义进度变量
tags_defs_lock = Lock()  # 创建锁，用于同步tags_defs
tags_refs = [0, 0]  # 定义进度变量
tags_refs_lock = Lock()  # 创建锁，用于同步tags_refs
tags_docs = [0, 0]  # 定义进度变量
tags_docs_lock = Lock()  # 创建锁，用于同步tags_docs
tags_comps = [0, 0]  # 定义进度变量
tags_comps_lock = Lock()  # 创建锁，用于同步tags_comps
tags_comps_docs = [0, 0]  # 定义进度变量
tags_comps_docs_lock = Lock()  # 创建锁，用于同步tags_comps_docs

class UpdateIds(Thread):
    def __init__(self, tag_buf):
        Thread.__init__(self, name="UpdateIdsElixir")  # 初始化线程
        self.tag_buf = tag_buf  # 存储标签缓冲区

    def run(self):
        global new_idxes, tags_done, tag_ready  # 声明全局变量
        self.index = 0  # 初始化索引

        for tag in self.tag_buf:
            new_idxes.append((self.update_blob_ids(tag), Event(), Event(), Event(), Event()))  # 更新blob ID并添加到new_idxes

            progress('ids: ' +  tag.decode() + ': ' + str(len(new_idxes[self.index][0])) +
                        ' new blobs', self.index+1)  # 打印进度信息

            new_idxes[self.index][1].set()  # 设置事件，表示标签已准备好

            self.index += 1  # 索引加1

            # 唤醒等待的线程
            with tag_ready:
                tag_ready.notify_all()  # 通知所有等待的线程

        tags_done = True  # 标记所有标签已处理完毕
        progress('ids: Thread finished', self.index)  # 打印线程完成信息

    def update_blob_ids(self, tag):
        global hash_file_lock, blobs_lock  # 声明全局变量

        if db.vars.exists('numBlobs'):
            idx = db.vars.get('numBlobs')  # 获取当前的blob数量
        else:
            idx = 0  # 如果不存在，初始化为0

        # 获取blob哈希和关联的文件名（不包括路径）
        blobs = scriptLines('list-blobs', '-f', tag)

        new_idxes = []  # 初始化新的idxes列表
        for blob in blobs:
            hash, filename = blob.split(b' ', maxsplit=1)  # 分割blob字符串
            with blobs_lock:
                blob_exist = db.blob.exists(hash)  # 检查blob是否存在
                if not blob_exist:
                    db.blob.put(hash, idx)  # 如果不存在，将blob添加到数据库

            if not blob_exist:
                with hash_file_lock:
                    db.hash.put(idx, hash)  # 将哈希添加到数据库
                    db.file.put(idx, filename)  # 将文件名添加到数据库

                new_idxes.append(idx)  # 添加新的idx到列表
                if verbose:
                    print(f"New blob #{idx} {hash}:{filename}")  # 打印详细信息
                idx += 1  # 索引加1
        db.vars.put('numBlobs', idx)  # 更新blob数量
        return new_idxes  # 返回新的idxes列表


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
                    tag_ready.wait()  # 等待条件变量
                continue

            tag = self.tag_buf[index]  # 获取当前标签

            new_idxes[index][1].wait()  # 确保标签已准备好

            self.update_versions(tag)  # 更新版本信息

            new_idxes[index][4].set()  # 设置事件，表示UpdateVersions已处理该标签

            progress('vers: ' + tag.decode() + ' done', index+1)  # 打印进度信息

            index += 1  # 索引加1

        progress('vers: Thread finished', index)  # 打印线程完成信息

    def update_versions(self, tag):
        global blobs_lock  # 声明全局变量

        # 获取blob哈希和关联的文件路径
        blobs = scriptLines('list-blobs', '-p', tag)
        buf = []  # 初始化缓冲区

        for blob in blobs:
            hash, path = blob.split(b' ', maxsplit=1)  # 分割blob字符串
            with blobs_lock:
                idx = db.blob.get(hash)  # 获取blob的idx
            buf.append((idx, path))  # 将idx和路径添加到缓冲区

        buf = sorted(buf)  # 对缓冲区进行排序
        obj = PathList()  # 创建PathList对象
        for idx, path in buf:
            obj.append(idx, path)  # 将idx和路径添加到PathList对象

            # 存储DT绑定文档文件，以便稍后解析
            if path[:33] == b'Documentation/devicetree/bindings':
                bindings_idxes.append(idx)  # 添加到bindings_idxes列表

            if verbose:
                print(f"Tag {tag}: adding #{idx} {path}")  # 打印详细信息
        db.vers.put(tag, obj, sync=True)  # 将版本信息存储到数据库


# 如果家族类型为 None 或 'M'，则跳过当前循环
if family in [None, 'M']: continue

# 解析当前文件的定义行
lines = scriptLines('parse-defs', hash, filename, family)

# 获取定义锁
with defs_lock:
    # 遍历解析后的每一行
    for l in lines:
        # 将行分割为标识符、类型和行号
        ident, type, line = l.split(b' ')
        # 解码类型
        type = type.decode()
        # 解码并转换行号为整数
        line = int(line.decode())

        # 更新定义索引
        defs_idxes[idx*idx_key_mod + line] = ident

        # 检查标识符是否已存在于定义数据库中
        if db.defs.exists(ident):
            obj = db.defs.get(ident)
        # 检查标识符是否为有效的标识符
        elif lib.isIdent(ident):
            obj = data.DefList()
        else:
            continue

        # 将当前索引、类型、行号和家族类型添加到对象中
        obj.append(idx, type, line, family)
        # 如果启用了详细输出，打印定义信息
        if verbose:
            print(f"def {type} {ident} in #{idx} @ {line}")
        # 将更新后的对象放回定义数据库中
        db.defs.put(ident, obj)


# 定义一个线程类用于更新引用
class UpdateRefs(Thread):
    def __init__(self, start, inc):
        # 初始化线程基类
        Thread.__init__(self, name="UpdateRefsElixir")
        # 设置起始索引和增量
        self.index = start
        self.inc = inc  # 增量相当于引用线程的数量

    def run(self):
        # 全局变量
        global new_idxes, tags_done, tags_refs, tags_refs_lock

        # 当标签处理未完成且当前索引小于新索引列表长度时继续循环
        while not (tags_done and self.index >= len(new_idxes)):
            # 如果当前索引大于等于新索引列表长度
            if self.index >= len(new_idxes):
                # 等待新的标签
                with tag_ready:
                    tag_ready.wait()
                continue

            # 确保标签已准备好
            new_idxes[self.index][1].wait()
            # 确保 UpdateDefs 已处理该标签
            new_idxes[self.index][2].wait()

            # 获取引用锁
            with tags_refs_lock:
                # 增加引用计数
                tags_refs[0] += 1

            # 更新引用
            self.update_references(new_idxes[self.index][0])

            # 增加索引
            self.index += self.inc

        # 获取引用锁
        with tags_refs_lock:
            # 增加完成的线程计数
            tags_refs[1] += 1
            # 打印进度信息
            progress('refs: Thread ' + str(tags_refs[1]) + '/' + str(self.inc) + ' finished', tags_refs[0])

    def update_references(self, idxes):
        # 全局变量
        global hash_file_lock, defs_lock, refs_lock, tags_refs

        # 遍历索引列表
        for idx in idxes:
            # 每处理 1000 个索引打印一次进度
            if idx % 1000 == 0: progress('refs: ' + str(idx), tags_refs[0])

            # 获取哈希文件锁
            with hash_file_lock:
                # 获取当前索引的哈希值
                hash = db.hash.get(idx)
                # 获取当前索引的文件名
                filename = db.file.get(idx)

            # 获取文件家族类型
            family = lib.getFileFamily(filename)
            # 如果家族类型为 None，则跳过当前循环
            if family == None: continue

            # 初始化前缀
            prefix = b''
            # Kconfig 值保存为 CONFIG_<value>
            if family == 'K':
                prefix = b'CONFIG_'

            # 解析文件中的 token
            tokens = scriptLines('tokenize-file', '-b', hash, family)
            # 初始化偶数标志和行号
            even = True
            line_num = 1
            # 初始化标识符字典
            idents = {}
            # 获取定义锁
            with defs_lock:
                # 遍历 token 列表
                for tok in tokens:
                    # 切换偶数标志
                    even = not even
                    if even:
                        # 添加前缀
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
                        # 增加行号
                        line_num += tok.count(b'\1')

            # 获取引用锁
            with refs_lock:
                # 遍历标识符字典
                for ident, lines in idents.items():
                    # 检查标识符是否已存在于引用数据库中
                    if db.refs.exists(ident):
                        obj = db.refs.get(ident)
                    else:
                        obj = data.RefList()

                    # 将当前索引、行号和家族类型添加到对象中
                    obj.append(idx, lines, family)
                    # 如果启用了详细输出，打印引用信息
                    if verbose:
                        print(f"ref: {ident} in #{idx} @ {lines}")
                    # 将更新后的对象放回引用数据库中
                    db.refs.put(ident, obj)


# 定义一个线程类用于更新文档
class UpdateDocs(Thread):
    def __init__(self, start, inc):
        # 初始化线程基类
        Thread.__init__(self, name="UpdateDocsElixir")
        # 设置起始索引和增量
        self.index = start
        self.inc = inc  # 增量相当于文档线程的数量

    def run(self):
        # 全局变量
        global new_idxes, tags_done, tags_docs, tags_docs_lock

        # 当标签处理未完成且当前索引小于新索引列表长度时继续循环
        while not (tags_done and self.index >= len(new_idxes)):
            # 如果当前索引大于等于新索引列表长度
            if self.index >= len(new_idxes):
                # 等待新的标签
                with tag_ready:
                    tag_ready.wait()
                continue

            # 确保标签已准备好
            new_idxes[self.index][1].wait()

            # 获取文档锁
            with tags_docs_lock:
                # 增加文档计数
                tags_docs[0] += 1

            # 更新文档注释
            self.update_doc_comments(new_idxes[self.index][0])

            # 增加索引
            self.index += self.inc

        # 获取文档锁
        with tags_docs_lock:
            # 增加完成的线程计数
            tags_docs[1] += 1
            # 打印进度信息
            progress('docs: Thread ' + str(tags_docs[1]) + '/' + str(self.inc) + ' finished', tags_docs[0])

    def update_doc_comments(self, idxes):
        # 全局变量
        global hash_file_lock, docs_lock, tags_docs

        # 遍历索引列表
        for idx in idxes:
            # 每处理 1000 个索引打印一次进度
            if idx % 1000 == 0: progress('docs: ' + str(idx), tags_docs[0])

            # 获取哈希文件锁
            with hash_file_lock:
                # 获取当前索引的哈希值
                hash = db.hash.get(idx)
                # 获取当前索引的文件名
                filename = db.file.get(idx)

            # 获取文件家族类型
            family = lib.getFileFamily(filename)
            # 如果家族类型为 None 或 'M'，则跳过当前循环
            if family in [None, 'M']: continue

            # 解析文档注释
            lines = scriptLines('parse-docs', hash, filename)
            # 获取文档锁
            with docs_lock:
                # 遍历解析后的每一行
                for l in lines:
                    # 将行分割为标识符和行号
                    ident, line = l.split(b' ')
                    # 解码并转换行号为整数
                    line = int(line.decode())

                    # 检查标识符是否已存在于文档数据库中
                    if db.docs.exists(ident):
                        obj = db.docs.get(ident)
                    else:
                        obj = data.RefList()

                    # 将当前索引、行号和家族类型添加到对象中
                    obj.append(idx, str(line), family)
                    # 如果启用了详细输出，打印文档信息
                    if verbose:
                        print(f"doc: {ident} in #{idx} @ {line}")
                    # 将更新后的对象放回文档数据库中
                    db.docs.put(ident, obj)


# 获取文件家族信息
family = lib.getFileFamily(filename)
# 如果家族信息为空或属于'K'或'M'，则跳过当前文件
if family in [None, 'K', 'M']: continue

# 使用兼容性解析器获取指定哈希值的文件内容，并根据家族信息进行处理
lines = compatibles_parser.run(scriptLines('get-blob', hash), family)
# 初始化兼容性字典
comps = {}
# 遍历每行内容
for l in lines:
    # 分割标识符和行号
    ident, line = l.split(' ')
    
    # 如果标识符已存在于字典中，则追加行号
    if ident in comps:
        comps[ident] += ',' + str(line)
    # 否则，将行号作为新值添加到字典中
    else:
        comps[ident] = str(line)

# 获取锁以确保线程安全
with comps_lock:
    # 遍历兼容性字典中的每个项
    for ident, lines in comps.items():
        # 如果数据库中已存在该标识符，则获取其对象
        if db.comps.exists(ident):
            obj = db.comps.get(ident)
        # 否则，创建一个新的引用列表对象
        else:
            obj = data.RefList()
        
        # 将当前索引、行号和家族信息添加到对象中
        obj.append(idx, lines, family)
        # 如果启用了详细输出，则打印兼容性信息
        if verbose:
            print(f"comps: {ident} in #{idx} @ {line}")
        # 将更新后的对象保存回数据库
        db.comps.put(ident, obj)


# 定义一个用于更新兼容性文档的线程类
class UpdateCompsDocs(Thread):
    def __init__(self, start, inc):
        # 调用父类构造函数
        Thread.__init__(self, name="UpdateCompsDocsElixir")
        # 设置起始索引和增量
        self.index = start
        self.inc = inc  # 等于兼容性文档线程的数量

    def run(self):
        # 全局变量声明
        global new_idxes, tags_done, tags_comps_docs, tags_comps_docs_lock
        
        # 当标签处理未完成且当前索引小于新索引列表长度时循环
        while not (tags_done and self.index >= len(new_idxes)):
            # 如果当前索引大于等于新索引列表长度
            if self.index >= len(new_idxes):
                # 等待新的标签
                with tag_ready:
                    tag_ready.wait()
                continue
            
            # 确保标签已准备好
            new_idxes[self.index][1].wait()
            # 确保UpdateComps已处理该标签
            new_idxes[self.index][3].wait()
            # 确保UpdateVersions已处理该标签
            new_idxes[self.index][4].wait()
            
            # 获取锁以确保线程安全
            with tags_comps_docs_lock:
                # 增加已处理的标签计数
                tags_comps_docs[0] += 1
            
            # 更新兼容性绑定信息
            self.update_compatibles_bindings(new_idxes[self.index][0])
            
            # 增加索引
            self.index += self.inc
        
        # 获取锁以确保线程安全
        with tags_comps_docs_lock:
            # 增加已完成的线程计数
            tags_comps_docs[1] += 1
            # 打印进度信息
            progress('comps_docs: Thread ' + str(tags_comps_docs[1]) + '/' + str(self.inc) + ' finished', tags_comps_docs[0])

    def update_compatibles_bindings(self, idxes):
        # 全局变量声明
        global hash_file_lock, comps_lock, comps_docs_lock, tags_comps_docs, bindings_idxes
        
        # 遍历每个索引
        for idx in idxes:
            # 每处理1000个索引打印一次进度信息
            if idx % 1000 == 0: 
                progress('comps_docs: ' + str(idx), tags_comps_docs[0])
            
            # 如果索引不在绑定索引列表中，则跳过
            if not idx in bindings_idxes: 
                continue
            
            # 获取锁以确保线程安全
            with hash_file_lock:
                # 从数据库中获取哈希值
                hash = db.hash.get(idx)
            
            # 设置家族信息
            family = 'B'
            # 使用兼容性解析器获取指定哈希值的文件内容，并根据家族信息进行处理
            lines = compatibles_parser.run(scriptLines('get-blob', hash), family)
            # 初始化兼容性文档字典
            comps_docs = {}
            # 获取锁以确保线程安全
            with comps_lock:
                # 遍历每行内容
                for l in lines:
                    # 分割标识符和行号
                    ident, line = l.split(' ')
                    
                    # 如果数据库中已存在该标识符
                    if db.comps.exists(ident):
                        # 如果标识符已存在于字典中，则追加行号
                        if ident in comps_docs:
                            comps_docs[ident] += ',' + str(line)
                        # 否则，将行号作为新值添加到字典中
                        else:
                            comps_docs[ident] = str(line)
            
            # 获取锁以确保线程安全
            with comps_docs_lock:
                # 遍历兼容性文档字典中的每个项
                for ident, lines in comps_docs.items():
                    # 如果数据库中已存在该标识符，则获取其对象
                    if db.comps_docs.exists(ident):
                        obj = db.comps_docs.get(ident)
                    # 否则，创建一个新的引用列表对象
                    else:
                        obj = data.RefList()
                    
                    # 将当前索引、行号和家族信息添加到对象中
                    obj.append(idx, lines, family)
                    # 如果启用了详细输出，则打印兼容性文档信息
                    if verbose:
                        print(f"comps_docs: {ident} in #{idx} @ {line}")
                    # 将更新后的对象保存回数据库
                    db.comps_docs.put(ident, obj)


# 定义一个打印进度信息的函数
def progress(msg, current):
    # 打印项目名称、消息和当前进度百分比
    print('{} - {} ({:.1%})'.format(project, msg, current/num_tags))


# 主程序入口
# 检查命令行参数中的线程数量
if len(argv) >= 2 and argv[1].isdigit() :
    cpu = int(argv[1])

    # 如果线程数量小于5，则设置为5
    if cpu < 5 :
        cpu = 5

# 根据CPU核心数分配线程数量
quo, rem = divmod(cpu, 5)
num_th_refs = quo
num_th_defs = quo
num_th_docs = quo

# 如果启用了DT绑定支持，则为每个线程分配相同的数量
if dts_comp_support:
    num_th_comps = quo
    num_th_comps_docs = quo
else :
    # 否则，将这些线程添加到剩余线程中
    num_th_comps = 0
    num_th_comps_docs = 0
    rem += 2*quo

# 再次分配剩余线程
quo, rem = divmod(rem, 2)
num_th_defs += quo
num_th_refs += quo + rem

# 获取所有新标签
tag_buf = []
for tag in scriptLines('list-tags'):
    # 如果数据库中不存在该标签，则将其添加到标签缓冲区
    if not db.vers.exists(tag):
        tag_buf.append(tag)

# 计算新标签数量
num_tags = len(tag_buf)
# 获取当前项目名称
project = lib.currentProject()

# 打印找到的新标签数量
print(project + ' - found ' + str(num_tags) + ' new tags')

# 如果没有新标签，则退出程序
if not num_tags:
    exit(0)

# 创建并添加更新ID和版本的线程
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

# 启动剩余线程
for i in range(1, len(threads_list)):
    threads_list[i].start()

# 确保所有线程完成
for i in range(len(threads_list)):
    threads_list[i].join()
