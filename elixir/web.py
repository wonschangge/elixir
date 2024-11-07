#!/usr/bin/env python3

#  This file is part of Elixir, a source code cross-referencer.
#
#  Copyright (C) 2017--2020 Mikaël Bouillot <mikael.bouillot@bootlin.com>
#  and contributors.
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

# 导入日志模块
import logging
# 导入操作系统模块
import os
# 导入系统模块
import sys
# 导入线程模块
import threading
# 导入时间模块
import time
# 导入日期时间模块
import datetime
# 从collections模块导入OrderedDict和namedtuple
from collections import OrderedDict, namedtuple
# 从re模块导入search和sub
from re import search, sub
# 从urllib模块导入parse
from urllib import parse
# 导入Falcon框架
import falcon
# 导入Jinja2模板引擎
import jinja2

# 从elixir库导入validFamily函数
from elixir.lib import validFamily
# 从elixir.query模块导入Query和SymbolInstance类
from elixir.query import Query, SymbolInstance
# 从elixir.filters模块导入get_filters函数
from elixir.filters import get_filters
# 从elixir.filters.utils模块导入FilterContext类
from elixir.filters.utils import FilterContext
# 从elixir.autocomplete模块导入AutocompleteResource类
from elixir.autocomplete import AutocompleteResource
# 从elixir.api模块导入ApiIdentGetterResource类
from elixir.api import ApiIdentGetterResource
# 从elixir.query模块导入get_query函数
from elixir.query import get_query
# 从elixir.web_utils模块导入ProjectConverter、IdentConverter、validate_version、validate_project和validate_ident函数
from elixir.web_utils import ProjectConverter, IdentConverter, validate_version, validate_project, validate_ident

# 定义版本缓存的持续时间（2分钟）
VERSION_CACHE_DURATION_SECONDS = 2 * 60  # 2 minutes
# 定义GitHub问题链接
ADD_ISSUE_LINK = "https://github.com/bootlin/elixir/issues/new"

# 定义默认项目
DEFAULT_PROJECT = 'linux'

# 定义ElixirProjectError类，继承自falcon.errors.HTTPError
class ElixirProjectError(falcon.errors.HTTPError):
    # 初始化方法，设置错误标题、描述、项目、版本、查询和额外模板参数
    def __init__(self, title, description, project=None, version=None, query=None,
                 status=falcon.HTTP_BAD_REQUEST, extra_template_args={}, **kwargs):
        self.project = project
        self.version = version
        self.query = query
        self.extra_template_args = extra_template_args
        # 调用父类的初始化方法
        super().__init__(status, title=title, description=description, **kwargs)

# 生成错误详情摘要，用于Bug报告
def generate_error_details(req, resp, title, details):
    # 返回包含请求日期、路径、查询字符串、方法、状态码、错误标题和详细信息的字符串
    return f"Request date: {datetime.datetime.now()}\n" + \
           f"Path: {req.path}\n" + \
           f"Query string: {req.query_string}\n" + \
           f"Method: {req.method}\n" + \
           f"Status code: {resp.status}\n" + \
           f"Error title: {title}\n" + \
           f"Error details: {details}\n"

# 获取GitHub问题链接
def get_github_issue_link(details: str):
    # 生成问题描述体，包括如何到达错误的信息和验证的详细信息
    body = ("TODO: add information on how you reached the error here and " +
            "validate the details below.\n\n" +
            "---\n\n" +
            details)
    # 返回带有问题描述体的GitHub问题链接
    return ADD_ISSUE_LINK + "?body=" + parse.quote(body)

# 从ElixirProjectError生成错误页面
def get_project_error_page(req, resp, exception: ElixirProjectError):
    # 生成错误详情摘要
    report_error_details = generate_error_details(req, resp, exception.title, exception.description)
    
    # 准备模板上下文
    template_ctx = {
        'projects': get_projects(req.context.config.project_dir),
        'topbar_families': TOPBAR_FAMILIES,
        'current_version_path': (None, None, None),
        'current_family': 'A',
        'source_base_url': '/',
        
        'referer': req.referer if req.referer != req.uri else None,
        'bug_report_link': get_github_issue_link(report_error_details),
        'report_error_details': report_error_details,
        
        'error_title': exception.title,
    }
    
    # 如果项目和查询不为空
    if exception.project is not None and exception.query is not None:
        # 添加当前项目的详细信息
        query = exception.query
        project = exception.project
        version = exception.version
        
        # 获取版本缓存
        versions_raw = get_versions_cached(query, req.context, project)
        # 定义获取新版本URL的函数
        get_url_with_new_version = lambda v: stringify_source_path(project, v, '/')
        # 获取版本列表和当前版本路径
        versions, current_version_path = get_versions(versions_raw, get_url_with_new_version, version)
        
        # 更新模板上下文
        template_ctx = {
            **template_ctx,
            
            'current_project': project,
            'versions': versions,
            'current_version_path': current_version_path,
        }
        
        # 如果版本为空，设置为最新版本
        if version is None:
            version = query.query('latest')
        else:
            template_ctx['current_tag'] = version
        
        # 设置源代码基础URL和标识基础URL
        template_ctx['source_base_url'] = get_source_base_url(project, version)
        template_ctx['ident_base_url'] = get_ident_base_url(project, version)
    
    # 如果描述不为空，添加到模板上下文
    if exception.description is not None:
        template_ctx['error_details'] = exception.description
    
    # 合并额外的模板参数
    template_ctx = {
        **template_ctx,
        **exception.extra_template_args,
    }
    
    # 渲染错误页面模板
    template = req.context.jinja_env.get_template('error.html')
    result = template.render(template_ctx)
    
    # 关闭查询对象
    if exception.query is not None:
        exception.query.close()
    
    # 返回渲染结果
    return result

# 从Falcon异常生成错误页面
def get_error_page(req, resp, exception: ElixirProjectError):
    # 生成错误详情摘要
    report_error_details = generate_error_details(req, resp, exception.title, exception.description)
    
    # 准备模板上下文
    template_ctx = {
        'projects': get_projects(req.context.config.project_dir),
        'topbar_families': TOPBAR_FAMILIES,
        'current_version_path': (None, None, None),
        'current_family': 'A',
        'source_base_url': '/',
        
        'referer': req.referer,
        'bug_report_link': ADD_ISSUE_LINK + parse.quote(report_error_details),
        'report_error_details': report_error_details,
        
        'error_title': exception.title,
    }
    
    # 如果描述不为空，添加到模板上下文
    if exception.description is not None:
        template_ctx['error_details'] = exception.description
    
    # 渲染错误页面模板
    template = req.context.jinja_env.get_template('error.html')
    return template.render(template_ctx)

# 验证项目和版本，返回项目、版本和查询。
# 用于项目/版本 URL
def validate_project_and_version(ctx, project, version):
    # 解码并验证项目名称
    project = validate_project(parse.unquote(project))
    # 如果项目名称无效，抛出错误
    if project is None:
        raise ElixirProjectError('Error', '无效的项目名称')

    # 获取项目的查询信息
    query = get_query(ctx.config.project_dir, project)
    # 如果查询信息不存在，抛出错误
    if not query:
        raise ElixirProjectError('Error', '未知项目', status=falcon.HTTP_NOT_FOUND)

    # 解码并验证版本号
    version = validate_version(parse.unquote(version))
    # 如果版本号无效，抛出错误
    if version is None:
        raise ElixirProjectError('Error', '无效的版本号', project=project, query=query)

    # 返回验证后的项目、版本和查询信息
    return project, version, query


# 返回源代码页面的基础 URL
# 假设项目和版本已经解码
def get_source_base_url(project, version):
    # 构建基础 URL 并返回
    return f'/{ parse.quote(project, safe="") }/{ parse.quote(version, safe="") }/source'


# 将 ParsedSourcePath 转换为对应的 URL 路径字符串
def stringify_source_path(project, version, path):
    # 检查路径是否以斜杠开头
    if not path.startswith('/'):
        # 如果不是，则在前面加上斜杠
        path = '/' + path
    # 组合基础 URL 和路径
    path = f'{ get_source_base_url(project, version) }{ path }'
    # 去除路径末尾的斜杠并返回
    return path.rstrip('/')

# 处理根URL请求
class IndexResource:
    def on_get(self, req, resp):
        ctx = req.context  # 获取请求上下文
        project = DEFAULT_PROJECT  # 设置默认项目

        query = get_query(ctx.config.project_dir, project)  # 获取查询对象
        if not query:
            raise ElixirProjectError('Error', f'Unknown default project: {project}',  # 如果查询对象为空，抛出错误
                                     status=falcon.HTTP_INTERNAL_SERVER_ERROR)

        version = parse.quote(query.query('latest'))  # 获取最新版本号并进行URL编码
        resp.status = falcon.HTTP_FOUND  # 设置响应状态为302 Found
        resp.location = stringify_source_path(project, version, '/')  # 设置重定向位置
        return

# 处理源代码URL请求
# 路径参数假定已由转换器解码
class SourceResource:
    def on_get(self, req, resp, project, version, path):
        project, version, query = validate_project_and_version(req.context, project, version)  # 验证项目和版本

        if not path.startswith('/') and len(path) != 0:  # 检查路径是否以斜杠开头且不为空
            path = f'/{ path }'  # 如果不是，则在前面加上斜杠

        if path.endswith('/'):  # 检查路径是否以斜杠结尾
            resp.status = falcon.HTTP_MOVED_PERMANENTLY  # 设置响应状态为301 Moved Permanently
            resp.location = stringify_source_path(project, version, path)  # 设置重定向位置
            return

        # 检查路径是否只包含允许的字符
        if not search('^[A-Za-z0-9_/.,+-]*$', path):
            raise ElixirProjectError('Error', 'Path contains characters that are not allowed',  # 抛出错误
                                     project=project, version=version, query=query)

        if version == 'latest':  # 检查版本是否为最新
            version = parse.quote(query.query('latest'))  # 获取最新版本号并进行URL编码
            resp.status = falcon.HTTP_FOUND  # 设置响应状态为302 Found
            resp.location = stringify_source_path(project, version, path)  # 设置重定向位置
            return

        raw_param = req.get_param('raw')  # 获取原始参数
        if raw_param is not None and raw_param.strip() != '0':  # 检查是否请求原始内容
            generate_raw_source(resp, query, project, version, path)  # 生成原始内容
        else:
            resp.content_type = falcon.MEDIA_HTML  # 设置响应内容类型为HTML
            resp.status, resp.text = generate_source_page(req.context, query, project, version, path)  # 生成源代码页面

        query.close()  # 关闭查询对象

# 处理没有路径的源代码URL请求，例如 '/u-boot/v2023.10/source'
# 注意没有尾部斜杠
class SourceWithoutPathResource(SourceResource):
    def on_get(self, req, resp, project, version):
        return super().on_get(req, resp, project, version, '')  # 调用父类方法，传入空路径

# 返回标识符页面的基础URL
# 假定项目和版本未经过编码
def get_ident_base_url(project, version, family=None):
    project = parse.quote(project, safe="")  # 对项目名称进行URL编码
    version = parse.quote(version, safe="")  # 对版本号进行URL编码
    if family is not None:
        return f'/{ project }/{ version }/{ parse.quote(family, safe="") }/ident'  # 返回带家族的标识符基础URL
    else:
        return f'/{ project }/{ version }/ident'  # 返回不带家族的标识符基础URL

# 将解析后的标识符路径转换为对应的URL路径字符串
def stringify_ident_path(project, version, family, ident):
    path = f'{ get_ident_base_url(project, version, family) }/{ parse.quote(ident, safe="") }'  # 组合基础URL和标识符
    return path.rstrip('/')  # 去除路径末尾的斜杠并返回

# 处理标识符资源的POST重定向请求
class IdentPostRedirectResource:
    def on_get(self, req, resp, project, version, family=None, ident=None):
        project, version, _ = validate_project_and_version(req.context, project, version)  # 验证项目和版本
        resp.status = falcon.HTTP_FOUND  # 设置响应状态为302 Found
        resp.location = stringify_source_path(project, version, "")  # 设置重定向位置

    def on_post(self, req, resp, project, version, family=None, ident=None):
        project, version, query = validate_project_and_version(req.context, project, version)  # 验证项目和版本

        form = req.get_media()  # 获取表单数据
        post_ident = form.get('i')  # 获取标识符
        post_family = form.get('f')  # 获取家族

        if not validFamily(post_family):  # 检查家族是否有效
            post_family = 'C'  # 如果无效，默认设置为'C'

        if not post_ident:  # 检查标识符是否为空
            raise ElixirProjectError('Error', 'Invalid identifier',  # 抛出错误
                                     project=project, version=version, query=query,
                                     extra_template_args={
                                         'searched_ident': parse.unquote(form.get('i')),  # 解码搜索的标识符
                                         'current_family': family,  # 当前家族
                                     })

        post_ident = post_ident.strip()  # 去除标识符首尾的空白字符
        resp.status = falcon.HTTP_MOVED_PERMANENTLY  # 设置响应状态为301 Moved Permanently
        resp.location = stringify_ident_path(project, version, post_family, post_ident)  # 设置重定向位置

        query.close()  # 关闭查询对象

# 处理带有家族参数的标识符URL请求，支持POST和GET
# 有关POST行为，请参见IdentPostRedirectResource
# 路径参数假定已由转换器解码
class IdentResource(IdentPostRedirectResource):
    def on_get(self, req, resp, project, version, family, ident):
        project, version, query = validate_project_and_version(req.context, project, version)  # 验证项目和版本

        family = parse.unquote(family)  # 解码家族
        if not validFamily(family):  # 检查家族是否有效
            family = 'C'  # 如果无效，默认设置为'C'

        ident = parse.unquote(ident)  # 解码标识符
        validated_ident = validate_ident(ident)  # 验证标识符
        if validated_ident is None:  # 检查验证结果
            raise ElixirProjectError('Error', 'Invalid identifier',  # 抛出错误
                                     project=project, version=version, query=query,
                                     extra_template_args={
                                         'searched_ident': ident,  # 搜索的标识符
                                         'current_family': family,  # 当前家族
                                     })

        ident = validated_ident  # 使用验证后的标识符

        if version == 'latest':  # 检查版本是否为最新
            version = parse.quote(query.query('latest'))  # 获取最新版本号并进行URL编码
            resp.status = falcon.HTTP_FOUND  # 设置响应状态为302 Found
            resp.location = stringify_ident_path(project, version, family, ident)  # 设置重定向位置
            return

        resp.content_type = falcon.MEDIA_HTML  # 设置响应内容类型为HTML
        resp.status, resp.text = generate_ident_page(req.context, query, project, version, family, ident)  # 生成标识符页面

        query.close()  # 关闭查询对象

# 处理未指定 family 的 ident URL
# 同时处理没有 family 的 ident URL 的 POST 请求 - IdentPostRedirectResource 继承自 IdentResource
class IdentWithoutFamilyResource(IdentResource):
    # 处理 GET 请求，调用父类方法并默认 family 为 'C'
    def on_get(self, req, resp, project, version, ident):
        super().on_get(req, resp, project, version, 'C', ident)

# 顶部搜索框下拉菜单中可用的文件家族
TOPBAR_FAMILIES = {
    'A': '所有符号',
    'C': 'C/CPP/ASM',
    'K': 'Kconfig',
    'D': 'Devicetree',
    'B': 'DT 兼容',
}

# 返回 basedir 中顶级目录的名称列表
def get_directories(basedir):
    directories = []  # 初始化目录列表
    for filename in os.listdir(basedir):  # 遍历 basedir 下的所有文件和目录
        filepath = os.path.join(basedir, filename)  # 构建文件路径
        if os.path.isdir(filepath):  # 检查是否为目录
            directories.append(filename)  # 将目录名添加到列表中
    return sorted(directories)  # 返回排序后的目录列表

# 项目名称和该项目根 URL 的元组
# 用于渲染项目列表
ProjectEntry = namedtuple('ProjectEntry', 'name, url')

# 返回 basedir 中存储的项目的 ProjectEntry 元组列表
def get_projects(basedir):
    return [ProjectEntry(p, f"/{p}/latest/source") for p in get_directories(basedir)]  # 获取目录并构建 ProjectEntry 列表

# 版本名称和选定资源 URL 的元组
# 用于渲染侧边栏中的版本列表
VersionEntry = namedtuple('VersionEntry', 'version, url')

# 处理 Query.query('version') 的结果并准备用于侧边栏模板的数据
# 返回一个有序字典，包含版本信息和当前版本的三元组 (major, minor, version)
# 参数:
#   versions: 有序字典，主版本号作为键，值为包含次版本号的有序字典，次版本号的值为完整的版本字符串列表
#   get_url: 函数，接受一个版本字符串并返回该版本的 URL
#   current_version: 当前浏览的版本字符串
def get_versions(versions, get_url, current_version):
    """
    处理版本信息并生成结构化的版本字典以及当前版本的路径。

    :param versions: 包含版本信息的字典，结构为 {major: {minor: [patch, ...]}, ...}
    :param get_url: 用于生成给定版本URL的函数
    :param current_version: 当前版本字符串
    :return: 包含处理后的版本信息和当前版本路径的元组
    """
    result = OrderedDict()  # 初始化结果字典
    current_version_path = (None, None, None)  # 初始化当前版本路径
    for major, minor_versions in versions.items():  # 遍历主版本号及其对应的次版本号
        for minor, patch_versions in minor_versions.items():  # 遍历次版本号及其对应的补丁版本号
            for v in patch_versions:  # 遍历补丁版本号
                if major not in result:  # 如果主版本号不在结果字典中
                    result[major] = OrderedDict()  # 初始化主版本号对应的有序字典
                if minor not in result[major]:  # 如果次版本号不在主版本号对应的字典中
                    result[major][minor] = []  # 初始化次版本号对应的列表
                result[major][minor].append(VersionEntry(v, get_url(v)))  # 将版本条目添加到列表中
                if v == current_version:  # 如果当前版本匹配
                    current_version_path = (major, minor, v)  # 更新当前版本路径

    return result, current_version_path  # 返回处理后的版本信息和当前版本路径


def get_versions_cached(q, ctx, project):
    """
    在上下文对象中缓存 `get_versions` 的结果。

    :param q: 查询对象
    :param ctx: 请求上下文对象
    :param project: 项目名称
    :return: 缓存的版本信息
    """
    with ctx.versions_cache_lock:  # 使用锁确保线程安全
        if project not in ctx.versions_cache:  # 如果项目不在缓存中
            ctx.versions_cache[project] = (time.time(), q.query('versions'))  # 将查询结果缓存
            cached_versions = ctx.versions_cache[project]  # 获取缓存的版本信息
        else:
            cached_versions = ctx.versions_cache[project]  # 获取缓存的版本信息
            if time.time() - cached_versions[0] > VERSION_CACHE_DURATION_SECONDS:  # 如果缓存过期
                ctx.versions_cache[project] = (time.time(), q.query('versions'))  # 更新缓存
                cached_versions = ctx.versions_cache[project]  # 获取更新后的缓存

        return cached_versions[1]  # 返回缓存的版本信息
# 返回布局模板使用的上下文信息。

# param q: 查询对象
# param ctx: 请求上下文对象
# param get_url_with_new_version: 用于生成新版本URL的函数
# param project: 项目名称
# param version: 项目版本
# return: 包含项目信息的字典
def get_layout_template_context(q, ctx, get_url_with_new_version, project, version):
    versions_raw = get_versions_cached(q, ctx, project)  # 获取缓存的版本信息
    versions, current_version_path = get_versions(versions_raw, get_url_with_new_version, version)  # 处理版本信息

    return {  # 返回包含项目信息的字典
        'projects': get_projects(ctx.config.project_dir),  # 获取所有项目
        'versions': versions,  # 版本列表
        'current_version_path': current_version_path,  # 当前版本路径
        'topbar_families': TOPBAR_FAMILIES,  # 顶部栏家族信息
        'source_base_url': get_source_base_url(project, version),  # 源代码基础 URL
        'ident_base_url': get_ident_base_url(project, version),  # 标识基础 URL
        'current_project': project,  # 当前项目名称
        'current_tag': parse.unquote(version),  # 当前标签（解码后的版本）
        'current_family': 'A',  # 当前家族
    }

# 生成原始源代码响应
def generate_raw_source(resp, query, project, version, path):
    type = query.query('type', version, path)  # 查询文件类型
    if type != 'blob':  # 如果不是文件
        raise ElixirProjectError('File not found', 'This file does not exist.',  # 抛出文件未找到错误
                                 query=query, project=project, version=version)
    else:
        code = query.get_file_raw(version, path)  # 获取文件原始内容
        resp.content_type = 'application/octet-stream'  # 设置响应内容类型
        resp.text = code  # 设置响应文本内容
        resp.downloadable_as = path.split('/')[-1]  # 设置下载文件名
        # 缓存 24 小时
        resp.cache_control = ('max-age=86400',)
        # 沙箱化结果以防万一
        resp.headers['Content-Security-Policy'] = "sandbox; default-src 'none'"

# 根据文件名猜测文件格式，并返回格式化为 HTML 的代码
def format_code(filename, code):
    import pygments  # 导入 pygments 模块
    import pygments.lexers  # 导入 pygments 词法分析器
    import pygments.formatters  # 导入 pygments 格式化器
    from pygments.lexers.asm import GasLexer  # 导入 GAS 词法分析器
    from pygments.lexers.r import SLexer  # 导入 R 词法分析器

    try:
        lexer = pygments.lexers.guess_lexer_for_filename(filename, code)  # 根据文件名猜测词法分析器
        if filename.endswith('.S') and isinstance(lexer, SLexer):  # 如果是汇编文件且词法分析器为 SLexer
            lexer = GasLexer()  # 使用 GAS 词法分析器
    except pygments.util.ClassNotFound:
        lexer = pygments.lexers.get_lexer_by_name('text')  # 如果找不到合适的词法分析器，使用文本词法分析器

    lexer.stripnl = False  # 不删除换行符
    formatter = pygments.formatters.HtmlFormatter(  # 创建 HTML 格式化器
        # 添加行号列
        linenos=True,
        # 行号包裹在链接 (a) 标签中
        anchorlinenos=True,
        # 每行包裹在带有 id='codeline-{line_number}' 的 span 标签中
        linespans='codeline',
    )
    return pygments.highlight(code, lexer, formatter)  # 返回高亮后的 HTML 代码

# 生成文件的格式化 HTML，并应用过滤器（例如添加标识链接）
# q: 查询对象
# project: 请求的项目名称
# version: 请求的项目版本
# path: 仓库中文件的路径
def generate_source(q, project, version, path):
    code = q.query('file', version, path)  # 获取文件内容

    _, fname = os.path.split(path)  # 获取文件名
    _, extension = os.path.splitext(fname)  # 获取文件扩展名
    extension = extension[1:].lower()  # 转换扩展名为小写
    family = q.query('family', fname)  # 获取文件家族

    source_base_url = get_source_base_url(project, version)  # 获取源代码基础 URL

    def get_ident_url(ident, ident_family=None):
        if ident_family is None:
            ident_family = family  # 如果未指定标识家族，使用文件家族
        return stringify_ident_path(project, version, ident_family, ident)  # 生成标识路径

    filter_ctx = FilterContext(  # 创建过滤器上下文
        q,
        version,
        family,
        path,
        get_ident_url,
        lambda path: f'{ source_base_url }{ "/" if not path.startswith("/") else "" }{ path }',  # 生成文件 URL
        lambda rel_path: f'{ source_base_url }{ os.path.dirname(path) }/{ rel_path }',  # 生成相对路径 URL
    )

    filters = get_filters(filter_ctx, project)  # 获取过滤器

    # 应用过滤器
    for f in filters:
        code = f.transform_raw_code(filter_ctx, code)  # 转换原始代码

    html_code_block = format_code(fname, code)  # 生成格式化 HTML 代码块

    # 将行号替换为当前文件中相应行的链接
    html_code_block = sub('href="#codeline-(\d+)', 'name="L\\1" id="L\\1" href="#L\\1', html_code_block)

    for f in filters:
        html_code_block = f.untransform_formatted_code(filter_ctx, html_code_block)  # 反转换格式化代码

    return html_code_block  # 返回格式化后的 HTML 代码块

# 表示 git 树中的文件条目
# type: 目录 (tree)、文件 (blob) 或符号链接 (symlink)
# name: 文件名
# path: 文件路径，对于符号链接为目标路径
# url: 文件的绝对 URL
# size: 文件大小（字节），目录和符号链接为 None
DirectoryEntry = namedtuple('DirectoryEntry', 'type, name, path, url, size')

# 返回包含目录中文件信息的 DirectoryEntry 对象列表
# q: 查询对象
# base_url: 文件 URL 通过将文件路径附加到此 URL 来创建。不应以斜杠结尾
# tag: 请求的仓库标签
# path: 仓库中目录的路径
def get_directory_entries(q, base_url, tag, path):
    dir_entries = []  # 初始化目录条目列表
    lines = q.query('dir', tag, path)  # 查询目录内容

    for l in lines:
        type, name, size, perm = l.split(' ')  # 分割查询结果
        file_path = f"{ path }/{ name }"  # 构建文件路径

        if type == 'tree':  # 如果是目录
            dir_entries.append(('tree', name, file_path, f"{ base_url }{ file_path }", None))  # 添加目录条目
        elif type == 'blob':  # 如果是文件
            # 120000 权限表示是符号链接
            if perm == '120000':
                dir_path = path if path.endswith('/') else path + '/'  # 确保路径以斜杠结尾
                link_contents = q.get_file_raw(tag, file_path)  # 获取符号链接内容
                link_target_path = os.path.abspath(dir_path + link_contents)  # 获取目标路径

                dir_entries.append(('symlink', name, link_target_path, f"{ base_url }{ link_target_path }", size))  # 添加符号链接条目
            else:
                dir_entries.append(('blob', name, file_path, f"{ base_url }{ file_path }", size))  # 添加文件条目

    return dir_entries  # 返回目录条目列表

# 生成 `source` 路由的响应（状态码和可选HTML）
# ctx: 请求上下文
# q: 查询对象
# project: 项目名称
# version: 项目版本
# path: 文件路径
def generate_source_page(ctx, q, project, version, path):
    status = falcon.HTTP_OK  # 设置默认状态码为200 OK

    source_base_url = get_source_base_url(project, version)  # 获取源代码的基础URL

    type = q.query('type', version, path)  # 查询文件类型

    # 生成面包屑导航链接
    path_split = path.split('/')[1:]  # 将路径按斜杠分割
    path_temp = ''  # 初始化临时路径变量
    breadcrumb_links = []  # 初始化面包屑链接列表
    for p in path_split:
        path_temp += '/' + p  # 构建当前路径
        breadcrumb_links.append((p, f'{ source_base_url }{ path_temp }'))  # 添加面包屑链接

    if type == 'tree':
        back_path = os.path.dirname(path[:-1])  # 获取上一级目录路径
        if back_path == '/':
            back_path = ''  # 如果上一级目录是根目录，则设置为空字符串

        template_ctx = {
            'dir_entries': get_directory_entries(q, source_base_url, version, path),  # 获取目录条目
            'back_url': f'{ source_base_url }{ back_path }' if path != '' else None,  # 获取返回上一级目录的URL
        }
        template = ctx.jinja_env.get_template('tree.html')  # 加载树形视图模板
    elif type == 'blob':
        template_ctx = {
            'code': generate_source(q, project, version, path),  # 生成源代码内容
            'path': path,  # 当前文件路径
        }
        template = ctx.jinja_env.get_template('source.html')  # 加载源代码视图模板
    else:
        raise ElixirProjectError('File not found', 'This file does not exist.',  # 抛出文件未找到错误
                                 status=falcon.HTTP_NOT_FOUND,
                                 query=q, project=project, version=version,
                                 extra_template_args={'breadcrumb_links': breadcrumb_links})

    # 创建标题，如 "Linux source code (v5.5.6) - Bootlin"
    if path == '':
        title_path = ''  # 根路径标题为空
    elif len(path_split) == 1:
        title_path = f'{ path_split[0] } - '  # 一级路径标题
    else:
        title_path = f'{ path_split[-1] } - { "/".join(path_split) } - '  # 深度路径标题

    get_url_with_new_version = lambda v: stringify_source_path(project, v, path)  # 获取新版本的URL

    # 创建模板上下文
    data = {
        **get_layout_template_context(q, ctx, get_url_with_new_version, project, version),  # 获取布局模板上下文

        'title_path': title_path,  # 页面标题路径
        'path': path,  # 当前路径
        'breadcrumb_links': breadcrumb_links,  # 面包屑链接

        **template_ctx,  # 模板特定上下文
    }

    return (status, template.render(data))  # 返回状态码和渲染后的HTML


# 表示文件中的一行及其URL
LineWithURL = namedtuple('LineWithURL', 'lineno, url')

# 表示要在标识模板中呈现的符号出现
# type: 符号类型
# path: 包含符号的文件路径
# line: LineWithURL 列表
SymbolEntry = namedtuple('SymbolEntry', 'type, path, lines')

# 将 SymbolInstance 转换为 SymbolEntry
# path of SymbolInstance 将被附加到 base_url
def symbol_instance_to_entry(base_url, symbol):
    # TODO 这应该是 Query 的职责
    if type(symbol.line) is str:
        line_numbers = symbol.line.split(',')  # 将字符串形式的行号拆分为列表
    else:
        line_numbers = [symbol.line]  # 如果行号已经是列表，则直接使用

    lines = [
        LineWithURL(l, f'{ base_url }/{ symbol.path }#L{ l }')  # 生成带有URL的行
        for l in line_numbers
    ]

    return SymbolEntry(symbol.type, symbol.path, lines)  # 返回 SymbolEntry 对象


# 生成 `ident` 路由的响应（状态码和可选HTML）
# ctx: 请求上下文
# basedir: 数据目录路径，例如："/srv/elixir-data"
# parsed_path: 解析后的标识路径
def generate_ident_page(ctx, q, project, version, family, ident):
    status = falcon.HTTP_OK  # 设置默认状态码为200 OK

    source_base_url = get_source_base_url(project, version)  # 获取源代码的基础URL

    symbol_definitions, symbol_references, symbol_doccomments = q.query('ident', version, ident, family)  # 查询符号定义、引用和文档注释

    symbol_sections = []  # 初始化符号部分列表

    if len(symbol_definitions) or len(symbol_references):
        if len(symbol_definitions):
            defs_by_type = OrderedDict({})  # 初始化按类型分组的定义字典

            # TODO 这应该是 Query 的职责
            for sym in symbol_definitions:
                if sym.type not in defs_by_type:
                    defs_by_type[sym.type] = [symbol_instance_to_entry(source_base_url, sym)]  # 添加新的符号类型
                else:
                    defs_by_type[sym.type].append(symbol_instance_to_entry(source_base_url, sym))  # 添加相同类型的符号

            symbol_sections.append({
                'title': 'Defined',  # 定义部分标题
                'symbols': defs_by_type,  # 符号定义
            })
        else:
            symbol_sections.append({
                'message': 'No definitions found in the database',  # 未找到定义时的提示信息
            })

        if len(symbol_doccomments):
            symbol_sections.append({
                'title': 'Documented',  # 文档部分标题
                'symbols': {'_unknown': [symbol_instance_to_entry(source_base_url, sym) for sym in symbol_doccomments]},  # 文档注释
            })

        if len(symbol_references):
            symbol_sections.append({
                'title': 'Referenced',  # 引用部分标题
                'symbols': {'_unknown': [symbol_instance_to_entry(source_base_url, sym) for sym in symbol_references]},  # 符号引用
            })
        else:
            symbol_sections.append({
                'message': 'No references found in the database',  # 未找到引用时的提示信息
            })

    else:
        if ident != '':
            status = falcon.HTTP_NOT_FOUND  # 如果未找到符号且标识不为空，则返回404 Not Found

    get_url_with_new_version = lambda v: stringify_ident_path(project, v, family, ident)  # 获取新版本的URL

    data = {
        **get_layout_template_context(q, ctx, get_url_with_new_version, project, version),  # 获取布局模板上下文

        'searched_ident': ident,  # 搜索的标识
        'current_family': family,  # 当前家族

        'symbol_sections': symbol_sections,  # 符号部分
    }

    template = ctx.jinja_env.get_template('ident.html')  # 加载标识模板
    return (status, template.render(data))  # 返回状态码和渲染后的HTML


# 定义一个名为Config的命名元组，当前仅包含项目目录路径
Config = namedtuple('Config', 'project_dir')

# 定义一个名为RequestContext的命名元组，包含当前Elixir配置、配置的Jinja环境和日志记录器
RequestContext = namedtuple('RequestContext', 'config, jinja_env, logger, versions_cache, versions_cache_lock')

def get_jinja_env():
    # 获取当前脚本的目录路径
    script_dir = os.path.dirname(os.path.realpath(__file__))
    # 构建模板目录的路径
    templates_dir = os.path.join(script_dir, '../templates/')
    # 创建文件系统加载器，用于加载模板
    loader = jinja2.FileSystemLoader(templates_dir)
    # 返回一个Jinja2环境对象
    return jinja2.Environment(loader=loader)

# 参见 https://falcon.readthedocs.io/en/v3.1.2/user/recipes/raw-url-path.html
# 将默认的未转义URL替换为转义版本
# 注意：这是非标准做法，并不能保证在所有WSGI服务器上都能正常工作
class RawPathComponent:
    def process_request(self, req, resp):
        # 从请求环境中获取原始URI
        raw_uri = req.env.get('RAW_URI') or req.env.get('REQUEST_URI')
        # 如果存在原始URI，则解析出请求路径
        if raw_uri:
            req.path, _, _ = raw_uri.partition('?')

# 为所有请求添加请求上下文
class RequestContextMiddleware:
    def __init__(self, jinja_env):
        # 初始化Jinja环境
        self.jinja_env = jinja_env
        # 初始化版本缓存字典
        self.versions_cache = {}
        # 初始化版本缓存锁
        self.versions_cache_lock = threading.Lock()

    def process_request(self, req, resp):
        # 创建并设置请求上下文
        req.context = RequestContext(
            Config(req.env['LXR_PROJ_DIR']),  # 配置对象
            self.jinja_env,  # Jinja环境
            logging.getLogger(__name__),  # 日志记录器
            self.versions_cache,  # 版本缓存
            self.versions_cache_lock,  # 版本缓存锁
        )

# 将捕获到的异常序列化为JSON或HTML
# 参见 https://falcon.readthedocs.io/en/stable/api/app.html#falcon.App.set_error_serializer
def error_serializer(req, resp, exception):
    # 获取客户端首选的媒体类型
    preferred = req.client_prefers((falcon.MEDIA_HTML, falcon.MEDIA_JSON))
    
    # 如果客户端有首选媒体类型
    if preferred is not None:
        # 如果首选媒体类型是JSON
        if preferred == falcon.MEDIA_JSON:
            # 将异常转换为JSON格式
            resp.data = exception.to_json()
            # 设置响应的内容类型为JSON
            resp.content_type = falcon.MEDIA_JSON
        # 如果首选媒体类型是HTML
        elif preferred == falcon.MEDIA_HTML:
            # 如果异常是ElixirProjectError类型
            if isinstance(exception, ElixirProjectError):
                # 生成项目错误页面
                resp.text = get_project_error_page(req, resp, exception)
            else:
                # 生成通用错误页面
                resp.text = get_error_page(req, resp, exception)
            # 设置响应的内容类型为HTML
            resp.content_type = falcon.MEDIA_HTML
    
    # 添加Vary头，指示响应根据Accept头变化
    resp.append_header('Vary', 'Accept')

# 构建并返回Falcon应用程序
def get_application():
    # 创建Falcon应用程序实例
    app = falcon.App(middleware=[
        RawPathComponent(),  # 处理原始URL路径的中间件
        RequestContextMiddleware(get_jinja_env()),  # 添加请求上下文的中间件
    ])
    
    # 注册自定义路由转换器
    app.router_options.converters['project'] = ProjectConverter
    app.router_options.converters['ident'] = IdentConverter
    
    # 设置错误序列化器
    app.set_error_serializer(error_serializer)
    
    # 添加路由
    app.add_route('/', IndexResource())  # 主页路由
    app.add_route('/{project}/{version}/source/{path:path}', SourceResource())  # 源代码路由
    app.add_route('/{project}/{version}/source', SourceWithoutPathResource())  # 源代码路由（无路径）
    app.add_route('/{project}/{version}/ident', IdentPostRedirectResource())  # 标识符POST重定向路由
    app.add_route('/{project}/{version}/ident/{ident}', IdentWithoutFamilyResource())  # 标识符路由（无家族）
    app.add_route('/{project}/{version}/{family}/ident/{ident}', IdentResource())  # 标识符路由
    app.add_route('/acp', AutocompleteResource())  # 自动完成资源路由
    app.add_route('/api/ident/{project:project}/{ident:ident}', ApiIdentGetterResource())  # API标识符获取路由
    
    # 返回构建好的Falcon应用程序
    return app

# 创建并初始化Falcon应用程序
application = get_application()

