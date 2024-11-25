parse_defs()
{
    # 根据 opt3 的值调用不同的解析函数
    case $opt3 in
    "TS")
        parse_defs_TS
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
    ctags -x --language-force=TypeScript "$full_path" |
    # 使用 awk 格式化输出
    awk '{print $1" "$2" "$3}'
    # 删除临时文件
    rm "$full_path"
    # 删除临时目录
    rmdir $tmp
}
