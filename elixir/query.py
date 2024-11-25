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

from elixir.lib import script, scriptLines, decode  # 从 elixir.lib 模块导入 script, scriptLines 和 decode 函数
from elixir import lib  # 从 elixir 包导入 lib 模块
from elixir import data  # 从 elixir 包导入 data 模块
import os  # 导入 os 模块，用于文件和目录操作
from collections import OrderedDict  # 从 collections 模块导入 OrderedDict 类
from urllib import parse  # 从 urllib 模块导入 parse 子模块

from io import BytesIO  # 从 io 模块导入 BytesIO 类

class SymbolInstance(object):
    def __init__(self, path, line, type=None):  # 初始化方法，设置路径、行号和类型
        self.path = path  # 设置路径
        self.line = line  # 设置行号
        self.type = type  # 设置类型

    def __repr__(self):  # 返回对象的字符串表示
        type_repr = ""  # 初始化类型表示为空字符串
        if self.type:  # 如果类型存在
            type_repr = f" , type: {self.type}"  # 添加类型到字符串表示中

        # 返回符号的详细信息
        return f"Symbol in path: {self.path}, line: {self.line}" + type_repr

    def __str__(self):  # 返回对象的字符串表示
        return self.__repr__()  # 调用 __repr__ 方法

# 返回一个 Query 类的实例，如果项目数据目录不存在则返回 None
# basedir: 项目数据目录的父目录的绝对路径，例如 "/srv/elixir-data/"
# project: 项目名称，父目录中的子目录，例如 "linux"
def get_query(basedir, project):
    datadir = basedir + '/' + project + '/data'  # 构建数据目录路径
    repodir = basedir + '/' + project + '/repo'  # 构建仓库目录路径

    if not os.path.exists(datadir) or not os.path.exists(repodir):  # 检查数据目录和仓库目录是否存在
        return None  # 如果任一目录不存在，返回 None

    return Query(datadir, repodir)  # 返回 Query 类的实例

class Query:
    def __init__(self, data_dir, repo_dir):  # 初始化方法，设置数据目录和仓库目录
        self.repo_dir = repo_dir  # 设置仓库目录
        self.data_dir = data_dir  # 设置数据目录
        self.dts_comp_support = int(self.script('dts-comp'))  # 获取 dts-comp 支持级别并转换为整数
        self.db = data.DB(data_dir, readonly=True, dtscomp=self.dts_comp_support)  # 创建数据库连接

    def script(self, *args):  # 执行脚本并返回结果
        return script(*args, env=self.getEnv())  # 调用 script 函数并传递环境变量

    def scriptLines(self, *args):  # 执行脚本并返回多行结果
        return scriptLines(*args, env=self.getEnv())  # 调用 scriptLines 函数并传递环境变量

    def getEnv(self):  # 获取环境变量
        return {
            **os.environ,  # 复制当前环境变量
            "LXR_REPO_DIR": self.repo_dir,  # 添加仓库目录环境变量
            "LXR_DATA_DIR": self.data_dir,  # 添加数据目录环境变量
        }

    def close(self):
        self.db.close()

    def query(self, cmd, *args):
        if cmd == 'versions':

            # Returns the list of indexed versions in the following format:
            # topmenu submenu tag
            # Example: v3 v3.1 v3.1-rc10
            versions = OrderedDict()

            for line in self.scriptLines('list-tags', '-h'):
                taginfo = decode(line).split(' ')
            num = len(taginfo)
            num = len(taginfo)
            # 初始化顶级菜单和子菜单
            num = len(taginfo)
            # 初始化顶级菜单和子菜单
            topmenu, submenu = 'FIXME', 'FIXME'

            # 根据标签信息的数量分配变量
            if num == 1:
                tag, = taginfo
            elif num == 2:
                submenu,tag = taginfo
            elif num ==3:
                topmenu,submenu,tag = taginfo

            if self.db.vers.exists(tag):
                # 如果顶级菜单不在版本字典中，初始化一个有序字典
                if self.db.vers.exists(tag):
                # 如果顶级菜单不在版本字典中，初始化一个有序字典
                    if topmenu not in versions:
                        versions[topmenu] = OrderedDict()
                    if submenu not in versions[topmenu]:
                        versions[topmenu][submenu] = []
                    versions[topmenu][submenu].append(tag)

            # 返回版本信息
            return versions

        elif cmd == 'latest':

            # Returns the tag considered as the latest one
            previous = None
            tag = ''
            index = 0

            # If we get the same tag twice, we are at the oldest one
            while not self.db.vers.exists(tag) and previous != tag:
                previous = tag
                # 获取最新的标签
                tag = decode(self.script('get-latest', str(index))).rstrip('\n')
                index += 1

            # 返回最新标签
            return tag

        elif cmd == 'type':

            # Returns the type (blob or tree) associated to
            # the given path. Example:
            # > ./query.py type v3.1-rc10 /Makefile
            # blob
            # > ./query.py type v3.1-rc10 /arch
            # tree

            version = args[0]
            path = args[1]
            # 调用脚本获取类型并去除首尾空白
            return decode(self.script('get-type', version, path)).strip()

        elif cmd == 'exist':

            # Returns True if the requested file exists, otherwise returns False

            version = args[0]
            path = args[1]

            # 分割路径为目录名和文件名
            dirname, filename = os.path.split(path)

            # 获取目录条目并去除最后一个空行
            entries = decode(self.script('get-dir', version, dirname)).split("\n")[:-1]
            # 遍历目录条目
            for entry in entries:
                # 获取文件名
                fname = entry.split(" ")[1]

                # 如果找到匹配的文件名，返回 True
                if fname == filename:
                    return True

            # 如果未找到文件，返回 False
            return False

        elif cmd == 'dir':

            # Returns the contents (trees or blobs) of the specified directory
            # Example: ./query.py dir v3.1-rc10 /arch

            version = args[0]
            path = args[1]
            entries_str =  decode(self.script('get-dir', version, path))
            return entries_str.split("\n")[:-1]

        elif cmd == 'file':

            # Returns the contents of the specified file
            # Tokens are marked for further processing
            # Example: ./query.py file v3.1-rc10 /Makefile

            version = args[0]
            path = args[1]

            # 获取文件名
            filename = os.path.basename(path)
            # 获取文件家族
            family = lib.getFileFamily(filename)

            if family != None:
                buffer = BytesIO()
                # 获取文件令牌
                tokens = self.scriptLines('tokenize-file', version, path, family)
                even = True

                # 设置前缀
                prefix = b''
                if family == 'K':
                    prefix = b'CONFIG_'

                # 遍历令牌
                for tok in tokens:
                    even = not even
                    tok2 = prefix + tok
                    # 检查令牌是否存在且兼容
                    if (even and self.db.defs.exists(tok2) and
                        (lib.compatibleFamily(self.db.defs.get(tok2).get_families(), family) or
                        lib.compatibleMacro(self.db.defs.get(tok2).get_macros(), family))):
                        tok = b'\033[31m' + tok2 + b'\033[0m'
                    else:
                        tok = lib.unescape(tok)
                    # 写入缓冲区
                    buffer.write(tok)
                # 返回解码后的缓冲区内容
                return decode(buffer.getvalue())
            else:
                # 如果文件没有家族信息，直接返回文件内容
                return decode(self.script('get-file', version, path))

        elif cmd == 'family':
            # Get the family of a given file

            filename = args[0]

            return lib.getFileFamily(filename)

        elif cmd == 'dts-comp':
            # Get state of dts_comp_support

            return self.dts_comp_support

        elif cmd == 'dts-comp-exists':
            # Check if a dts compatible string exists

            ident = args[0]
            if self.dts_comp_support:
                return self.db.comps.exists(ident)
            else:
                return False

        elif cmd == 'keys':
            # Return all keys of a given database
            # /!\ This can take a while /!\

            name = args[0]

            if name == 'vars':
                return self.db.vars.get_keys()
            elif name == 'blob':
                return self.db.blob.get_keys()
            elif name == 'hash':
                return self.db.hash.get_keys()
            elif name == 'file':
                return self.db.file.get_keys()
            elif name == 'vers':
                return self.db.vers.get_keys()
            elif name == 'defs':
                return self.db.defs.get_keys()
            elif name == 'refs':
                return self.db.refs.get_keys()
            elif name == 'docs':
                return self.db.docs.get_keys()
            elif name == 'comps' and self.dts_comp_support:
                return self.db.comps.get_keys()
            elif name == 'comps_docs' and self.dts_comp_support:
                return self.db.comps_docs.get_keys()
            else:
                return []

        elif cmd == 'ident':
            # Returns identifier search results
            version = args[0]
            ident = args[1]
            family = args[2]

            # DT bindings compatible strings are handled differently
            if family == 'B':
                return self.get_idents_comps(version, ident)
            else:
                return self.get_idents_defs(version, ident, family)

        else:
            # 返回未知子命令的错误信息
            return 'Unknown subcommand: ' + cmd + '\n'

    def get_file_raw(self, version, path):
        """
        获取并解码特定版本文件的原始内容。

        参数:
            version (str): 文件的版本。
            path (str): 文件路径。

        返回:
            str: 解码后的文件内容。
        """
        return decode(self.script('get-file', version, path))  # 调用脚本获取并解码文件内容

    def get_idents_comps(self, version, ident):
        """
        获取与特定标识符相关的组件信息。

        参数:
            version (str): 版本号。
            ident (str): 标识符。

        返回:
            tuple: 包含C文件、DT文件和文档文件中的符号实例列表。
        """
        # DT 绑定兼容字符串处理方式不同
        # 它们在C文件中定义
        # 在DT文件中使用
        # 在文档文件中记录
        symbol_c = []  # 存储C文件中的符号实例
        symbol_dts = []  # 存储DT文件中的符号实例
        symbol_docs = []  # 存储文档文件中的符号实例

        # DT 兼容字符串在数据库中被引用
        ident = parse.quote(ident)  # 对标识符进行URL编码

        if not self.dts_comp_support or not self.db.comps.exists(ident):
            return symbol_c, symbol_dts, symbol_docs  # 如果不支持DT兼容或标识符不存在于组件数据库中，返回空列表

        files_this_version = self.db.vers.get(version).iter()  # 获取当前版本的所有文件迭代器
        comps = self.db.comps.get(ident).iter(dummy=True)  # 获取标识符对应的组件迭代器

        if self.db.comps_docs.exists(ident):
            comps_docs = self.db.comps_docs.get(ident).iter(dummy=True)  # 获取标识符对应的文档组件迭代器
        else:
            comps_docs = data.RefList().iter(dummy=True)  # 如果没有文档组件，创建一个空的迭代器

        comps_idx, comps_lines, comps_family = next(comps)  # 获取第一个组件的信息
        comps_docs_idx, comps_docs_lines, comps_docs_family = next(comps_docs)  # 获取第一个文档组件的信息
        compsCBuf = []  # 存储C/CPP/ASM文件中的组件信息
        compsDBuf = []  # 存储DT文件中的组件信息
        compsBBuf = []  # 存储DT绑定文档文件中的组件信息

        for file_idx, file_path in files_this_version:
            while comps_idx < file_idx:
                comps_idx, comps_lines, comps_family = next(comps)  # 移动到下一个组件

            while comps_docs_idx < file_idx:
                comps_docs_idx, comps_docs_lines, comps_docs_family = next(comps_docs)  # 移动到下一个文档组件

            if comps_idx == file_idx:
                if comps_family == 'C':
                    compsCBuf.append((file_path, comps_lines))  # 将C文件中的组件信息添加到缓冲区
                elif comps_family == 'D':
                    compsDBuf.append((file_path, comps_lines))  # 将DT文件中的组件信息添加到缓冲区

            if comps_docs_idx == file_idx:
                compsBBuf.append((file_path, comps_docs_lines))  # 将文档文件中的组件信息添加到缓冲区

        for path, cline in sorted(compsCBuf):
            symbol_c.append(SymbolInstance(path, cline, 'compatible'))  # 创建C文件中的符号实例并添加到列表

        for path, dlines in sorted(compsDBuf):
            symbol_dts.append(SymbolInstance(path, dlines))  # 创建DT文件中的符号实例并添加到列表

        for path, blines in sorted(compsBBuf):
            symbol_docs.append(SymbolInstance(path, blines))  # 创建文档文件中的符号实例并添加到列表

        return symbol_c, symbol_dts, symbol_docs  # 返回符号实例列表

    def get_idents_defs(self, version, ident, family):
        """
        获取与特定标识符相关的定义、引用和文档注释。

        参数:
            version (str): 版本号。
            ident (str): 标识符。
            family (str): 符号家族（例如 'C' 表示C语言）。

        返回:
            tuple: 包含定义、引用和文档注释的符号实例列表。
        """
        symbol_definitions = []  # 存储定义的符号实例
        symbol_references = []  # 存储引用的符号实例
        symbol_doccomments = []  # 存储文档注释的符号实例

        if not self.db.defs.exists(ident):
            return symbol_definitions, symbol_references, symbol_doccomments  # 如果标识符不存在于定义数据库中，返回空列表

        if not self.db.vers.exists(version):
            return symbol_definitions, symbol_references, symbol_doccomments  # 如果版本不存在，返回空列表

        files_this_version = self.db.vers.get(version).iter()  # 获取当前版本的所有文件迭代器
        this_ident = self.db.defs.get(ident)  # 获取标识符的定义信息
        defs_this_ident = this_ident.iter(dummy=True)  # 获取标识符的定义迭代器
        macros_this_ident = this_ident.get_macros()  # 获取标识符的宏信息

        if self.db.refs.exists(ident):
            refs = self.db.refs.get(ident).iter(dummy=True)  # 获取标识符的引用迭代器
        else:
            refs = data.RefList().iter(dummy=True)  # 如果没有引用，创建一个空的迭代器

        if self.db.docs.exists(ident):
            docs = self.db.docs.get(ident).iter(dummy=True)  # 获取标识符的文档注释迭代器
        else:
            docs = data.RefList().iter(dummy=True)  # 如果没有文档注释，创建一个空的迭代器

        # 版本、定义、引用和文档注释都按索引顺序填充
        # 因此可以按顺序遍历每个文件的定义、引用和文档注释
        def_idx, def_type, def_line, def_family = next(defs_this_ident)  # 获取第一个定义的信息
        ref_idx, ref_lines, ref_family = next(refs)  # 获取第一个引用的信息
        doc_idx, doc_line, doc_family = next(docs)  # 获取第一个文档注释的信息

        dBuf = []  # 存储定义信息
        rBuf = []  # 存储引用信息
        docBuf = []  # 存储文档注释信息

        for file_idx, file_path in files_this_version:
            # 将定义、引用和文档注释移动到当前文件
            while def_idx < file_idx:
                def_idx, def_type, def_line, def_family = next(defs_this_ident)  # 移动到下一个定义

            while ref_idx < file_idx:
                ref_idx, ref_lines, ref_family = next(refs)  # 移动到下一个引用

            while doc_idx < file_idx:
                doc_idx, doc_line, doc_family = next(docs)  # 移动到下一个文档注释

            # 将当前标识符的信息复制到dBuf、rBuf和docBuf
            while def_idx == file_idx:
                if (def_family == family or family == 'A'
                    or lib.compatibleMacro(macros_this_ident, family)):
                    dBuf.append((file_path, def_type, def_line))  # 将符合条件的定义信息添加到缓冲区
                def_idx, def_type, def_line, def_family = next(defs_this_ident)  # 移动到下一个定义

            if ref_idx == file_idx:
                if lib.compatibleFamily(family, ref_family) or family == 'A':
                    rBuf.append((file_path, ref_lines))  # 将符合条件的引用信息添加到缓冲区

            if doc_idx == file_idx:  # TODO 是否应该使用 `while`？
                docBuf.append((file_path, doc_line))  # 将文档注释信息添加到缓冲区

        # 按路径名称排序dBuf，然后再按类型排序
        dBuf.sort()

        for path, type, dline in sorted(dBuf, key=lambda d: d[1], reverse=True):
            symbol_definitions.append(SymbolInstance(path, dline, type))  # 创建定义的符号实例并添加到列表

        for path, rlines in sorted(rBuf):
            symbol_references.append(SymbolInstance(path, rlines))  # 创建引用的符号实例并添加到列表

        for path, docline in sorted(docBuf):
            symbol_doccomments.append(SymbolInstance(path, docline))  # 创建文档注释的符号实例并添加到列表

        return symbol_definitions, symbol_references, symbol_doccomments  # 返回符号实例列表


def cmd_ident(q, version, ident, family, **kwargs):
    # 调用查询方法，获取标识符的定义、引用和文档注释
    symbol_definitions, symbol_references, symbol_doccomments = q.query("ident", version, ident, family)
    
    # 打印标识符的定义
    print("Symbol Definitions:")
    for symbol_definition in symbol_definitions:
        print(symbol_definition)

    # 打印标识符的引用
    print("\nSymbol References:")
    for symbol_reference in symbol_references:
        print(symbol_reference)

    # 打印标识符的文档注释
    print("\nDocumented in:")
    for symbol_doccomment in symbol_doccomments:
        print(symbol_doccomment)

def cmd_file(q, version, path, **kwargs):
    # 调用查询方法，获取文件的内容
    code = q.query("file", version, path)
    
    # 打印文件的内容
    print(code)

if __name__ == "__main__":
    # 导入 argparse 模块
    import argparse

    # 创建 Query 对象，初始化数据目录和仓库目录
    query = Query(lib.getDataDir(), lib.getRepoDir())

    # 创建 ArgumentParser 对象，用于解析命令行参数
    parser = argparse.ArgumentParser()
    
    # 添加版本参数，指定项目版本，默认为 "latest"
    parser.add_argument("version", help="项目的版本", type=str, default="latest")
    
    # 创建子命令解析器
    subparsers = parser.add_subparsers()

    # 添加 ident 子命令解析器，用于获取标识符的定义和引用
    ident_subparser = subparsers.add_parser('ident', help="获取标识符的定义和引用")
    
    # 添加 ident 参数，指定标识符名称
    ident_subparser.add_argument('ident', type=str, help="标识符名称")
    
    # 添加 family 参数，指定请求的文件家族
    ident_subparser.add_argument('family', type=str, help="请求的文件家族")
    
    # 设置 ident 子命令的处理函数
    ident_subparser.set_defaults(func=cmd_ident, q=query)

    # 添加 file 子命令解析器，用于获取源文件内容
    file_subparser = subparsers.add_parser('file', help="获取源文件内容")
    
    # 添加 path 参数，指定源文件路径
    file_subparser.add_argument('path', type=str, help="源文件路径")
    
    # 设置 file 子命令的处理函数
    file_subparser.set_defaults(func=cmd_file, q=query)

    # 解析命令行参数
    args = parser.parse_args()
    
    # 调用相应的处理函数
    args.func(**vars(args))
