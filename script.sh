#!/bin/sh

#  This file is part of Elixir, a source code cross-referencer.
#
#  Copyright (C) 2017--2020  Mikaël Bouillot
#  <mikael.bouillot@bootlin.com> and contributors
#  Portions copyright (c) 2019 D3 Engineering, LLC
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

# 检查仓库目录是否存在
if [ ! -d "$LXR_REPO_DIR" ]; then
    # 如果不存在，输出错误信息并退出
    echo "$0: Can't find repository"
    exit 1
fi

# 获取当前路径以便稍后找到同级的 find-file-doc-comments.pl 脚本
cur_dir=`pwd`
# 获取脚本的绝对路径
script_path=`realpath "$0"`
# 切换到脚本所在目录
cd `dirname "$script_path"`
# 获取脚本所在目录的绝对路径
script_dir=`pwd`
# 切换回原来的目录
cd "$cur_dir"
# 初始化 DT 绑定兼容字符串支持，默认禁用
dts_comp_support=0

. $script_dir/myadd.sh

# 版本目录处理函数
version_dir()
{
    # 直接输出输入内容
    cat;
}

# 版本修订处理函数
version_rev()
{
    # 直接输出输入内容
    cat;
}

# 获取所有标签
get_tags()
{
    # 获取所有 Git 标签
    git tag |
    # 处理版本目录
    version_dir |
    # 在每个标签后添加 .0
    sed 's/$/.0/' |
    # 按版本号排序
    sort -V |
    # 去掉最后的 .0
    sed 's/\.0$//'
}

# 列出所有标签
list_tags()
{
    # 输出所有标签
    echo "$tags"
}

# 列出所有标签的详细信息
list_tags_h()
{
    # 输出所有标签
    echo "$tags" |
    # 反向排序
    tac |
    # 格式化输出
    sed -r 's/^(v[0-9]*)\.([0-9]*)(.*)$/\1 \1.\2 \1.\2\3/'
}

# 获取最新标签
get_latest()
{
    # 获取所有 Git 标签
    git tag |
    # 处理版本目录
    version_dir |
    # 过滤掉包含 -rc 的标签
    grep -v '\-rc' |
    # 按版本号排序
    sort -V |
    # 获取倒数第 opt1 + 1 个标签
    tail -n $(($opt1 + 1)) |
    # 获取第一个标签
    head -1
}

# 获取对象类型
get_type()
{
    # 将 opt1 转换为版本修订格式
    v=`echo $opt1 | version_rev`
    # 获取 Git 对象类型
    git cat-file -t "$v:`denormalize $opt2`" 2>/dev/null
}

# 获取 Blob 对象
get_blob()
{
    # 获取 Git Blob 对象
    git cat-file blob $opt1
}

# 获取文件内容
get_file()
{
    # 将 opt1 转换为版本修订格式
    v=`echo $opt1 | version_rev`
    # 获取 Git 文件内容
    git cat-file blob "$v:`denormalize $opt2`" 2>/dev/null
}

# 获取目录内容
get_dir()
{
    # 将 opt1 转换为版本修订格式
    v=`echo $opt1 | version_rev`
    # 获取 Git 目录内容
    git ls-tree -l "$v:`denormalize $opt2`" 2>/dev/null |
    # 使用 awk 格式化输出
    awk '{print $2" "$5" "$4" "$1}' |
    # 过滤掉 . 结尾的行
    grep -v ' \.' |
    # 按第一列和第二列排序
    sort -t ' ' -k 1,1r -k 2,2
}

# 分词文件内容
tokenize_file()
{
    # 判断是否指定了 -b 选项
    if [ "$opt1" = -b ]; then
        # 使用 opt2 作为引用
        ref=$opt2
    else
        # 将 opt1 转换为版本修订格式
        v=`echo $opt1 | version_rev`
        # 使用转换后的版本修订格式和 denormalize 后的 opt2 作为引用
        ref="$v:`denormalize $opt2`"
    fi

    # 判断是否指定了 D 选项
    if [ $opt3 = "D" ]; then
        # 不在设备树中切割 -
        regex='s%((/\*.*?\*/|//.*?\001|[^'"'"']"(\\.|.)*?"|# *include *<.*?>|[^\w-])+)([\w-]+)?%\1\n\4\n%g'
    else
        # 默认正则表达式
        regex='s%((/\*.*?\*/|//.*?\001|[^'"'"']"(\\.|.)*?"|# *include *<.*?>|\W)+)(\w+)?%\1\n\4\n%g'
    fi

    # 获取 Git Blob 内容
    git cat-file blob $ref 2>/dev/null |
    # 替换换行符为 \001
    tr '\n' '\1' |
    # 使用 Perl 进行正则替换
    perl -pe "$regex" |
    # 去掉最后一行
    head -n -1
}

# 列出 Blob 对象
list_blobs()
{
    # 将 opt2 转换为版本修订格式
    v=`echo $opt2 | version_rev`

    # 判断是否指定了 -p 选项
    if [ "$opt1" = '-p' ]; then
        # 返回 Blob 哈希和完整路径
        format='\1 \2'
    # 判断是否指定了 -f 选项
    elif [ "$opt1" = '-f' ]; then
        # 返回 Blob 哈希和文件名（不包括路径）
        format='\1 \4'
    else
        # 默认返回只有 Blob 哈希
        format='\1'
        # 将 opt1 转换为版本修订格式
        v=`echo $opt1 | version_rev`
    fi

    # 列出 Git 目录树中的 Blob 对象
    git ls-tree -r "$v" |
    # 使用 sed 进行格式化
    sed -r "s/^\S* blob (\S*)\t(([^/]*\/)*(.*))$/$format/; /^\S* commit .*$/d"
}

# 取消分词
untokenize()
{
    # 删除所有换行符
    tr -d '\n' |
    # 替换 > 为 */
    sed 's/>/\*\//g' |
    # 替换 < 为 /*
    sed 's/</\/\*/g' |
    # 替换 \1\2\3 为 \n<>
    tr '\1\2\3' '\n<>'
}

# 解析定义
parse_defs()
{
    # 根据 opt3 的值调用不同的解析函数
    case $opt3 in
    "C")
        parse_defs_C
        ;;
    "K")
        parse_defs_K
        ;;
    "D")
        parse_defs_D
        ;;
    *)
        parse_dCefs_All $cmd $opt1 $opt2 $opt3
        ;;
    esac
}

# 解析 C 语言定义
parse_defs_C()
{
    # 创建临时目录
    tmp=`mktemp -d`
    # 定义临时文件的完整路径
    full_path=$tmp/$opt2
    # 将 Git Blob 内容写入临时文件
    git cat-file blob "$opt1" > "$full_path"

    # 使用自编的v6.1.0 ctags 解析大部分定义
    ctags -x --kinds-c=+p+x --extras='-{anonymous}' "$full_path" |
    # 过滤掉 operator 和 CONFIG_ 开头的行
    grep -avE "^operator |CONFIG_" |
    # 使用 awk 格式化输出
    awk '{print $1" "$2" "$3}'

    # 解析函数宏，例如 .S 文件中的宏
    perl -ne '/^\s*ENTRY\((\w+)\)/ and print "$1 function $.\n"' "$full_path"
    perl -ne '/^SYSCALL_DEFINE[0-9]\(\s*(\w+)\W/ and print "sys_$1 function $.\n"' "$full_path"

    # 删除临时文件
    rm "$full_path"
    # 删除临时目录
    rmdir $tmp
}

# 解析 Kconfig 定义
parse_defs_K()
{
    # 创建临时目录
    tmp=`mktemp -d`
    # 定义临时文件的完整路径
    full_path=$tmp/$opt2
    # 将 Git Blob 内容写入临时文件
    git cat-file blob "$opt1" > "$full_path"
    # 使用自编的v6.1.0 ctags 解析 Kconfig 定义
    ctags -x --language-force=kconfig --kinds-kconfig=c --extras-kconfig=-{configPrefixed} "$full_path" |
    # 使用 awk 格式化输出
    awk '{print "CONFIG_"$1" "$2" "$3}'
    # 删除临时文件
    rm "$full_path"
    # 删除临时目录
    rmdir $tmp
}

# 解析 DTS 定义
parse_defs_D()
{
    # 创建临时目录
    tmp=`mktemp -d`
    # 定义临时文件的完整路径
    full_path=$tmp/$opt2
    # 将 Git Blob 内容写入临时文件
    git cat-file blob "$opt1" > "$full_path"
    # 使用自编的v6.1.0 ctags 解析 DTS 定义
    ctags -x --language-force=dts "$full_path" |
    # 使用 awk 格式化输出
    awk '{print $1" "$2" "$3}'
    # 删除临时文件
    rm "$full_path"
    # 删除临时目录
    rmdir $tmp
}

# 解析文档
parse_docs()
{
    # 创建临时文件
    tmpfile=`mktemp`

    # 将 Git Blob 内容写入临时文件
    git cat-file blob "$opt1" > "$tmpfile"
    # 调用 find-file-doc-comments.pl 脚本解析文档
    "$script_dir/find-file-doc-comments.pl" "$tmpfile" || exit "$?"

    # 删除临时文件
    rm -rf "$tmpfile"
}

# 获取 DT 兼容性支持状态
dts_comp()
{
    # 输出 DT 兼容性支持状态
    echo $dts_comp_support
}

# 获取项目名称，用于后续确定项目配置文件
project=$(basename `dirname $LXR_REPO_DIR`)

# 定义项目配置文件路径，根据项目名称动态确定
plugin=$script_dir/projects/$project.sh

# 检查项目配置文件是否存在
if [ -f "$plugin" ] ; then
    # 如果存在，则加载项目配置文件，以便执行项目特定的配置或函数
    . $plugin
fi

# 切换到代码仓库目录，这是执行后续操作的基础位置
cd "$LXR_REPO_DIR"

# 检查传入的参数数量，如果没有参数则设置默认命令为帮助
test $# -gt 0 || set help

# 获取第一个参数作为命令
cmd=$1
# 获取第二个参数作为选项1
opt1=$2
# 获取第三个参数作为选项2
opt2=$3
# 获取第四个参数作为选项3
opt3=$4
# 移除已处理的参数
shift

# 定义去规范化函数，去掉字符串的第一个字符
denormalize()
{
    # 使用cut命令去掉字符串的第一个字符
    echo $1 | cut -c 2-
}

# 根据命令进行不同的操作
case $cmd in
    list-tags)
        # 获取标签列表
        tags=`get_tags`

        # 检查是否指定了帮助选项
        if [ "$opt1" = '-h' ]; then
            # 如果指定了帮助选项，调用list_tags_h函数
            list_tags_h
        else
            # 否则调用list_tags函数
            list_tags
        fi
        ;;
    get-latest)
        # 获取最新版本
        get_latest
        ;;
    get-type)
        # 获取类型
        get_type
        ;;
    get-blob)
        # 获取blob对象
        get_blob
        ;;
    get-file)
        # 获取文件
        get_file
        ;;
    get-dir)
        # 获取目录
        get_dir
        ;;
    list-blobs)
        # 列出所有blob对象
        list_blobs
        ;;
    tokenize-file)
        # 对文件进行分词
        tokenize_file
        ;;
    untokenize)
        # 反向分词
        untokenize
        ;;
    parse-defs)
        # 解析定义
        parse_defs
        ;;
    parse-docs)
        # 解析文档
        parse_docs
        ;;
    dts-comp)
        # 处理DTS组件
        dts_comp
        ;;
    help)
        # 显示帮助信息
        echo "Usage: $0 subcommand [args]..."
        exit 1
        ;;
    test)
        opt3="TS"
        parse_defs
        ;;
    *)
        # 处理未知命令
        echo "$0: Unknown subcommand: $cmd"
        exit 1
esac
