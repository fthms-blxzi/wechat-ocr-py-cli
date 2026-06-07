# 微信 OCR Python CLI (wechat-ocr-py-cli)

[English](README.en-US.md) | [简体中文](README.md)

一个在 Windows 上并行运行微信 4.x OCR 的独立、轻量级、高性能命令行界面 (CLI)。它编译了 C++ 封装引擎，打包了所需的微信可执行程序和运行库，并将所有内容打包成一个无任何外部依赖的单文件可执行程序 (`wechat-ocr-py-cli.exe`)。

## 功能特性

- **零依赖单文件可执行程序**：运行所需的所有组件（微信 `Weixin.exe`、`mmmojo_64.dll`、`Weixin.dll`、模型文件及 C++ 绑定库）均已打包至单个文件中。运行期无需系统中安装微信。
- **高性能并行处理**：利用 Python 的 `multiprocessing` 进程池实现高并发并发 OCR 处理。
- **多种输入输出模式**：
  - 通过 `--input` 处理单张图片。
  - 通过标准输入（stdin 管道）动态流式传输图片路径，或通过 `--input-list` 从文本文件中加载图片路径。
  - 将结果输出到文件或 stdout（以 JSONLines 格式）。
- **健壮的路径处理**：自动剥离流式传输及文件读取路径中的 Unicode 字节顺序标记 (BOM) (`\ufeff`)。
- **详尽的帮助命令**：`--help` 屏幕动态展示打包的微信版本、微信 OCR 引擎版本以及详细的构建元数据（如编译器、代码库引用和 Python 版本）。

## 构建设置

### 前提条件

- Windows 操作系统
- Python 3.11+
- [Git](https://git-scm.com/)
- [7-Zip](https://7-zip.org/)（确保 `7z` 命令在系统环境变量 `PATH` 中可用）
- Visual Studio Build Tools / MSBuild（首选并主要支持 MSVC 编译器工具链，MinGW GCC 用作备用。注意：目前不支持 LLVM/Clang）。

### 编译与打包

1. 安装构建依赖：
   ```powershell
   pip install -r requirements.txt
   ```

2. 运行自动化构建脚本：
   ```powershell
   python build.py
   ```
   *脚本将自动克隆 C++ 封装库、应用 CMake 兼容性补丁、使用 MSVC 编译原生二进制文件、检测或下载微信 4.x 运行环境、写入元数据，并使用 PyInstaller 在 `dist/wechat-ocr-py-cli.exe` 处编译生成最终的单文件可执行程序。*

3. 自定义 C++ 源码版本（可选）：
   您可以通过设置 `WECHAT_OCR_CPP_REPO_REF` 环境变量来指定编译 C++ 绑定时检出的 Git 分支、提交哈希或标签（默认指向 `e32d4af10d8045f8613078bac2df442662c76b03`）：
   ```powershell
   $env:WECHAT_OCR_CPP_REPO_REF = "origin/master"
   python build.py
   ```

4. 自定义微信目标版本（可选）：
   您可以通过设置 `WECHAT_VERSION` 环境变量来指定下载并打包的特定微信版本（默认值为 `4.1.10.27`）：
   ```powershell
   $env:WECHAT_VERSION = "4.1.10.27"
   python build.py
   ```

## 非独立（轻量）构建模式

为了生成体积大幅缩小的可执行程序，您可以使用 **非独立构建模式** (Non-Standalone Mode) 构建 CLI。在此模式下，CLI 不会打包庞大的微信 DLL 或模型文件，而是在运行期动态加载它们。

### 构建方式
在运行 `build.py` 之前设置环境变量：
```powershell
$env:WECHAT_OCR_NON_STANDALONE = "1"
python build.py
```
这会生成 `dist/wechat-ocr-py-cli-ns.exe`。

### 运行期使用
运行非独立版可执行程序时，您可以通过命令行参数显式提供本地已安装微信的路径：

```powershell
dist\wechat-ocr-py-cli-ns.exe --wechat-dir "C:\Program Files\Tencent\Weixin" --wechat-ocr-dir "%APPDATA%\Tencent\xwechat\xplugin\plugins\WeChatOcr\extracted\..." --input "image.png"
```
如果省略这些参数，CLI 将自动尝试扫描本地标准安装路径以寻找所需的运行库。

## 下载并解压 Release 产物

GitHub Actions CI 流水线会自动构建可执行程序，并将其打包为受密码保护的 `.7z` 压缩包（已加密文件头）。

1. 从 **Releases** 页面下载相应的 `.7z` 归档。
2. 压缩包的加密密码即为该 release 的版本标签（version tag）。例如，如果版本标签是 `260607-ec81bb`，这便是您的解压密码。
3. 使用 7-Zip 解压缩：
   ```powershell
   7z x "wechat-ocr-py-cli-*.7z" -p"您的版本标签"
   ```

## 使用说明

查看帮助及动态打包版本信息：
```powershell
dist\wechat-ocr-py-cli.exe --help
```

### 示例

- **单张图片文件**：
  ```powershell
  dist\wechat-ocr-py-cli.exe --input "C:\path\to\image.png" --output -
  ```

- **从文件列表批量处理（输出 JSONLines 格式）**：
  ```powershell
  dist\wechat-ocr-py-cli.exe --input-list "list.txt" --output "results.jsonl" --workers 4
  ```

- **通过 Stdin 管道流式传输（Cmd/PowerShell）**：
  ```powershell
  cmd.exe /c "echo C:\path\to\image.png | dist\wechat-ocr-py-cli.exe --input-list - --output -"
  ```

## 许可证

本项目自身采用 **Beer-ware 许可证** 授权。详情请参见 [LICENSE](LICENSE) 文件。

*注意：本项目依赖了 [swigger/wechat-ocr](https://github.com/swigger/wechat-ocr)（由于上游可能删除该仓库，我们使用自己的 Fork 版本）C++ 库及微信的原生 dll 组件。请您务必遵守其相应的许可证和使用条款。*
