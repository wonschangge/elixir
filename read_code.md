通用的获取所有git标签的方式：

```sh
# 末尾加0以便按version排序，最后再去0
# 可以使比如 v0.1, v0.1-rc1, v0.1-rc2这种，rc排在前
git tag | cat | sed 's/$/.0/' | sort -V | sed 's/\.0$//'

# 再加上反向排序和三级递进式格式化输出
git tag | cat | sed 's/$/.0/' | sort -V | sed 's/\.0$//' | tac |
    sed -r 's/^(v[0-9]*)\.([0-9]*)(.*)$/\1 \1.\2 \1.\2\3/'
```

linux:

```sh
git tag |
cat |
sed -r 's/^(pre|lia64-|)(v?[0-9\.]*)(pre|-[^pf].*?|)(alpha|-[pf].*?|)([0-9]*)(.*?)$/\2#\3@\4@\5@\60@\1.0/' |
sort -V |
sed -r 's/^(.*?)#(.*?)@(.*?)@(.*?)@(.*?)0@(.*?)\.0$/\6\1\2\3\4\5/'
```


uboot的特定list_tags_h:

```sh
# 针对v20xx系列的tags单独处理
git tag |
    cat | 
    sed 's/$/.0/' | 
    sort -V | 
    sed 's/\.0$//' | 
    tac |
    sed -r 's/^(v[0-9]*)\.([0-9]*)(.*)$/\1 \1.\2 \1.\2\3/' |
    grep '^v20' |
    tac |
    sed -r 's/^(v20..)\.([0-9][0-9])(.*)$/\1 \1.\2 \1.\2\3/'

# 针对v1|U系列的tags单独处理
git tag |
    cat | 
    sed 's/$/.0/' | 
    sort -V | 
    sed 's/\.0$//' | 
    tac |
    sed -r 's/^(v[0-9]*)\.([0-9]*)(.*)$/\1 \1.\2 \1.\2\3/' |
    grep -E '^(v1|U)' |
    tac |
    sed -r 's/^/old by-version /'

# 针对LABEL|DENX系列的tags单独处理
git tag |
    cat | 
    sed 's/$/.0/' | 
    sort -V | 
    sed 's/\.0$//' | 
    tac |
    sed -r 's/^(v[0-9]*)\.([0-9]*)(.*)$/\1 \1.\2 \1.\2\3/' |
    grep -E '^(LABEL|DENX)' |
    tac |
    sed -r 's/^/old by-date /'
```

oh的dsoftbus:

```sh

```