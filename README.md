# The Elixir Cross Referencer
# Elixir 交叉引用

Elixir is a source code cross-referencer inspired by
[LXR](https://en.wikipedia.org/wiki/LXR_Cross_Referencer). It’s written
in Python and its main purpose is to index every release of a C or C{plus}{plus}
project (like the Linux kernel) while keeping a minimal footprint.

Elixir 是一个源代码交叉引用器，灵感来自
[LXR](https://en.wikipedia.org/wiki/LXR_Cross_References)。写的是
在 Python 中，其主要目的是索引 C 或 C{plus}{plus} 的每个版本
项目（如 Linux 内核），同时保持最小的占用空间。

It uses Git as a source-code file store and Berkeley DB for cross-reference
data. Internally, it indexes Git _blobs_ rather than trees of files to avoid
duplicating work and data. It has a straightforward data structure
(reminiscent of older LXR releases) to keep queries simple and fast.

它使用 Git 作为源代码文件存储并使用 Berkeley DB 进行交叉引用
数据。在内部，它索引 Git _blob_ 而不是文件树以避免
重复工作和数据。它有一个简单的数据结构
（让人想起旧的 LXR 版本）以保持查询简单快速。

You can see it in action on https://elixir.bootlin.com/

您可以在 https://elixir.bootlin.com/ 上看到它的运行情况

* [Changelog](CHANGELOG.adoc)
* [更改日志](CHANGELOG.adoc)

# Requirements
# 要求

* Python >= 3.8
* Git >= 1.9
* The Jinja2 and Pygments (>= 2.7) Python libraries
* Berkeley DB (and its Python binding)
* Universal Ctags
* Perl (for non-greedy regexes and automated testing)
* Falcon and `mod_wsgi` (for the REST API)
---
* Python>=3.8
* git >= 1.9
* Jinja2 和 Pygments (>= 2.7) Python 库
* Berkeley DB（及其 Python 绑定）
* Universal Ctags
* Perl（用于非贪婪正则表达式和自动化测试）
* Falcon 和 `mod_wsgi` （用于 REST API）

# Architecture
# 架构

The shell script (`script.sh`) is the lower layer and provides commands
to interact with Git and other Unix utilities. The Python commands use
the shell script’s services to provide access to the annotated source
code and identifier lists (`query.py`) or to create and update the
databases (`update.py`). Finally, the web interface (`web.py`) and
uses the query interface to generate HTML pages and to answer REST
queries, respectively.

shell脚本（`script.sh`）是下层，提供命令
与 Git 和其他 Unix 实用程序交互。 Python 命令使用
shell 脚本的服务提供对带注释的源的访问
代码和标识符列表（`query.py`）或创建和更新
数据库（`update.py`）。最后，网络界面（`web.py`）和
使用查询接口生成HTML页面并回答REST
分别查询。

When installing the system, you should test each layer manually and make
sure it works correctly before moving on to the next one.

安装系统时，应手动测试每一层并进行
确保它正常工作，然后再继续下一个。

# Manual Installation 
# 手动安装

## Install Dependencies 
## 安装依赖项

> For Debian


```
sudo apt install python3-pip python3-venv libdb-dev python3-dev build-essential universal-ctags perl git apache2 libapache2-mod-wsgi-py3 libjansson4
```

## Download Elixir Project
## 下载 Elixir 项目

```
git clone https://github.com/bootlin/elixir.git /usr/local/elixir/
```

## Create a virtualenv for Elixir
## 为 Elixir 创建虚拟环境

```sh
python -m venv /usr/local/elixir/venv
. /usr/local/elixir/venv/bin/activate
pip install -r /usr/local/elixir/requirements.txt
```

## Create directories for project data
## 创建项目数据目录

```
mkdir -p /path/elixir-data/linux/repo
mkdir -p /path/elixir-data/linux/data
```

## Set environment variables
## 设置环境变量

Two environment variables are used to tell Elixir where to find the project’s
local git repository and its databases:

两个环境变量用于告诉 Elixir 在哪里可以找到项目的
本地 git 存储库及其数据库：

* `LXR_REPO_DIR` (the git repository directory for your project)
* `LXR_DATA_DIR` (the database directory for your project)
---
* `LXR_REPO_DIR` （项目的 git 存储库目录）
* `LXR_DATA_DIR` （项目的数据库目录）

Now open `/etc/profile` and append the following content.

现在打开“/etc/profile”并附加以下内容。

```
export LXR_REPO_DIR=/path/elixir-data/linux/repo
export LXR_DATA_DIR=/path/elixir-data/linux/data
```

And then run `source /etc/profile`.

然后运行“source /etc/profile”。

## Clone Kernel source code
## 克隆内核源代码

First clone the master tree released by Linus Torvalds:

首先克隆Linus Torvalds发布的主树：

```
cd /path/elixir-data/linux
git clone --bare https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git repo
```

Then, you should also declare a `stable` remote branch corresponding to the `stable` tree, to get all release updates:

然后，您还应该声明与“stable”树对应的“stable”远程分支，以获取所有版本更新：

```
cd repo
git remote add stable git://git.kernel.org/pub/scm/linux/kernel/git/stable/linux-stable.git
git fetch stable
```

Then, you can also declare an `history` remote branch corresponding to the old Linux versions not present in the other repos, to get all the old version still available:

然后，您还可以声明一个与其他存储库中不存在的旧 Linux 版本相对应的“history”远程分支，以使所有旧版本仍然可用：

```
cd repo
git remote add history https://github.com/bootlin/linux-history.git
git fetch history --tags
```

Feel free to add more remote branches in this way, as Elixir will consider tags from all remote branches.

请随意以这种方式添加更多远程分支，因为 Elixir 会考虑来自所有远程分支的标签。

## First Test 
## 第一次测试

```
cd /usr/local/elixir/
./script.sh list-tags
```

## Create Database 
## 创建数据库

```
. ./venv/bin/activate
./update.py <number of threads>
```

> Generating the full database can take a long time: it takes about 15 hours on a Xeon E3-1245 v5 to index 1800 tags in the Linux kernel. For that reason, you may want to tweak the script (for example, by limiting the number of tags with a "head") in order to test the update and query commands. You can even create a new Git repository and just create one tag instead of using the official kernel repository which is very large.

> 生成完整数据库可能需要很长时间：在 Xeon E3-1245 v5 上为 Linux 内核中的 1800 个标签建立索引大约需要 15 个小时。因此，您可能需要调整脚本（例如，通过限制带有“head”的标签数量）以测试更新和查询命令。您甚至可以创建一个新的 Git 存储库，只创建一个标签，而不是使用非常大的官方内核存储库。

## Second Test 
## 第二次测试

Verify that the queries work:

验证查询是否有效：

```console
$ ./elixir/query.py v4.10 ident raw_spin_unlock_irq C
$ ./elixir/query.py v4.10 file /kernel/sched/clock.c
```

**📌 NOTE**\
`v4.10` can be replaced with any other tag.
NOTE: Don’t forget to activate the virtual environment!

**📌注意**\
`v4.10` 可以替换为任何其他标签。
注意：不要忘记激活虚拟环境！

## Configure httpd
## 配置httpd

The CGI interface (`web.py`) is meant to be called from your web
server. Since it includes support for indexing multiple projects,
it expects a different variable (`LXR_PROJ_DIR`) which points to a
directory with a specific structure:

CGI 接口 (`web.py`) 旨在从您的 Web 调用
服务器。由于它包括对多个项目建立索引的支持，
它需要一个不同的变量（`LXR_PROJ_DIR`），它指向
具有特定结构的目录：

* `<LXR_PROJ_DIR>`
  * `<project 1>`
    * `data`
    * `repo`
  * `<project 2>`
    * `data`
    * `repo`
  * `<project 3>`
    * `data`
    * `repo`
* `<LXR_PROJ_DIR>`

It will then generate the other two variables upon calling the query
command.

然后，它将在调用查询时生成其他两个变量
命令。

Now replace `/etc/apache2/sites-enabled/000-default.conf` with `docker/000-default.conf`.
Note: If using httpd (RedHat/Centos) instead of apache2 (Ubuntu/Debian),
the default config file to edit is `/etc/httpd/conf.d/elixir.conf`.

现在将“/etc/apache2/sites-enabled/000-default.conf”替换为“docker/000-default.conf”。
注意：如果使用 httpd (RedHat/Centos) 而不是 apache2 (Ubuntu/Debian)，
要编辑的默认配置文件是“/etc/httpd/conf.d/elixir.conf”。

Finally, start the httpd server.

最后，启动httpd服务器。

```
systemctl restart apache2
```

## Configure SELinux policy
## 配置 SELinux 策略

When running systemd with SELinux enabled, httpd server can only visit limited directories.
If your /path/elixir-data/ is not one of these allowed directories, you will be responded with 500 status code.

当在启用 SELinux 的情况下运行 systemd 时，httpd 服务器只能访问有限的目录。
如果您的 /path/elixir-data/ 不是这些允许的目录之一，您将收到 500 状态代码响应。

To allow httpd server to visit /path/elixir-data/, run following codes:

要允许httpd服务器访问/path/elixir-data/，请运行以下代码：

```
chcon -R -t httpd_sys_rw_content_t /path/elixir-data/
```

To check if it takes effect, run the following codes:

运行以下代码检查是否生效：

```
ls -Z /path/elixir-data/
```

In case you want to check SELinux log related with httpd, run the following codes:

如果您想查看与httpd相关的SELinux日志，请运行以下代码：

```
audit2why -a | grep httpd | less
```

## Configure systemd log directory
## 配置systemd日志目录

By default, the error log of elixir will be put in /tmp/elixir-errors.
However, systemd enables PrivateTmp by default.
And, the final error directory will be like /tmp/systemd-private-xxxxx-httpd.service-xxxx/tmp/elixir-errors.
If you want to disable it, configure httpd.service with the following attribute:

默认情况下，elixir 的错误日志会放在 /tmp/elixir-errors 中。
但是，systemd 默认启用 PrivateTmp。
并且，最终的错误目录将类似于 /tmp/systemd-private-xxxxx-httpd.service-xxxx/tmp/elixir-errors。
如果要禁用它，请使用以下属性配置 httpd.service：

```
PrivateTmp=false
```

## Configuration for other servers
## 其他服务器的配置

Other HTTP servers (like nginx or lighthttpd) may not support WSGI and may require a separate WSGI server, like uWSGI.

其他 HTTP 服务器（如 nginx 或 lighthttpd）可能不支持 WSGI，并且可能需要单独的 WSGI 服务器，如 uWSGI。

Information about how to configure uWSGI with Lighthttpd can be found here:
https://redmine.lighttpd.net/projects/lighttpd/wiki/HowToPythonWSGI#Python-WSGI-apps-via-uwsgi-SCGI-FastCGI-or-HTTP-using-the-uWSGI-server

有关如何使用 Lighthttpd 配置 uWSGI 的信息可以在这里找到：
https://redmine.lighttpd.net/projects/lighttpd/wiki/HowToPythonWSGI#Python-WSGI-apps-via-uwsgi-SCGI-FastCGI-or-HTTP-using-the-uWSGI-server

Pull requests with example uWSGI configuration for Elixir are welcome.

欢迎使用 Elixir 的示例 uWSGI 配置请求请求。

# REST API usage 
# REST API 使用

After configuring httpd, you can test the API usage:

配置好httpd后，可以测试API使用情况：

## ident query
## 身份查询

Send a get request to `/api/ident/<Project>/<Ident>?version=<version>&family=<family>`.
For example:

发送 get 请求到 `/api/ident/<Project>/<Ident>?version=<version>&family=<family>`。
例如：

```
curl http://127.0.0.1/api/ident/barebox/cdev?version=latest&family=C
```

The response body is of the following structure:
响应主体的结构如下：

```
{
    "definitions":
        [{"path": "commands/loadb.c", "line": 71, "type": "variable"}, ...],
    "references":
        [{"path": "arch/arm/boards/cm-fx6/board.c", "line": "64,64,71,72,75", "type": null}, ...]
}
```

# Maintenance and enhancements
# 维护和增强

## Using a cache to improve performance
## 使用缓存来提高性能

At Bootlin, we’re using the [Varnish http cache](https://varnish-cache.org/)
as a front-end to reduce the load on the server running the Elixir code.

在 Bootlin，我们使用 [Varnish http 缓存](https://varnish-cache.org/)
作为前端来减少运行 Elixir 代码的服务器的负载。


    .-------------.           .---------------.           .-----------------------.
    | Http client | --------> | Varnish cache | --------> | Apache running Elixir |
    '-------------'           '---------------'           '-----------------------'

## Keeping Elixir databases up to date
## 保持 Elixir 数据库最新

To keep your Elixir databases up to date and index new versions that are released,
we’re proposing to use a script like `utils/update-elixir-data` which is called
through a daily cron job.

为了使您的 Elixir 数据库保持最新并为发布的新版本建立索引，
我们建议使用像“utils/update-elixir-data”这样的脚本，它被称为
通过日常 cron 作业。

You can set `$ELIXIR_THREADS` if you want to change the number of threads used by
update.py for indexing (by default the number of CPUs on your system).

如果你想改变使用的线程数，你可以设置`$ELIXIR_THREADS`
update.py 用于索引（默认情况下是系统上的 CPU 数量）。

## Keeping git repository disk usage under control
## 控制 git 存储库磁盘使用

As you keep updating your git repositories, you may notice that some can become
considerably bigger than they originally were. This seems to happen when a `gc.log`
file appears in a big repository, apparently causing git’s garbage collector (`git gc`)
to fail, and therefore causing the repository to consume disk space at a fast
pace every time new objects are fetched.

当您不断更新 git 存储库时，您可能会注意到有些可能会变成
比原来大得多。这似乎发生在 `gc.log` 时
文件出现在一个大存储库中，显然导致 git 的垃圾收集器（`gi​​t gc`）
失败，从而导致存储库快速消耗磁盘空间
每次获取新对象时的速度。

When this happens, you can save disk space by packing git directories as follows:

发生这种情况时，您可以通过打包 git 目录来节省磁盘空间，如下所示：

```
cd <bare-repo>
git prune
rm gc.log
git gc --aggressive
```

Actually, a second pass with the above commands will save even more space.

实际上，第二次使用上述命令将节省更多空间。

To process multiple git repositories in a loop, you may use the
`utils/pack-repositories` that we are providing, run from the directory
where all repositories are found.

要循环处理多个 git 存储库，您可以使用
我们提供的“utils/pack-repositories”，从目录运行
找到所有存储库的地方。

# Building Docker images 
# 构建 Docker 镜像

Dockerfiles are provided in the `docker/` directory.
To build the image, run the following commands:

Dockerfiles 在 `docker/` 目录中提供。
要构建图像，请运行以下命令：


    # git clone https://github.com/bootlin/elixir
    # docker build -t elixir -f ./elixir/docker/Dockerfile ./elixir/

You can then run the image using `docker run`.
Here we mount a host directory as Elixir data:

然后您可以使用“docker run”运行该映像。
这里我们挂载一个主机目录作为 Elixir 数据：

    # mkdir ./elixir-data
    # docker run -v ./elixir-data/:/srv/elixir-data -d --name elixir-container elixir
    # docker run -p 8080:80 -v ./elixir-data/:/srv/elixir-data -d --name elixir-container elixir

The Docker image does not contain any repositories.
To index a repository, you can use the `index-repository` script.
For example, to add the [musl](https://musl.libc.org/) repository, run:

Docker 映像不包含任何存储库。
要为存储库建立索引，您可以使用“index-repository”脚本。
例如，要添加 [musl](https://musl.libc.org/) 存储库，请运行：

    # docker exec -it -e PYTHONUNBUFFERED=1 elixir-container \
       /bin/bash -c 'export "PATH=/usr/local/elixir/venv/bin:$PATH" ; \
       /usr/local/elixir/utils/index-repository \
       musl https://git.musl-libc.org/git/musl'

Without PYTHONUNBUFFERED environment variable, update logs may show up with a delay.

如果没有 PYTHONUNBUFFERED 环境变量，更新日志可能会延迟显示。

Or, to run indexing in a separate container:

或者，要在单独的容器中运行索引：

    # docker run -e PYTHONUNBUFFERED=1 -v ./elixir-data/:/srv/elixir-data \
       --entrypoint /bin/bash elixir -c \
       'export "PATH=/usr/local/elixir/venv/bin:$PATH" ; \
       /usr/local/elixir/utils/index-repository \
       musl https://git.musl-libc.org/git/musl'

You can also use utils/index-all-repositories to start indexing all officially supported repositories.

您还可以使用 utils/index-all-repositories 开始为所有官方支持的存储库建立索引。

After indexing is done, Elixir should be available under the following URL on your host:
http://172.17.0.2/musl/latest/source

索引完成后，Elixir 应该可以在主机上的以下 URL 下使用：
http://172.17.0.2/musl/latest/source

If 172.17.0.2 does not answer, you can check the IP address of the container by running:

如果 172.17.0.2 没有应答，您可以通过运行以下命令检查容器的 IP 地址：

    # docker inspect elixir-container | grep IPAddress

## Automatic repository updates
## 自动存储库更新

The Docker image does not automatically update repositories by itself.
You can, for example, start `utils/update-elixir-data` in the container (or in a separate container, with Elixir data volume/directory mounted)
from cron on the host to periodically update repositories.

Docker 镜像本身不会自动更新存储库。
例如，您可以在容器中（或在单独的容器中，安装了 Elixir 数据卷/目录）启动 `utils/update-elixir-data`
从主机上的 cron 定期更新存储库。

## Using Docker image as a development server
## 使用 Docker 镜像作为开发服务器

You can easily use the Docker image as a development server by following the steps above, but mounting Elixir source directory from the host
into `/usr/local/elixir/` in the container when running `docker run elixir`.

您可以按照上述步骤轻松使用 Docker 镜像作为开发服务器，但需要从主机挂载 Elixir 源目录
运行“docker run elixir”时进入容器中的“/usr/local/elixir/”。

Changes in the code made on the host should be automatically reflected in the container.
You can use `apache2ctl` to restart Apache.
Error logs are available in `/var/log/apache2/error.log` within the container.

在主机上进行的代码更改应自动反映在容器中。
您可以使用 apache2ctl 重新启动 Apache。
错误日志可在容器内的“/var/log/apache2/error.log”中找到。

# Hardware requirements 
# 硬件要求

Performance requirements depend mostly on the amount of traffic that you get
on your Elixir service. However, a fast server also helps for the initial
indexing of the projects.

性能要求主要取决于您获得的流量
在您的 Elixir 服务上。然而，快速的服务器也有助于初始
项目索引。

SSD storage is strongly recommended because of the frequent access to
git repositories.

由于频繁访问，强烈推荐SSD存储
git 存储库。

At Bootlin, here are a few details about the server we’re using:

在 Bootlin，以下是有关我们正在使用的服务器的一些详细信息：

* As of July 2019, our Elixir service consumes 17 GB of data (supporting all projects),
or for the Linux kernel alone (version 5.2 being the latest), 12 GB for indexing data,
and 2 GB for the git repository.
* We’re using an LXD instance with 8 GB of RAM on a cloud server with 8 CPU cores
running at 3.1 GHz.

* 截至 2019 年 7 月，我们的 Elixir 服务消耗 17 GB 数据（支持所有项目），
或者仅对于 Linux 内核（最新版本 5.2），12 GB 用于索引数据，
2 GB 用于 git 存储库。
* 我们在具有 8 个 CPU 核心的云服务器上使用具有 8 GB RAM 的 LXD 实例
运行频率为 3.1 GHz。

# Contributing to Elixir 
# 为 Elixir 做出贡献

## Supporting a new project
## 支持新项目

Elixir has a very simple modular architecture that allows to support
new source code projects by just adding a new file to the Elixir sources.

Elixir 有一个非常简单的模块化架构，可以支持
只需将新文件添加到 Elixir 源即可创建新的源代码项目。

Elixir’s assumptions: Elixir 的假设：

* Project sources have to be available in a git repository
* All project releases are associated to a given git tag. Elixir
only considers such tags.
---
* 项目源必须在 git 存储库中可用
* 所有项目版本都与给定的 git 标签相关联。灵丹妙药
只考虑这样的标签。

First make an installation of Elixir by following the above instructions.
See the `projects` subdirectory for projects that are already supported.

首先按照上述说明安装 Elixir。
请参阅“projects”子目录以获取已支持的项目。

Once Elixir works for at least one project, it’s time to clone the git
repository for the project you want to support:

一旦 Elixir 至少适用于一个项目，就该克隆 git 了
您想要支持的项目的存储库：

    cd /srv/git
    git clone --bare https://github.com/zephyrproject-rtos/zephyr

After doing this, you may also reference and fetch remote branches for this project,
for example corresponding to the `stable` tree for the Linux kernel (see the
instructions for Linux earlier in this document).

完成此操作后，您还可以引用并获取该项目的远程分支，
例如对应于 Linux 内核的 `stable` 树（参见
本文档前面针对 Linux 的说明）。

Now, in your `LXR_PROJ_DIR` directory, create a new directory for the
new project:

现在，在“LXR_PROJ_DIR”目录中，为
新项目：

    cd $LXR_PROJ_DIR
    mkdir -p zephyr/data
    ln -s /srv/git/zephyr.git repo
    export LXR_DATA_DIR=$LXR_PROJ_DIR/data
    export LXR_REPO_DIR=$LXR_PROJ_DIR/repo

Now, go back to the Elixir sources and test that tags are correctly
extracted:

现在，返回 Elixir 源并测试标签是否正确
提取：

    ./script.sh list-tags

Depending on how you want to show the available versions on the Elixir pages,
you may have to apply substitutions to each tag string, for example to add
a `v` prefix if missing, for consistency with how other project versions are
shown. You may also decide to ignore specific tags. All this can be done
by redefining the default `list_tags()` function in a new `projects/<projectname>.sh`
file. Here’s an example (`projects/zephyr.sh` file):

根据您想要在 Elixir 页面上显示可用版本的方式，
您可能必须对每个标记字符串进行替换，例如添加
如果缺少，则添加“v”前缀，以与其他项目版本保持一致
显示。您也可以决定忽略特定标签。这一切都可以做到
通过在新的“projects/<projectname>.sh”中重新定义默认的“list_tags()”函数
文件。这是一个示例（`projects/zephyr.sh` 文件）：

    list_tags()
    {
        echo "$tags" |
        grep -v '^zephyr-v'
    }

Note that `<project_name>` **must** match the name of the directory that
you created under `LXR_PROJ_DIR`.

请注意，“<project_name>”**必须**与该目录的名称匹配
您在“LXR_PROJ_DIR”下创建。

The next step is to make sure that versions are classified as you wish
in the version menu. This classification work is done through the
`list_tags_h()` function which generates the output of the `./scripts.sh list-tags -h`
command. Here’s what you get for the Linux project:

下一步是确保版本按照您的意愿进行分类
在版本菜单中。这种分类工作是通过
`list_tags_h()` 函数生成 `./scripts.sh list-tags -h` 的输出
命令。以下是您从 Linux 项目中获得的内容：

    v4 v4.16 v4.16
    v4 v4.16 v4.16-rc7
    v4 v4.16 v4.16-rc6
    v4 v4.16 v4.16-rc5
    v4 v4.16 v4.16-rc4
    v4 v4.16 v4.16-rc3
    v4 v4.16 v4.16-rc2
    v4 v4.16 v4.16-rc1
    ...

The first column is the top level menu entry for versions.
The second one is the next level menu entry, and
the third one is the actual version that can be selected by the menu.
Note that this third entry must correspond to the exact
name of the tag in git.

第一列是版本的顶级菜单条目。
第二个是下一级菜单条目，并且
第三个是可以通过菜单选择的实际版本。
请注意，第三个条目必须准确对应
git 中标签的名称。

If the default behavior is not what you want, you will have
to customize the `list_tags_h` function.

如果默认行为不是您想要的，您将有
自定义 `list_tags_h` 函数。

You should also make sure that Elixir properly identifies
the most recent versions:

您还应该确保 Elixir 正确识别
最新版本：

    ./script.sh get-latest

If needed, customize the `get_latest()` function.

如果需要，自定义“get_latest()”函数。

If you want to enable support for `compatible` properties in Devicetree files,
add `dts_comp_support=1` at the beginning of `projects/<projectname>.sh`.

如果您想在 Devicetree 文件中启用对“兼容”属性的支持，
在“projects/<projectname>.sh”开头添加“dts_comp_support=1”。

You are now ready to generate Elixir’s database for your
new project:

您现在已准备好为您的 Elixir 数据库生成
新项目：

    ./update.py <number of threads>

You can then check that Elixir works through your http server.

然后您可以通过您的 http 服务器检查 Elixir 是否正常工作。

## Coding style 
## 编码风格

If you wish to contribute to Elixir’s Python code, please
follow the [official coding style for Python](https://www.python.org/dev/peps/pep-0008/).

如果您想为 Elixir 的 Python 代码做出贡献，请
遵循[Python 官方编码风格](https://www.python.org/dev/peps/pep-0008/)。

## How to send patches
## 如何发送补丁

The best way to share your contributions with us is to https://github.com/bootlin/elixir/pulls[file a pull
request on GitHub].

与我们分享您的贡献的最佳方式是 https://github.com/bootlin/elixir/pulls[file a pull
在 GitHub 上请求]。

# Automated testing # 自动化测试

Elixir includes a simple test suite in `t/`.  To run it,
from the top-level Elixir directory, run:

Elixir 在 `t/` 中包含一个简单的测试套件。要运行它，
从顶级 Elixir 目录中，运行：

    prove

The test suite uses code extracted from Linux v5.4 in `t/tree`.

该测试套件使用从“t/tree”中的 Linux v5.4 中提取的代码。

## Licensing of code in `t/tree`
## `t/tree` 中代码的许可

The copied code is licensed as described in the [COPYING](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/plain/COPYING) file included with
Linux.  All the files copied carry SPDX license identifiers of `GPL-2.0+` or
`GPL-2.0-or-later`.  Per [GNU’s compatibility table](https://www.gnu.org/licenses/gpl-faq.en.html#AllCompatibility), GPL 2.0+ code can be used
under GPLv3 provided the combination is under GPLv3.  Moreover, https://www.gnu.org/licenses/license-list.en.html#AGPLv3.0[GNU’s overview
of AGPLv3] indicates that its terms "effectively consist of the terms of GPLv3"
plus the network-use paragraph.  Therefore, the developers have a good-faith
belief that licensing these files under AGPLv3 is authorized.  (See also https://github.com/Freemius/wordpress-sdk/issues/166#issuecomment-310561976[this
issue comment] for another example of a similar situation.)

复制的代码按照 [COPYING](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/plain/COPYING) 文件中的描述进行许可
Linux。复制的所有文件都带有“GPL-2.0+”的 SPDX 许可证标识符或
`GPL-2.0-或更高版本`。根据 [GNU 兼容性表](https://www.gnu.org/licenses/gpl-faq.en.html#AllCompatibility)，可以使用 GPL 2.0+ 代码
符合 GPLv3，前提是该组合符合 GPLv3。此外，https://www.gnu.org/licenses/license-list.en.html#AGPLv3.0[GNU 的概述
AGPLv3] 表明其术语“有效地包含 GPLv3 的条款”
加上网络使用段落。所以开发商有诚意
相信根据 AGPLv3 许可这些文件已获得授权。 （另请参阅https://github.com/Freemius/wordpress-sdk/issues/166#issuecomment-310561976[此
问题评论] 类似情况的另一个例子。）

# License
# 许可证

Elixir is copyright (c) 2017--2020 its contributors.  It is licensed AGPLv3.
See the `COPYING` file included with Elixir for details.

Elixir 的版权所有 (c) 2017--2020 其贡献者。它已获得 AGPLv3 许可。
有关详细信息，请参阅 Elixir 附带的“COPYING”文件。