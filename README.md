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

## 本地使用
注意事项：
1. 本测试框架暂时只使用在 linux 电脑上，不支持 Windows，但 Windows 的 wsl2 暂时测试通过，但不排除有什么隐藏问题
2. 本测试框架使用 gcc 进行编译，不支持 gcc 的 bsp 将不会通过测试

用户使用前应使用如下命令安装 pip 依赖

```shell
pip install scons requests tqdm wget html-table
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

### 针对于不同使用用户所使用的的测试命令
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

### 部分示例

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
