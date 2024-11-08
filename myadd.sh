# 获取第一个参数作为命令
cmd=$1
# 获取第二个参数作为选项1
opt1=$2
# 获取第三个参数作为选项2
opt2=$3
# 获取第四个参数作为选项3
opt3=$4


parse_dCefs_All() {
    echo cmd:$cmd
    echo opt1:$opt1
    echo opt2:$opt2
    echo opt3:$opt3
    return

    case $opt3 in
    "TS")
        parse_defs_TS
        ;;

    ::)
        parse_dCefs_All $opt3
        ;;
    esac
}

# 解析 TS 定义
parse_defs_TS()
{
    # 创建临时目录
    tmp=`mktemp -d`
    # 定义临时文件的完整路径
    full_path=$tmp/$opt2
    # 将 Git Blob 内容写入临时文件
    git cat-file blob "$opt1" > "$full_path"
    # 使用 ctags-universal 解析 DTS 定义
    ctags-universal -x --language-force=TypeScript "$full_path" |
    # 使用 awk 格式化输出
    awk '{print $1" "$2" "$3}'
    # 删除临时文件
    rm "$full_path"
    # 删除临时目录
    rmdir $tmp
}
