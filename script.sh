#!/bin/sh

# 检查环境变量 LXR_REPO_DIR 是否指向一个存在的目录
if [ ! -d "$LXR_REPO_DIR" ]; then
    # 如果目录不存在，输出错误信息并退出脚本
    echo "$0: Can't find repository"
    exit 1
fi

# 切换到仓库目录
cd "$LXR_REPO_DIR"

# 检查命令行参数数量，如果没有参数则设置默认参数为 help
test $# -gt 0 || set help

# 获取第一个命令行参数作为命令
cmd=$1
# 移除已处理的第一个参数
shift

# 根据命令执行不同的操作
case $cmd in
    list-tags)
        # 列出前10个 Git 标签，并去掉前缀 'v' 和后缀 '.0'，然后按版本号排序
        git tag |
        head -n 10 |
        sed 's/^v//' |
        sed 's/$/.0/' |
        sort -V |
        sed 's/\.0$//'
        ;;
    get-blob)
        # 获取指定对象的内容
        git cat-file blob $1
        ;;
    get-file)
        # 获取指定标签和路径下的文件内容
        git cat-file blob v$1:$2
        ;;
    get-dir)
        # 列出指定标签和路径下的目录内容，排除根目录
        git ls-tree -l "v$1:$2" |
        awk '{print $2" "$5" "$4}' |
        grep -v ' \.' |
        sort -t ' ' -k 1,1r -k 2,2
        ;;
    list-blobs)
        # 列出指定标签下的所有文件对象
        if [ "$1" = '-p' ]; then
            # 设置输出格式为路径和对象ID
            format='\1 \2'
            shift
        elif [ "$1" = '-f' ]; then
            # 设置输出格式为路径和文件大小
            format='\1 \4'
            shift
        else
            # 默认只输出路径
            format='\1'
        fi

        git ls-tree -r "v$1" |
        sed -r "s/^\S* blob (\S*)\t(([^/]*\/)*(.*))$/$format/"
        ;;
    tokenize-file)
        # 将文件内容进行分词处理
        if [ "$1" = -b ]; then
            # 使用指定的引用
            ref=$2
        else
            # 使用默认的标签和路径
            ref=v$1:$2
        fi

        git cat-file blob $ref |
        tr '\n<>' '\1\2\3' |
        sed 's/\/\*/</g' |
        sed 's/\*\//>/g' |
        sed -r 's/(\W*)(<[^>]*>)?(\w*)/\1\2\n\3\n/g' |
        head -n -1
        ;;
    untokenize)
        # 反向分词处理
        tr -d '\n' |
        sed 's/>/\*\//g' |
        sed 's/</\/\*/g' |
        tr '\1\2\3' '\n<>'
        ;;
    parse-defs)
        # 解析定义并生成标签文件
        tmp=`mktemp -d`
        git cat-file blob "$1" > $tmp/$2
        ctags -x $tmp/$2 | awk '{print $1" "$2" "$3}'
        rm $tmp/$2
        rmdir $tmp
        ;;
    help)
        # 显示帮助信息
        echo "Usage: $0 subcommand [args]..."
        exit 1
        ;;
    *)
        # 处理未知命令
        echo "$0: Unknown subcommand: $cmd"
        exit 1
esac