# WeChat OCR Python CLI (wechat-ocr-py-cli)

[English](README.en-US.md) | [简体中文](README.md)

A standalone, lightweight, high-performance command line interface (CLI) for running WeChat 4.x OCR parallelized on Windows. It compiles the C++ wrapper engine, packages the required WeChat executable and runtime libraries, and bundles everything into a single zero-dependency executable (`wechat-ocr-py-cli.exe`).

## Features

- **Zero-Dependency Executable**: Everything required (WeChat `Weixin.exe`, `mmmojo_64.dll`, `Weixin.dll`, models, and C++ binding library) is bundled into a single file. No outsider WeChat installations are required at runtime.
- **High-Performance Parallel Processing**: Utilizes a Python `multiprocessing` worker pool for concurrent OCR processing.
- **Multiple Input & Output Modes**:
  - Process a single image via `--input`.
  - Stream a list of image paths dynamically via standard input (stdin pipe) or load them from a text file via `--input-list`.
  - Output results to a file or stdout (in JSONLines format).
- **Robust Path Processing**: Automatic Unicode Byte Order Mark (BOM) stripping (`\ufeff`) from streamed and file-read paths.
- **Informative Help Command**: The `--help` screen dynamically lists the bundled WeChat version, WeChat OCR engine version, and detailed build metadata (such as the compiler, repository references, and Python version).

## Build Setup

### Prerequisites

- Windows OS
- Python 3.11+
- [Git](https://git-scm.com/)
- [7-Zip](https://7-zip.org/) (Ensure `7z` is available on the system `PATH`)
- Visual Studio Build Tools / MSBuild (MSVC compiler is the primary and preferred supported toolchain, MinGW GCC serves as a fallback. Note: LLVM/Clang is currently not supported).

### Compilation & Packaging

1. Install build requirements:
   ```powershell
   pip install -r requirements.txt
   ```

2. Run the automated build script:
   ```powershell
   python build.py
   ```
   *The script will automatically clone the C++ wrapper repo, apply CMake compatibility patches, build the native binaries with MSVC, detect or download WeChat version 4.x runtime, write metadata, and compile the final executable with PyInstaller under `dist/wechat-ocr-py-cli.exe`.*

3. Custom C++ Source Reference (Optional):
   You can specify a custom Git branch, commit hash, or tag to checkout when building the C++ binding by setting the `WECHAT_OCR_CPP_REPO_REF` environment variable (defaults to commit `e32d4af10d8045f8613078bac2df442662c76b03`):
   ```powershell
   $env:WECHAT_OCR_CPP_REPO_REF = "origin/master"
   python build.py
   ```

4. Custom WeChat Target Version (Optional):
   You can specify an exact WeChat version to download and bundle by setting the `WECHAT_VERSION` environment variable (defaults to `4.1.10.27`):
   ```powershell
   $env:WECHAT_VERSION = "4.1.10.27"
   python build.py
   ```

## Non-Standalone Build Mode

To create a drastically smaller executable, you can build the CLI in **Non-Standalone Mode**. In this mode, the CLI will not bundle the heavy WeChat DLLs or models, and will instead dynamically load them at runtime.

### Building
Set the environment variable before running `build.py`:
```powershell
$env:WECHAT_OCR_NON_STANDALONE = "1"
python build.py
```
This produces `dist/wechat-ocr-py-cli-ns.exe`.

### Runtime Usage
When running the non-standalone executable, you can explicitly provide the paths to your local WeChat installation via command-line arguments:

```powershell
dist\wechat-ocr-py-cli-ns.exe --wechat-dir "C:\Program Files\Tencent\Weixin" --wechat-ocr-dir "%APPDATA%\Tencent\xwechat\xplugin\plugins\WeChatOcr\extracted\..." --input "image.png"
```
If these arguments are omitted, the CLI will automatically fallback and attempt to scan the standard local installation paths for the required libraries.

## Downloading & Extracting Releases

The GitHub Actions CI pipeline automatically builds and packages the executable into a password-protected `.7z` archive (with encrypted headers).

1. Download the `.7z` artifact from the **Releases** page.
2. The archive is encrypted using the release version tag as the password. For example, if the release tag is `260607-ec81bb`, that is your password.
3. Extract it using 7-Zip:
   ```powershell
   7z x "wechat-ocr-py-cli-*.7z" -p"YOUR_RELEASE_TAG"
   ```

## Usage

Check help and dynamic bundled versions:
```powershell
dist\wechat-ocr-py-cli.exe --help
```

### Examples

- **Single Image File**:
  ```powershell
  dist\wechat-ocr-py-cli.exe --input "C:\path\to\image.png" --output -
  ```

- **File-based List (JSONLines Output)**:
  ```powershell
  dist\wechat-ocr-py-cli.exe --input-list "list.txt" --output "results.jsonl" --workers 4
  ```

- **Streaming Stdin Pipe (Cmd/PowerShell)**:
  ```powershell
  cmd.exe /c "echo C:\path\to\image.png | dist\wechat-ocr-py-cli.exe --input-list - --output -"
  ```

## License

This project itself is licensed under the **Beer-ware License**. See the [LICENSE](LICENSE) file for details.

*Note: This project relies on the [swigger/wechat-ocr](https://github.com/swigger/wechat-ocr) (we use our fork in case that upstream deletes it) C++ library and WeChat's native dll components. You must also respect their corresponding licenses and terms of usage.*
