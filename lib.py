#!/usr/bin/python3

import subprocess  # 导入subprocess模块，用于执行外部命令
import re  # 导入re模块，用于正则表达式操作

def echo(bstr):
    """
    打印字节字符串到控制台。
    
    参数:
    bstr (bytes): 要打印的字节字符串
    """
    print(bstr.decode(), end='')  # 将字节字符串解码为普通字符串并打印，不换行

def script(*args):
    """
    执行脚本并返回输出。
    
    参数:
    *args: 可变数量的参数，传递给脚本
    
    返回:
    bytes: 脚本的输出
    """
    args = ('./script.sh',) + args  # 将脚本路径和参数组合成一个元组
    p = subprocess.run(args, stdout=subprocess.PIPE)  # 执行脚本并将输出捕获到p
    p = p.stdout  # 获取脚本的标准输出
    return p  # 返回脚本的输出

def scriptLines(*args):
    """
    执行脚本并返回按行分割的输出列表。
    
    参数:
    *args: 可变数量的参数，传递给脚本
    
    返回:
    list: 按行分割的脚本输出列表
    """
    p = script(*args)  # 调用script函数获取脚本输出
    p = p.split(b'\n')  # 按行分割输出
    del p[-1]  # 删除最后一个空行
    return p  # 返回按行分割的输出列表

def unescape(bstr):
    """
    对字节字符串进行转义处理。
    
    参数:
    bstr (bytes): 要处理的字节字符串
    
    返回:
    bytes: 处理后的字节字符串
    """
    subs = (
        ('<', '\033[32m/*'),  # 定义转义替换规则
        ('>', '*/\033[0m'),
        ('\1', '\n'),
        ('\2', '<'),
        ('\3', '>'))
    for a, b in subs:
        a = a.encode()  # 将替换规则中的字符编码为字节字符串
        b = b.encode()
        bstr = bstr.replace(a, b)  # 替换字节字符串中的特定字符
    return bstr  # 返回处理后的字节字符串

def isIdent(bstr):
    """
    判断字节字符串是否为标识符。
    
    参数:
    bstr (bytes): 要判断的字节字符串
    
    返回:
    bool: 如果是标识符返回True，否则返回False
    """
    if len(bstr) < 3:  # 如果字节字符串长度小于3，返回False
        return False
    elif re.search(b'_', bstr):  # 如果字节字符串包含下划线，返回True
        return True
    elif re.search(b'^[A-Z0-9]*$', bstr):  # 如果字节字符串只包含大写字母或数字，返回True
        return True
    else:
        return False  # 其他情况返回False

def autoBytes(arg):
    """
    将输入转换为字节字符串。
    
    参数:
    arg (str or int): 输入参数，可以是字符串或整数
    
    返回:
    bytes: 转换后的字节字符串
    """
    if type(arg) is str:  # 如果输入是字符串，编码为字节字符串
        arg = arg.encode()
    elif type(arg) is int:  # 如果输入是整数，先转换为字符串再编码为字节字符串
        arg = str(arg).encode()
    return arg  # 返回转换后的字节字符串
