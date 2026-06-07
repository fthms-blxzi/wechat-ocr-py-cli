"""Extract build metadata from metadata.json and set GitHub Actions environment variables.

Reads bin/wechat/metadata.json and writes VERSION and ARCHIVE_NAME to $GITHUB_ENV
for use in subsequent workflow steps (7z compression and release upload).
"""

import json
import re
import os
import sys


def detect_toolchain_slug(cmake_generator, compiler_version):
    """Derive a short toolchain slug (e.g. msvc19, mingw-gcc15) from build metadata."""
    cg = cmake_generator.lower()
    comp = compiler_version.lower()

    if "visual studio" in cg or "msvc" in cg or "nmake" in cg or "microsoft" in comp:
        m = re.search(r"Version\s+([0-9]+)", compiler_version)
        return f"msvc{m.group(1)}" if m else "msvc"

    if "mingw" in cg or any(x in comp for x in ["gcc", "g++", "mingw"]):
        m = re.search(r"(\d+)\.\d+\.\d+", compiler_version.strip())
        return f"mingw-gcc{m.group(1)}" if m else "mingw"

    if "clang" in comp:
        m = re.search(r"(\d+)\.\d+\.\d+", compiler_version.strip())
        return f"clang{m.group(1)}" if m else "clang"

    return "unknown"


def main():
    metadata_path = os.path.join("bin", "wechat", "metadata.json")
    if not os.path.exists(metadata_path):
        print(f"Error: {metadata_path} not found.", file=sys.stderr)
        sys.exit(1)

    with open(metadata_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    bm = meta["build_metadata"]

    cli_ver = bm["cli_version"]
    cpp_ref = bm["cpp_repo_ref"][:6]
    wxocr_ver = meta.get("wechat_ocr_version", "Unknown").split()[0]
    py_slug = "py" + "".join(bm["python_version"].split(".")[:2])
    tool_slug = detect_toolchain_slug(
        bm.get("cmake_generator", ""),
        bm.get("compiler_version", "Unknown"),
    )

    archive_name = (
        f"wechat-ocr-py-cli-{cli_ver}-wxocr-{wxocr_ver}"
        f"-wcpp-{cpp_ref}-{py_slug}-{tool_slug}.7z"
    )

    print(f"VERSION={cli_ver}")
    print(f"ARCHIVE_NAME={archive_name}")

    # Write to $GITHUB_ENV if running inside GitHub Actions
    github_env = os.environ.get("GITHUB_ENV")
    if github_env:
        with open(github_env, "a", encoding="utf-8") as f:
            f.write(f"VERSION={cli_ver}\n")
            f.write(f"ARCHIVE_NAME={archive_name}\n")


if __name__ == "__main__":
    main()
