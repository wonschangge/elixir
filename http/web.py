#!/usr/bin/python3

from subprocess import check_output  # 导入 subprocess 模块中的 check_output 函数

def shell_exec(cmd):  # 定义执行 shell 命令的函数
    """
    执行 shell 命令并返回输出结果。

    参数:
    cmd (str): 要执行的 shell 命令

    返回:
    list: 命令的输出结果，按行分割后的列表
    """
    try:
        a = check_output(cmd, shell=True)  # 执行命令并捕获输出
    except:
        a = b'error\n'  # 如果命令执行失败，设置输出为 "error"

    # 尝试将输出从字节串解码为字符串
    try:
        a = a.decode('utf-8')  # 使用 UTF-8 编码解码
    except UnicodeDecodeError:
        a = a.decode('iso-8859-1')  # 如果 UTF-8 解码失败，使用 ISO-8859-1 编码解码

    a = a.split('\n')  # 将输出按行分割成列表
    del a[-1]  # 删除最后一行（通常是空行）
    return a  # 返回处理后的输出列表

# 启用调试模式
import cgitb
cgitb.enable()

import cgi  # 导入 CGI 模块
import os  # 导入 os 模块
from re import search, sub  # 导入正则表达式模块
from collections import OrderedDict  # 导入有序字典模块

print('Content-Type: text/html;charset=utf-8\n')  # 设置 HTTP 响应头，指定内容类型为 HTML

form = cgi.FieldStorage()  # 获取 CGI 表单数据
version = form.getvalue('v')  # 获取表单中名为 'v' 的值
if not (version and search('^[A-Za-z0-9.-]+$', version)):  # 验证版本号是否有效
    version = '2.6.11'  # 如果无效，设置默认版本号

url = os.environ['SCRIPT_URL']  # 获取当前脚本的 URL

# 使用正则表达式匹配URL，提取路径部分
m = search('^/source/(.*)$', url)

# 如果匹配成功
if m:
    # 设置模式为'source'
    mode = 'source'
    # 提取路径部分
    path = m.group(1)
    # 检查路径是否只包含字母、数字、下划线、斜杠、点、逗号和加减号
    if not search('^[A-Za-z0-9_/.,+-]*$', path):
        # 如果路径包含非法字符，设置路径为'INVALID'
        path = 'INVALID'
    # 构建新的URL
    url2 = 'source/' + path + '?'

# 如果URL等于'/ident'
elif url == '/ident':
    # 设置模式为'ident'
    mode = 'ident'
    # 从表单中获取标识符
    ident = form.getvalue('i')
    # 检查标识符是否只包含字母、数字和下划线
    if not (ident and search('^[A-Za-z0-9_]*$', ident)):
        # 如果标识符无效，设置为'INVALID'
        ident = 'INVALID'
    # 构建新的URL
    url2 = 'ident?i=' + ident + '&'

# 读取模板头部文件
head = open('template-head').read()

# 替换模板中的$baseurl变量
head = sub('\$baseurl', 'http://lxr2', head)

# 执行查询命令，获取版本列表
lines = shell_exec('cd ..; ./query.py versions')

# 创建一个有序字典来存储版本信息
va = OrderedDict()

# 遍历版本列表
for l in lines:
    # 匹配2.6开头的版本
    if search('^2\.6', l):
        m = search('^(2\.6)(\.[0-9]*)((\.|-).*)?$', l)
    else:
        # 匹配其他版本
        m = search('^([0-9]*)(\.[0-9]*)((\.|-).*)?$', l)

    # 提取主要版本号和次要版本号
    m1 = m.group(1)
    m2 = m.group(2)

    # 如果主要版本号不在字典中，创建一个新的有序字典
    if m1 not in va:
        va[m1] = OrderedDict()
    # 如果主要版本号和次要版本号的组合不在字典中，创建一个新的列表
    if m1 + m2 not in va[m1]:
        va[m1][m1 + m2] = []
    # 将版本号添加到列表中
    va[m1][m1 + m2].append(l)

# 构建版本选择菜单
v = '<ul id="menu">\n'
b = 1
# 遍历主要版本号
for v1k in va:
    v1v = va[v1k]
    # 添加主要版本号的菜单项
    v += ' <li class="menuitem" id="mi0' + str(b) + '"><a href="' + url2 + 'v=' + v1k + '">v' + v1k + '</a>\n'
    b += 1
    # 添加子菜单
    v += ' <ul class="submenu">\n'
    # 遍历次要版本号
    for v2k in v1v:
        v2v = v1v[v2k]
        # 添加次要版本号的菜单项
        v += '  <li><a href="' + url2 + 'v=' + v2k + '">v' + v2k + '</a>\n'
        # 添加子子菜单
        v += '  <ul class="subsubmenu">\n'
        # 遍历具体版本号
        for v3 in v2v:
            v += '   <li><a href="' + url2 + 'v=' + v3 + '">v' + v3 + '</a></li>\n'
        v += '  </ul></li>\n'
    v += ' </ul></li>\n'
v += '</ul>\n'

# 替换模板中的$versions变量
head = sub('\$versions', v, head)

# 如果模式为'source'
if mode == 'source':
    # 构建面包屑导航
    banner = '<a href="source/?v=' + version + '">Linux</a>/'
    p2 = ''
    # 遍历路径中的每个部分
    for p in path.split('/'):
        if p == '': continue
        banner += '<a href="source/' + p2 + p + '/?v=' + version + '">' + p + '</a>/'
        p2 += p + '/'

    # 替换模板中的$banner变量
    head = sub('\$banner', banner, head)
    # 替换模板中的$title变量
    head = sub('\$title', 'Linux/' + path + ' - Linux Cross Reference - Free Electrons', head)
    # 输出头部内容
    print(head, end='')

    # 初始化行列表
    lines = ['null - -']

    # 根据路径类型执行不同的查询命令
    if path[-1:] == '/' or path == '':
        type = 'tree'
        lines += shell_exec('cd ..; ./query.py dir ' + version + ' \'' + path + '\'')
    else:
        type = 'blob'
        lines += shell_exec('cd ..; ./query.py file ' + version + ' \'' + path + '\'')

    # 处理目录类型
    if type == 'tree':
        if path != '':
            lines[0] = 'back - -'

        # 输出目录列表表格
        print('<table>\n')
        for l in lines:
            type, name, size = l.split(' ')

            if type == 'null':
                continue
            elif type == 'tree':
                icon = 'folder.gif'
                size = ''
                path2 = path + name + '/'
                name = name + '/'
            elif type == 'blob':
                icon = 'text.gif'
                size = size + ' bytes'
                path2 = path + name
            elif type == 'back':
                icon = 'back.gif'
                size = ''
                path2 = os.path.dirname(path[:-1]) + '/'
                if path2 == '/': path2 = './'
                name = 'Parent directory'

            print('  <tr>')
            print('    <td><a href="source/' + path2 + '?v=' + version + '"><img src="/icons/' + icon + '" width="20" height="22" border="0" alt="' + icon + '"/></a></td>')
            print('    <td><a href="source/' + path2 + '?v=' + version + '">' + name + '</a></td>')
            print('    <td>' + size + '</td>')

            print('  </tr>\n')

        print('</table>', end='')

    # 处理文件类型
    elif type == 'blob':
        del (lines[0])

        # 输出代码预览
        print('<div id="lxrcode"><pre>')

        width = len(str(len(lines)))
        num = 1
        n2 = ('%' + str(width) + 'd') % num
        for l in lines:
            print('<a name="L' + str(num) + '" href="source/' + path + '?v=' + version + '#L' + str(num) + '">' + n2 + '</a> ', end='')
            l = cgi.escape(l)
            l = sub('"', '&quot;', l)
            l = sub('\033\[31m(.*?)\033\[0m', '<a href="ident?v=' + version + '&i=\\1">\\1</a>', l)
            l = sub('\033\[32m', '<i>', l)
            l = sub('\033\[0m', '</i>', l)
            print(l)
            num += 1
            n2 = ('%' + str(width) + 'd') % num

        print('</pre></div>', end='')

# 如果模式为'ident'
elif mode == 'ident':
    # 替换模板中的$banner变量
    head = sub('\$banner', ident, head)
    # 替换模板中的$title变量
    head = sub('\$title', 'Linux identifier search "' + ident + '" - Linux Cross Reference - Free Electrons', head)
    # 输出头部内容
    print(head, end='')

    # 执行查询命令，获取标识符定义和引用信息
    lines = shell_exec('cd .. ; ./query.py ident ' + version + ' ' + ident)
    lines = iter(lines)

    # 解析定义信息
    m = search('Defined in (\d*) file', next(lines))
    num = int(m.group(1))

    print('Defined in', num, 'files:')
    print('<ul>')
    for i in range(0, num):
        l = next(lines)
        m = search('^(.*): (\d*) \((.*)\)$', l)
        f, n, t = m.groups()
        print('<li><a href="source/' + f + '?v=' + version + '#L' + n + '">' + f + ', line ' + n + ' (as a ' + t + ')</a>', end='')
    print('</ul>')

    next(lines)

    # 解析引用信息
    m = search('Referenced in (\d*) file', next(lines))
    num = int(m.group(1))

    print('Referenced in', num, 'files:')
    print('<ul>')
    for i in range(0, num):
        l = next(lines)
        m = search('^(.*): (.*)$', l)
        f = m.group(1)
        ln = m.group(2).split(',')
        if len(ln) == 1:
            n = ln[0]
            print('<li><a href="source/' + f + '?v=' + version + '#L' + str(n) + '">' + f + ', line ' + str(n) + '</a>', end='')
        else:
            if num > 100:  # 简洁显示
                n = len(ln)
                print('<li><a href="source/' + f + '?v=' + version + '">' + f + '</a>, ' + str(n) + ' times')
            else:  # 详细显示
                print('<li>' + f)
                print('<ul>')
                for n in ln:
                    print('<li><a href="source/' + f + '?v=' + version + '#L' + str(n) + '">line ' + str(n) + '</a>')
                print('</ul>')
    print('</ul>')

# 如果模式无效
else:
    print(head)
    print('Invalid request')

# 输出模板尾部内容
print(open('template-tail').read(), end='')

