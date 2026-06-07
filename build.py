import os
import sys
import shutil
import subprocess

def log(msg):
    print(f"[BUILD] {msg}")

def clone_cpp_core():
    temp_dir = "wechat-ocr-cpp-temp"
    if os.path.exists(temp_dir):
        log(f"Cleaning existing directory {temp_dir}...")
        try:
            shutil.rmtree(temp_dir)
        except Exception as e:
            # Git files can sometimes be read-only on Windows
            subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", temp_dir])
            
    # Get repository URL from environment variable (with empty/null fallback)
    repo_url = os.environ.get("WECHAT_OCR_CPP_REPO_URL", "").strip()
    if not repo_url:
        repo_url = "https://github.com/fthms-blxzi/wechat-ocr"
        
    log(f"Cloning C++ repository from {repo_url}...")
    subprocess.run(["git", "clone", repo_url, temp_dir], check=True)
    
    # Get checkout ref from environment variable (with empty/null fallback)
    ref = os.environ.get("WECHAT_OCR_CPP_REPO_REF", "").strip()
    if not ref:
        ref = "e32d4af10d8045f8613078bac2df442662c76b03"
    log(f"Checking out target reference: {ref}")
    
    # Handle remote branch reference pattern (e.g. "origin master" -> "origin/master")
    if " " in ref:
        parts = ref.split()
        if len(parts) == 2 and parts[0] == "origin":
            ref = f"origin/{parts[1]}"
            
    # Checkout specific commit/ref
    subprocess.run(["git", "fetch", "--all"], cwd=temp_dir, check=True)
    subprocess.run(["git", "checkout", ref], cwd=temp_dir, check=True)
    
    # Patch CMakeLists.txt to support MinGW GCC compiling alongside MSVC
    cm_path = os.path.join(temp_dir, "CMakeLists.txt")
    log("Patching CMakeLists.txt...")
    with open(cm_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    old_block = """if (WIN32)
	# add _CRT_SECURE_NO_WARNINGS
	add_definitions(-D_CRT_SECURE_NO_WARNINGS -D_SCL_SECURE_NO_WARNINGS -D_UNICODE -DUNICODE -EHsc)
	# find_package(Protobuf REQUIRED)
	link_directories("${CMAKE_CURRENT_SOURCE_DIR}/spt/x64")
	set(Protobuf_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/spt" CACHE INTERNAL "")
	set(Protobuf_LIBRARIES "libprotobuf-lite.lib" CACHE INTERNAL "")"""
    
    new_block = """if (WIN32)
	add_definitions(-D_CRT_SECURE_NO_WARNINGS -D_SCL_SECURE_NO_WARNINGS -D_UNICODE -DUNICODE)
endif()

if (MSVC)
	add_compile_options(/EHsc)
	link_directories("${CMAKE_CURRENT_SOURCE_DIR}/spt/x64")
	set(Protobuf_INCLUDE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/spt" CACHE INTERNAL "")
	set(Protobuf_LIBRARIES "libprotobuf-lite.lib" CACHE INTERNAL "")"""
    
    content = content.replace(old_block, new_block)
    
    content = content.replace(
        "target_compile_options(libprotobuf-lite PRIVATE -fPIC)",
        "if (NOT WIN32)\n\t\ttarget_compile_options(libprotobuf-lite PRIVATE -fPIC)\n\tendif()"
    )
    
    with open(cm_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    # Patch export_names.cmake to use conditional target_link_options for DEF file
    exp_path = os.path.join(temp_dir, "export_names.cmake")
    log("Patching export_names.cmake...")
    with open(exp_path, "r", encoding="utf-8") as f:
        content_exp = f.read()
        
    old_exp = """        # 添加DEF文件到链接器
        set_property(TARGET ${TARGET_NAME} APPEND_STRING PROPERTY LINK_FLAGS " /DEF:\\"${EXPORT_FILE}\\"")
        message(STATUS "为 ${TARGET_NAME} 配置了符号导出 (${SYMBOLS})")"""
        
    new_exp = """        # 添加DEF文件到链接器
        if (MSVC)
            set_property(TARGET ${TARGET_NAME} APPEND_STRING PROPERTY LINK_FLAGS " /DEF:\\"${EXPORT_FILE}\\"")
        else()
            target_link_options(${TARGET_NAME} PRIVATE "${EXPORT_FILE}")
        endif()
        message(STATUS "为 ${TARGET_NAME} 配置了符号导出 (${SYMBOLS})")"""
        
    content_exp = content_exp.replace(old_exp, new_exp)
    with open(exp_path, "w", encoding="utf-8") as f:
        f.write(content_exp)

# Global dictionary to collect compiler and linker version info
build_info = {
    "cmake_generator": "Unknown",
    "compiler_version": "Unknown",
    "linker_version": "Unknown"
}

def extract_toolchain_versions(build_dir):
    compiler_path = None
    linker_path = None
    cache_path = os.path.join(build_dir, "CMakeCache.txt")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if line.startswith("CMAKE_CXX_COMPILER:FILEPATH="):
                        compiler_path = line.split("=", 1)[1].strip()
                    elif line.startswith("CMAKE_LINKER:FILEPATH="):
                        linker_path = line.split("=", 1)[1].strip()
        except Exception as e:
            log(f"Failed to read CMakeCache.txt: {e}")
            
    # Fallback to scanning CMakeFiles for compiler configuration if cache didn't have it (e.g. Visual Studio generators)
    if not compiler_path or not linker_path:
        cmake_files_dir = os.path.join(build_dir, "CMakeFiles")
        if os.path.exists(cmake_files_dir):
            for root, dirs, files in os.walk(cmake_files_dir):
                if "CMakeCXXCompiler.cmake" in files:
                    compiler_info_path = os.path.join(root, "CMakeCXXCompiler.cmake")
                    try:
                        with open(compiler_info_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                            import re
                            m_comp = re.search(r'set\(CMAKE_CXX_COMPILER "(.*?)"\)', content)
                            if m_comp:
                                compiler_path = m_comp.group(1)
                            m_link = re.search(r'set\(CMAKE_LINKER "(.*?)"\)', content)
                            if m_link:
                                linker_path = m_link.group(1)
                    except Exception as e:
                        log(f"Failed to read CMakeCXXCompiler.cmake: {e}")
                    
    compiler_ver = "Unknown"
    linker_ver = "Unknown"
    
    if compiler_path:
        try:
            if "cl.exe" in compiler_path.lower():
                res = subprocess.run([compiler_path], capture_output=True, text=True, errors="ignore")
                # cl.exe outputs version description on stderr, look for lines containing version/Microsoft
                lines = (res.stdout + res.stderr).splitlines()
                for line in lines:
                    if "compiler version" in line.lower() or "optimizing compiler" in line.lower():
                        compiler_ver = line.strip()
                        break
                if compiler_ver == "Unknown" and lines:
                    compiler_ver = lines[0].strip()
            else:
                res = subprocess.run([compiler_path, "--version"], capture_output=True, text=True, errors="ignore")
                lines = (res.stdout + res.stderr).splitlines()
                if lines:
                    compiler_ver = lines[0].strip()
        except Exception as e:
            log(f"Failed to read compiler version from {compiler_path}: {e}")
            
    if linker_path:
        try:
            if "link.exe" in linker_path.lower():
                res = subprocess.run([linker_path], capture_output=True, text=True, errors="ignore")
                lines = (res.stdout + res.stderr).splitlines()
                for line in lines:
                    if "linker version" in line.lower() or "incremental linker" in line.lower():
                        linker_ver = line.strip()
                        break
                if linker_ver == "Unknown" and lines:
                    linker_ver = lines[0].strip()
            else:
                res = subprocess.run([linker_path, "--version"], capture_output=True, text=True, errors="ignore")
                lines = (res.stdout + res.stderr).splitlines()
                if lines:
                    linker_ver = lines[0].strip()
        except Exception as e:
            log(f"Failed to read linker version from {linker_path}: {e}")
            
    build_info["compiler_version"] = compiler_ver
    build_info["linker_version"] = linker_ver

def build_cpp_core():
    temp_dir = os.path.abspath("wechat-ocr-cpp-temp")
    os.makedirs("bin", exist_ok=True)
    
    cmake_generator = os.environ.get("WECHAT_OCR_CMAKE_GENERATOR", "").strip()
    if not cmake_generator:
        cmake_generator = "Visual Studio 17 2022"
    build_info["cmake_generator"] = cmake_generator
        
    user_configured = bool(os.environ.get("WECHAT_OCR_CMAKE_GENERATOR", "").strip())
    
    log(f"Attempting C++ core configuration with generator: {cmake_generator}...")
    build_dir = os.path.abspath(os.path.join(temp_dir, "build_configured"))
    
    cmake_cmd = ["cmake", "-G", cmake_generator, "-B", build_dir]
    if cmake_generator.startswith("Visual Studio"):
        cmake_cmd += ["-A", "x64"]
        
    res = subprocess.run(cmake_cmd, cwd=temp_dir)
    
    if res.returncode == 0:
        log(f"Generator {cmake_generator} configured successfully. Building in Release...")
        subprocess.run([
            "cmake", "--build", build_dir, "--config", "Release"
        ], cwd=temp_dir, check=True)
        
        # Check if they are in build_dir/Release first, then fall back to build_dir
        release_dir = os.path.join(build_dir, "Release")
        search_dir = release_dir if os.path.exists(release_dir) else build_dir
        
        pyd_files = [f for f in os.listdir(search_dir) if f.endswith(".pyd") or (f.startswith("wcocr.") and f.endswith(".so"))]
        if not pyd_files:
            raise Exception("wcocr.pyd was not generated.")
        shutil.copy2(os.path.join(search_dir, pyd_files[0]), "bin/wcocr.pyd")
        
        dll_name = "wcocr.dll" if os.path.exists(os.path.join(search_dir, "wcocr.dll")) else "libwcocr.dll"
        shutil.copy2(os.path.join(search_dir, dll_name), "bin/wcocr.dll")
        
        extract_toolchain_versions(build_dir)
        log("Successfully compiled C++ core.")
    else:
        if user_configured:
            raise Exception(f"Configured generator {cmake_generator} failed to configure CMake.")
            
        log("MSVC compilation environment not found. Falling back to default generator...")
        build_dir = os.path.abspath(os.path.join(temp_dir, "build"))
        
        subprocess.run([
            "cmake", "-DCMAKE_BUILD_TYPE=Release", "-B", build_dir
        ], cwd=temp_dir, check=True)
        
        # Detect the actual generator CMake chose from the cache
        fallback_generator = "Unknown"
        cache_path = os.path.join(build_dir, "CMakeCache.txt")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith("CMAKE_GENERATOR:INTERNAL="):
                            fallback_generator = line.split("=", 1)[1].strip()
                            break
            except Exception:
                pass
        build_info["cmake_generator"] = fallback_generator
        log(f"Detected default generator: {fallback_generator}")
        subprocess.run([
            "cmake", "--build", build_dir, "--config", "Release"
        ], cwd=temp_dir, check=True)
        
        # Detect if it built into a 'Release' subdirectory (default MSVC generator behavior)
        release_dir = os.path.join(build_dir, "Release")
        search_dir = release_dir if os.path.exists(release_dir) else build_dir
        
        pyd_files = [f for f in os.listdir(search_dir) if f.endswith(".pyd") or (f.startswith("wcocr.") and f.endswith(".so"))]
        if not pyd_files:
            raise Exception("wcocr.pyd was not generated in build folder.")
        shutil.copy2(os.path.join(search_dir, pyd_files[0]), "bin/wcocr.pyd")
        
        dll_name = "wcocr.dll" if os.path.exists(os.path.join(search_dir, "wcocr.dll")) else "libwcocr.dll"
        shutil.copy2(os.path.join(search_dir, dll_name), "bin/wcocr.dll")
        
        extract_toolchain_versions(build_dir)
        log("Successfully compiled with default generator.")


def get_wechat_runtime():
    dest_dir = "bin/wechat"
    if os.path.exists(dest_dir):
        log("WeChat runtime already present in bin/wechat. Skipping detection/download.")
        return
        
    os.makedirs(dest_dir, exist_ok=True)
    
    # Try searching the local system first
    weixin_exe = r"C:\Program Files\Tencent\Weixin\Weixin.exe"
    xplugin_dir = os.path.expandvars(r"%APPDATA%\Tencent\xwechat\xplugin\plugins\WeChatOcr")
    
    target_wechat_ver = os.environ.get("WECHAT_VERSION", "").strip()
    
    local_found = False
    if os.path.exists(weixin_exe) and os.path.exists(xplugin_dir):
        log("Local WeChat installation detected. Copying runtime components...")
        weixin_parent = os.path.dirname(weixin_exe)
        
        if target_wechat_ver:
            ver_folders = [f for f in os.listdir(weixin_parent) if os.path.isdir(os.path.join(weixin_parent, f)) and f == target_wechat_ver]
        else:
            ver_folders = [f for f in os.listdir(weixin_parent) if os.path.isdir(os.path.join(weixin_parent, f)) and f.startswith("4.1.")]
        
        ocr_dlls = []
        for root, dirs, files in os.walk(xplugin_dir):
            if "wxocr.dll" in files and "extracted" in root:
                ocr_dlls.append(os.path.join(root, "wxocr.dll"))
                
        if ver_folders and ocr_dlls:
            best_ver = ver_folders[-1]
            best_ver_path = os.path.join(weixin_parent, best_ver)
            best_ocr_dll = ocr_dlls[-1]
            best_ocr_dir = os.path.dirname(best_ocr_dll)
            
            log(f"Found version folder: {best_ver}, OCR DLL directory: {best_ocr_dir}")
            shutil.copy2(weixin_exe, os.path.join(dest_dir, "Weixin.exe"))
            
            dest_ver_dir = os.path.join(dest_dir, best_ver)
            os.makedirs(dest_ver_dir, exist_ok=True)
            shutil.copy2(os.path.join(best_ver_path, "mmmojo_64.dll"), os.path.join(dest_ver_dir, "mmmojo_64.dll"))
            shutil.copy2(os.path.join(best_ver_path, "Weixin.dll"), os.path.join(dest_ver_dir, "Weixin.dll"))
            
            dest_ocr_dir = os.path.join(dest_dir, "ocr")
            os.makedirs(dest_ocr_dir, exist_ok=True)
            for f in os.listdir(best_ocr_dir):
                # Skip the raw bin/zipped plugin packages (WeChatOcr.bin)
                if not f.endswith(".bin") and os.path.isfile(os.path.join(best_ocr_dir, f)):
                    shutil.copy2(os.path.join(best_ocr_dir, f), os.path.join(dest_ocr_dir, f))
            
            local_found = True
            log("Local WeChat runtime files copied successfully.")
            
    if not local_found:
        log("Local WeChat 4.x runtime not found. Querying GitHub to download version...")
        download_wechat_runtime(dest_dir)

def extract_installer(temp_exe, temp_extract):
    if os.path.exists(temp_extract):
        try:
            shutil.rmtree(temp_extract)
        except Exception:
            subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", temp_extract])
    os.makedirs(temp_extract)
    
    subprocess.run(["7z", "x", temp_exe, f"-o{temp_extract}", "-y"], check=True)
    
    # Check for any inner .7z archives (like install.7z) and extract them
    inner_7z = None
    for root, dirs, files in os.walk(temp_extract):
        for f in files:
            if f.endswith(".7z"):
                inner_7z = os.path.join(root, f)
                break
        if inner_7z:
            break
            
    if inner_7z:
        log(f"Found inner archive {inner_7z}. Extracting inner files...")
        temp_extract_inner = os.path.join(temp_extract, "inner_extracted")
        subprocess.run(["7z", "x", inner_7z, f"-o{temp_extract_inner}", "-y"], check=True)

def download_wechat_runtime(dest_dir):
    import requests
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    api_url = "https://api.github.com/repos/cscnk52/wechat-windows-versions/releases"
    
    target_wechat_ver = os.environ.get("WECHAT_VERSION", "").strip()
    
    if target_wechat_ver:
        fallback_ver = f"v{target_wechat_ver}"
        fallback_url = f"https://github.com/cscnk52/wechat-windows-versions/releases/download/v{target_wechat_ver}/weixin_{target_wechat_ver}.exe"
    else:
        fallback_ver = "v4.1.10.27"
        fallback_url = "https://github.com/cscnk52/wechat-windows-versions/releases/download/v4.1.10.27/weixin_4.1.10.27.exe"
        
    download_url = None
    version_str = None
    
    try:
        log("Fetching releases from cscnk52/wechat-windows-versions...")
        resp = requests.get(api_url, headers=headers, timeout=15)
        if resp.status_code == 200:
            releases = resp.json()
            for release in releases:
                tag = release.get("tag_name", "")
                if target_wechat_ver:
                    if tag != f"v{target_wechat_ver}":
                        continue
                elif not tag.startswith("v4."):
                    continue
                    
                for asset in release.get("assets", []):
                    name = asset.get("name", "")
                    if name.startswith("weixin_") and name.endswith(".exe"):
                        download_url = asset.get("browser_download_url")
                        version_str = tag.lstrip("v")
                        break
                if download_url:
                    break
    except Exception as e:
        log(f"GitHub API query encountered an error: {e}")
        
    if not download_url:
        log(f"Unable to find dynamic download. Falling back to WeChat {fallback_ver}...")
        download_url = fallback_url
        version_str = fallback_ver.lstrip("v")
        
    temp_exe = "temp_weixin.exe"
    log(f"Downloading WeChat installer from {download_url}...")
    with requests.get(download_url, headers=headers, stream=True) as r:
        r.raise_for_status()
        with open(temp_exe, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                
    log("Download completed. Extracting installer contents using 7z...")
    temp_extract = "temp_extract_weixin"
    extract_installer(temp_exe, temp_extract)
    
    # Scan the extracted directories to locate Weixin.exe, Weixin.dll, mmmojo_64.dll and WeChatOcr.bin
    extracted_weixin_exe = None
    extracted_version = None
    extracted_weixin_dll = None
    extracted_mmmojo_dll = None
    extracted_ocr_bin = None
    
    for root, dirs, files in os.walk(temp_extract):
        for f in files:
            lf = f.lower()
            if lf == "weixin.exe":
                extracted_weixin_exe = os.path.join(root, f)
            elif lf == "weixin.dll":
                extracted_weixin_dll = os.path.join(root, f)
                extracted_version = os.path.basename(root)
            elif lf == "mmmojo_64.dll":
                extracted_mmmojo_dll = os.path.join(root, f)
            elif lf == "wechatocr.bin":
                extracted_ocr_bin = os.path.join(root, f)
                
    # If the layout is unsupported, clean and redownload the tested fallback version specifically
    if not (extracted_weixin_exe and extracted_weixin_dll and extracted_mmmojo_dll and extracted_ocr_bin):
        log("Extracted layout unrecognized. Retrying with fallback version v4.1.10.27...")
        if download_url != fallback_url:
            shutil.rmtree(temp_extract)
            if os.path.exists(temp_exe): os.remove(temp_exe)
            log(f"Downloading fallback from {fallback_url}...")
            with requests.get(fallback_url, headers=headers, stream=True) as r:
                r.raise_for_status()
                with open(temp_exe, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            extract_installer(temp_exe, temp_extract)
            for root, dirs, files in os.walk(temp_extract):
                for f in files:
                    lf = f.lower()
                    if lf == "weixin.exe":
                        extracted_weixin_exe = os.path.join(root, f)
                    elif lf == "weixin.dll":
                        extracted_weixin_dll = os.path.join(root, f)
                        extracted_version = os.path.basename(root)
                    elif lf == "mmmojo_64.dll":
                        extracted_mmmojo_dll = os.path.join(root, f)
                    elif lf == "wechatocr.bin":
                        extracted_ocr_bin = os.path.join(root, f)
                        
    if not (extracted_weixin_exe and extracted_weixin_dll and extracted_mmmojo_dll and extracted_ocr_bin):
        raise Exception("Failed to locate required files in downloaded WeChat package.")
        
    log(f"Extracted components. Version discovered: {extracted_version}")
    shutil.copy2(extracted_weixin_exe, os.path.join(dest_dir, "Weixin.exe"))
    
    dest_ver_dir = os.path.join(dest_dir, extracted_version)
    os.makedirs(dest_ver_dir, exist_ok=True)
    shutil.copy2(extracted_weixin_dll, os.path.join(dest_ver_dir, "Weixin.dll"))
    shutil.copy2(extracted_mmmojo_dll, os.path.join(dest_ver_dir, "mmmojo_64.dll"))
    
    dest_ocr_dir = os.path.join(dest_dir, "ocr")
    if os.path.exists(dest_ocr_dir):
        shutil.rmtree(dest_ocr_dir)
    os.makedirs(dest_ocr_dir)
    
    # Extract WeChatOcr.bin (it is a ZIP file containing the ocr dll and models)
    log("Extracting WeChatOcr.bin plugin package...")
    subprocess.run(["7z", "x", extracted_ocr_bin, f"-o{dest_ocr_dir}", "-y"], check=True)
    
    # Clean any unneeded .bin file from extracted plugin folder
    for f in os.listdir(dest_ocr_dir):
        if f.endswith(".bin"):
            os.remove(os.path.join(dest_ocr_dir, f))
            
    # Cleanup temp resources
    shutil.rmtree(temp_extract)
    if os.path.exists(temp_exe):
        os.remove(temp_exe)
    log("WeChat 4.x runtime successfully downloaded and extracted.")
def save_metadata(dest_dir):
    log("Generating metadata.json for the built artifact...")
    import json
    import re
    import ctypes
    
    weixin_exe = os.path.join(dest_dir, "Weixin.exe")
    wechat_ver = "Unknown"
    if os.path.exists(weixin_exe):
        try:
            size = ctypes.windll.version.GetFileVersionInfoSizeW(weixin_exe, None)
            if size:
                res = ctypes.create_string_buffer(size)
                if ctypes.windll.version.GetFileVersionInfoW(weixin_exe, 0, size, res):
                    fixed = ctypes.c_void_p()
                    flen = ctypes.c_uint()
                    if ctypes.windll.version.VerQueryValueW(res, "\\", ctypes.byref(fixed), ctypes.byref(flen)):
                        dwMS = ctypes.cast(fixed, ctypes.POINTER(ctypes.c_uint32))[2]
                        dwLS = ctypes.cast(fixed, ctypes.POINTER(ctypes.c_uint32))[3]
                        wechat_ver = f"{dwMS >> 16}.{dwMS & 0xffff}.{dwLS >> 16}.{dwLS & 0xffff}"
        except Exception as e:
            log(f"Error reading WeChat version: {e}")

    ocr_ver = "Unknown"
    ocr_dll_ver = "Unknown"
    ocr_dir = os.path.join(dest_dir, "ocr")
    xml_path = os.path.join(ocr_dir, "file_component.xml")
    if os.path.exists(xml_path):
        try:
            with open(xml_path, "r", encoding="utf-8") as f:
                xml_content = f.read()
            m = re.search(r'version="(\d+)"', xml_content)
            if m:
                ocr_ver = m.group(1)
        except Exception as e:
            log(f"Error reading file_component.xml: {e}")
            
    wxocr_dll = os.path.join(ocr_dir, "wxocr.dll")
    if os.path.exists(wxocr_dll):
        try:
            size = ctypes.windll.version.GetFileVersionInfoSizeW(wxocr_dll, None)
            if size:
                res = ctypes.create_string_buffer(size)
                if ctypes.windll.version.GetFileVersionInfoW(wxocr_dll, 0, size, res):
                    fixed = ctypes.c_void_p()
                    flen = ctypes.c_uint()
                    if ctypes.windll.version.VerQueryValueW(res, "\\", ctypes.byref(fixed), ctypes.byref(flen)):
                        dwMS = ctypes.cast(fixed, ctypes.POINTER(ctypes.c_uint32))[2]
                        dwLS = ctypes.cast(fixed, ctypes.POINTER(ctypes.c_uint32))[3]
                        ocr_dll_ver = f"{dwMS >> 16}.{dwMS & 0xffff}.{dwLS >> 16}.{dwLS & 0xffff}"
        except Exception as e:
            log(f"Error reading WeChat OCR DLL version: {e}")

    combined_ocr_ver = ocr_ver
    if ocr_dll_ver != "Unknown":
        if combined_ocr_ver != "Unknown":
            combined_ocr_ver = f"{combined_ocr_ver} (DLL: {ocr_dll_ver})"
        else:
            combined_ocr_ver = f"DLL: {ocr_dll_ver}"

    cli_version = "Unknown"
    cli_repo_url = "Unknown"
    cli_repo_ref = "Unknown"
    try:
        res_url = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True)
        if res_url.returncode == 0:
            cli_repo_url = res_url.stdout.strip()
    except Exception:
        pass
        
    try:
        res_ref = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
        if res_ref.returncode == 0:
            cli_repo_ref = res_ref.stdout.strip()
    except Exception:
        pass

    try:
        res_time = subprocess.run(["git", "show", "-s", "--format=%ct", "HEAD"], capture_output=True, text=True)
        res_sha = subprocess.run(["git", "rev-parse", "--short=6", "HEAD"], capture_output=True, text=True)
        if res_time.returncode == 0 and res_sha.returncode == 0:
            import datetime
            ts = int(res_time.stdout.strip())
            commit_utc = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            date_str = commit_utc.strftime("%y%m%d")
            cli_version = f"{date_str}-{res_sha.stdout.strip()}"
    except Exception as e:
        log(f"Failed to calculate git version tag: {e}")

    cpp_repo_url = os.environ.get("WECHAT_OCR_CPP_REPO_URL", "").strip()
    if not cpp_repo_url:
        cpp_repo_url = "https://github.com/fthms-blxzi/wechat-ocr"
        
    cpp_repo_ref = os.environ.get("WECHAT_OCR_CPP_REPO_REF", "").strip()
    if not cpp_repo_ref:
        cpp_repo_ref = "e32d4af10d8045f8613078bac2df442662c76b03"

    python_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    metadata = {
        "wechat_version": wechat_ver,
        "wechat_ocr_version": combined_ocr_ver,
        "build_metadata": {
            "cli_version": cli_version,
            "cli_repo_url": cli_repo_url,
            "cli_repo_ref": cli_repo_ref,
            "cpp_repo_url": cpp_repo_url,
            "cpp_repo_ref": cpp_repo_ref,
            "python_version": python_ver,
            "cmake_generator": build_info.get("cmake_generator", "Unknown"),
            "compiler_version": build_info.get("compiler_version", "Unknown"),
            "linker_version": build_info.get("linker_version", "Unknown")
        }
    }
    
    meta_path = os.path.join(dest_dir, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
    log(f"Saved metadata: {metadata}")

def package_standalone_exe():
    log("Running PyInstaller to compile standalone executable...")
    import PyInstaller.__main__
    PyInstaller.__main__.run([
        "--onefile",
        "--add-data", "bin;bin",
        "--name", "wechat-ocr-py-cli",
        "wechat_ocr_cli.py"
    ])
    log("PyInstaller compilation complete. Output executable is at dist/wechat-ocr-py-cli.exe")

def main():
    log("Starting build orchestration...")
    clone_cpp_core()
    build_cpp_core()
    get_wechat_runtime()
    save_metadata("bin/wechat")
    package_standalone_exe()
    
    # Cleanup temporary C++ build folder
    temp_dir = "wechat-ocr-cpp-temp"
    if os.path.exists(temp_dir):
        log("Cleaning up temporary build files...")
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", temp_dir])
    log("Build fully completed!")

if __name__ == "__main__":
    main()
