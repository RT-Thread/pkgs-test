# pkgs-test 测试框架

## Github Actions使用

### 用法

``` yml
jobs:
  pkgs-test:
    uses: RT-Thread/pkgs-test/.github/workflows/pkgs-action.yml@main
    with:
      # 指定测试的rt-thread内核版本 使用空格分隔
      # branch "branch:[branch]" tag "tag:[tag]"
      # 默认值为 "branch:master tag:v4.1.1"
      rt-thread-versions: "branch:master tag:v4.1.1"

      # 指定测试的bsp 使用空格分隔
      # [bsp]:[toolchain]
      # 默认值为 "qemu-vexpress-a9:sourcery-arm stm32/stm32h750-artpi:sourcery-arm k210:sourcery-riscv-none-embed"
      bsps: "qemu-vexpress-a9:sourcery-arm stm32/stm32h750-artpi:sourcery-arm k210:sourcery-riscv-none-embed"

      # 指定测试的软件包 使用空格或者换行符分隔 仅仅test-specific-pkgs为true时可用。
      # 多行输入可以这样输入
      # pkgs: |
      #     hello
      #     LiteOS-SDK
      # 默认值是 "hello"
      pkgs: "hello"
      
      # 用于测试指定的软件包，用于对rt-thread内核更新的检查，通过参数pkgs指定软件包。
      # 默认值为false，不指定。
      test-specific-pkgs: false

      # 测试package时是否测试latest版本，false时测试latest版本。
      # 默认值为 false
      package-test-nolatest: false
      
      # 测试全部的package，true为测试全部。
      # 默认值为 false
      package-test-all: false

      # 是否执行check-errors，true为检查。
      # 默认值为 true
      check-errors: true

      # 是否从githubpages下载旧的测试结果，并将新的测试结果与其合并，true为下载并合并。
      # 默认值为 false
      package-append-res: false

      # 旧测试结果的githubpages地址。
      # 默认值为 https://rt-thread.github.io/packages/
      pages-url: https://rt-thread.github.io/packages/

      # 是否将测试结果发布到githubpages，true是发布。
      # 默认值为 false
      deploy-pages: false
```
目前可以在软件包索引仓库和软件包仓库使用pkgs-test来测试软件包的编译情况。

### Packages仓库

软件包索引仓库里面目前有两个功能，一个是当发生改动的时候测试改动的软件包，另外就是定时测试全部的软件包。

#### 改动测试

这里是Packages仓库的软件包测试workflow文件其中的一个job，目的是当发生改动的时候测试改动的软件包。

```yml
 change:
        if: ${{ github.event_name == 'pull_request' || github.event_name == 'push'}}
        uses: RT-Thread/pkgs-test/.github/workflows/pkgs-action.yml@main
        with:
            package-append-res: true
            deploy-pages: true
```

这里使用if进行了判断，当workflow的触发事件是pull_request或者push的时候，执行change这个job。

传入的参数有两个，package-append-res用来开启从github pages下载旧的测试结果并且与新的合并，deploy-pages用来开启将测试结果发布到github pagses。

#### 定时全部测试

这里我举出两个jobs的例子，测试master内核版本下两个bsp的软件包编译情况。

``` yml
  master-stm32h750-artpi-test:
        if: ${{ github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'}}
        uses: RT-Thread/pkgs-test/.github/workflows/pkgs-action.yml@main
        with:
            bsps: stm32/stm32h750-artpi:sourcery-arm
            rt-thread-versions: branch:master
            package-append-res: true
            package-test-all: true
            deploy-pages: true
            check-errors: false

    master-k210-test:
        if: ${{ github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'}}
        needs: master-stm32h750-artpi-test
        uses: RT-Thread/pkgs-test/.github/workflows/pkgs-action.yml@main
        with:
            bsps: k210:sourcery-riscv-none-embed
            rt-thread-versions: branch:master
            package-append-res: true
            package-test-all: true
            deploy-pages: true
            check-errors: false
```

测试全部软件包的触发事件有两个，schedule定时测试和workflow_dispatch手动触发，这里也是使用if来判断的。

这里注意一下，测试全部软件包需要一个接着一个按顺序测试，不能并行进行测试，不然发布测试结果会产生冲突，workflow文件也用了concurrency这个参数来确保每次只有一个workflow在运行，让其余的进行等待。

``` yml
concurrency:
    group: pkgs-test
    cancel-in-progress: false # wait for finish.
```

然后解释一下传入的参数。

1. bsps指的就是测试的bsp和其使用的工具链，用冒号进行分隔。
2. rt-thread-versions指的就是内核的版本，branch和tag有两种不同的输入方法`branch:master tag:v4.1.1`
3. package-append-res表示的是从github pages下载旧的测试结果并且与新的合并。
4. package-test-all就是最主要的一个参数，表示测试全部软件包。
5. deploy-pages表示发布测试结果到GitHub pages。
6. check-errors表示关闭错误检查，这里是因为主要目的是发布测试结果，所以用不需要检查是否有软件包没有通过编译测试。

### 软件包仓库

软件包仓库的使用方法比较简单，不需要输入任何参数，它的测试过程和本地测试基本上一致。

这里有一个例子，[https://github.com/RT-Thread-packages/hello](https://github.com/RT-Thread-packages/hello)

它的workflow文件是这样的。

``` yml
name: RT-Thread_Packages_Test

on:
  [push, pull_request]

jobs:
  pkgs-test:
    uses: RT-Thread/pkgs-test/.github/workflows/pkgs-action.yml@main
```
## 本地使用
注意事项：
1. 本测试框架暂时只使用在 linux 电脑上，不支持 Windows，但 Windows 的 wsl2 暂时测试通过，但不排除有什么隐藏问题
2. 本测试框架使用 gcc 进行编译，不支持 gcc 的 bsp 将不会通过测试

用户使用前应使用如下命令安装 pip 依赖

```shell
pip install scons requests tqdm wget dominate PyGithub pytz
```

其命令行参数如下所示

`--config` 加载用户配置文件 默认 config.json

`--pkg` 测试单独软件包 xxx:xxx

`--nolatest` 编译内容是否不包含 latest 版本

`-j` 同时编译的作业数量。默认 16

### 用户使用

1. 可直接使用 python3 pkgs-test.py 执行 config.json 中的配置文件来进行默认 hello 软件包的测试
2. 用户也可更改 config.json 文件中的 pkgs 字段来测试其他软件包
3. 也可通过 --config 指定一个配置文件进行测试
4. 可以通过 config subparser 对配置文件进行配置
5. 也可以通过 check subparser 检查测试结果


### 执行测试

#### 针对于不同使用用户所使用的的测试命令

- 软件包开发者：测试软件包所支持的 bsp、rtt 版本
  - 软件包版本发布测试
    - 可以对指定软件包版本，进行所支持的 bsp、rtt 版本测试
        ```python
            python3 pkgs-test.py --pkg=hello:v1.0.0
        ```
  - 软件包 master 测试 ci
    - 可以在更新软件包代码之后，自动对 master 版本进行所支持的 bsp、rtt 版本测试
        ```python
            python3 pkgs-test.py --pkg=hello:latest
        ```
  - 软件包的所有版本测试
    - 可以对指定软件包的所有版本，进行所支持的 bsp、rtt 版本测试
        ```python
            python3 pkgs-test.py --pkg=hello
        ```
  - 开发者所有软件包测试
    - 可以对指定软件包集合的所有软件包版本，进行所支持的 bsp、rtt 版本测试
        首先改动 config.json 中的 pkgs 字段，例如您要测试 hello1 hello2 两个软件包，要把 pkgs 字段改为 `"pkgs":["hello1","hello2"]`
        之后使用下面的命令
        ```python
            python3 pkgs-test.py
        ```

#### 部分示例

1. 只测试 hello 的 v1.0.0 版本
    ```shell
    python3 pkgs-test.py --pkg=hello:v1.0.0
    ```
   等同于配置文件中的
    ```json
    "pkgs":[
    "hello:v1.0.0"
    ],
    ```
2. 测试多个软件包（修改配置文件中的 pkgs 字段）
    ```json
    "pkgs":[
    "pkg1",
    "pkg2",
    "pkg3",
    ],
    ```

### 使用config设置配置文件
- 设置rt-thread内核版本
  - 单个版本
    ```shell
    python pkgs-test.py config --rtthread=branch:master
    ```
  - 多个版本
    ```shell
    python pkgs-test.py config --rtthread="branch:master tag:v4.1.1"
    ```
- 设置bsp
  - 单个版本
    ```shell
    python pkgs-test.py config --bsps=qemu-vexpress-a9:sourcery-arm
    ```
  - 多个版本
    ```shell
    python pkgs-test.py config --rtthread="qemu-vexpress-a9:sourcery-arm stm32/stm32h750-artpi:sourcery-arm"
    ```
- 指定配置文件
    ```shell
    python pkgs-test.py config  --rtthread=branch:master --file=config.json
    ```
- 指定软件包
    ```shell
    python pkgs-test.py config --pkgs="hello"
    ```

### 使用check检查测试结果
- 检查自动生成的测试结果
    ```shell
    python pkgs-test.py check
    ```
- 指定文件路径
    ```shell
    python pkgs-test.py check --file='pkgs_res_single.json'
    ```
