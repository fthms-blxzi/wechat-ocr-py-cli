import os
import sys
import time
import json
import argparse
import multiprocessing

# Locate base directory (frozen if packaged by PyInstaller)
if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

# Add bin/ folder to PATH and sys.path for DLL resolution
bin_dir = os.path.join(base_dir, "bin")
if os.path.exists(bin_dir):
    sys.path.append(bin_dir)
    if hasattr(os, 'add_dll_directory'):
        try:
            os.add_dll_directory(bin_dir)
        except Exception:
            pass

# Initialize worker processes
def init_worker(wechat_dir, ocr_exe, dll_dir):
    if hasattr(os, 'add_dll_directory'):
        try:
            os.add_dll_directory(dll_dir)
        except Exception:
            pass
    sys.path.append(dll_dir)
    
    import wcocr
    try:
        wcocr.init(ocr_exe, wechat_dir)
    except Exception as e:
        print(f"Worker {os.getpid()} failed to init wcocr: {e}", file=sys.stderr)

def worker_process_image(task):
    import wcocr
    image_id, img_path = task
    
    if not os.path.exists(img_path):
        return {
            "image_path": img_path,
            "error": "File not found"
        }
        
    start_time = time.time()
    try:
        res = wcocr.ocr(img_path)
        duration = time.time() - start_time
        return {
            "image_path": img_path,
            "duration_seconds": duration,
            "results": res
        }
    except Exception as e:
        return {
            "image_path": img_path,
            "duration_seconds": time.time() - start_time,
            "error": str(e)
        }

def stdin_line_generator():
    image_id = 0
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        path = line.strip().lstrip('\ufeff')
        if path:
            yield (image_id, path)
            image_id += 1

def file_line_generator(filepath):
    image_id = 0
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                path = line.strip().lstrip('\ufeff')
                if path:
                    yield (image_id, path)
                    image_id += 1
    except Exception as e:
        print(f"Failed to read input list file: {e}", file=sys.stderr)

def main():
    multiprocessing.freeze_support()
    
    default_workers = max(1, multiprocessing.cpu_count() - 2)
    
    # Locate WeChat runtime components inside the bundled directory
    wechat_base = os.path.join(bin_dir, "wechat")
    
    # Load metadata versions if available
    metadata_path = os.path.join(wechat_base, "metadata.json")
    wechat_ver = "Unknown"
    ocr_ver = "Unknown"
    build_meta = {}
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                wechat_ver = meta.get("wechat_version", "Unknown")
                ocr_ver = meta.get("wechat_ocr_version", "Unknown")
                build_meta = meta.get("build_metadata", {})
        except Exception:
            pass

    cli_ver = build_meta.get("cli_version", "Unknown")
    cli_url = build_meta.get("cli_repo_url", "Unknown")
    cli_ref = build_meta.get("cli_repo_ref", "Unknown")
    cpp_url = build_meta.get("cpp_repo_url", "Unknown")
    cpp_ref = build_meta.get("cpp_repo_ref", "Unknown")
    py_ver = build_meta.get("python_version", "Unknown")
    cmake_generator = build_meta.get("cmake_generator", build_meta.get("vs_generator", "Unknown"))
    compiler = build_meta.get("compiler_version", "Unknown")
    linker = build_meta.get("linker_version", "Unknown")

    description_text = "Standalone WeChat 4.x OCR Command Line Interface"
    epilog_text = (
        f"Bundled Versions:\n"
        f"  WeChat Version:     {wechat_ver}\n"
        f"  WeChat OCR Version: {ocr_ver}\n\n"
        f"Build Metadata:\n"
        f"  CLI Version:        {cli_ver}\n"
        f"  CLI Repo URL:       {cli_url}\n"
        f"  CLI Repo Ref:       {cli_ref}\n"
        f"  C++ Repo URL:       {cpp_url}\n"
        f"  C++ Repo Ref:       {cpp_ref}\n"
        f"  Python Version:     {py_ver}\n"
        f"  CMake Generator:    {cmake_generator}\n"
        f"  Compiler:           {compiler}\n"
        f"  Linker:             {linker}"
    )
    
    parser = argparse.ArgumentParser(
        description=description_text,
        epilog=epilog_text,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--input", "-i", default=None, metavar="INPUT_IMAGE_FILE_PATH", help="Single image file path to run OCR on")
    parser.add_argument("--input-list", "-l", default="-", metavar="INPUT_LIST_FILE_PATH", help="File containing image paths (one per line), or '-' for stdin streaming (default: '-')")
    parser.add_argument("--output", "-o", default="-", metavar="OUTPUT_FILE_PATH", help="Output JSONLines file path, or '-' for stdout (default: '-')")
    parser.add_argument("--workers", "-w", type=int, default=default_workers, metavar="NUM_WORKERS", help=f"Number of parallel worker processes (default: {default_workers})")
    
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
        
    args = parser.parse_args()
    
    if not os.path.exists(wechat_base):
        print("Error: WeChat runtime folder not found. Please run build.py first.", file=sys.stderr)
        sys.exit(1)
        
    wechat_exe = os.path.join(wechat_base, "Weixin.exe")
    ocr_dll = os.path.join(wechat_base, "ocr", "wxocr.dll")
    
    # Detect the version subdirectory dynamically
    ver_folders = [f for f in os.listdir(wechat_base) if os.path.isdir(os.path.join(wechat_base, f)) and f.startswith("4.1.")]
    if not ver_folders:
        print("Error: WeChat version subfolder not found in runtime directory.", file=sys.stderr)
        sys.exit(1)
        
    wechat_ver_dir = os.path.join(wechat_base, ver_folders[0])
    
    # Setup inputs and generators
    if args.input:
        tasks = [(0, args.input)]
    else:
        if args.input_list == "-":
            tasks = stdin_line_generator()
        else:
            tasks = file_line_generator(args.input_list)
            
    # Setup outputs
    if args.output == "-":
        out_stream = sys.stdout
        if hasattr(out_stream, 'reconfigure'):
            try:
                out_stream.reconfigure(encoding='utf-8')
            except Exception:
                pass
    else:
        try:
            out_stream = open(args.output, "w", encoding="utf-8")
        except Exception as e:
            print(f"Error: Failed to open output file: {e}", file=sys.stderr)
            sys.exit(1)
            
    # Start process pool
    pool = multiprocessing.Pool(
        processes=args.workers,
        initializer=init_worker,
        initargs=(wechat_ver_dir, ocr_dll, bin_dir)
    )
    
    try:
        for result in pool.imap_unordered(worker_process_image, tasks):
            out_stream.write(json.dumps(result, ensure_ascii=False) + "\n")
            out_stream.flush()
    except KeyboardInterrupt:
        pass
    finally:
        pool.terminate()
        pool.join()
        if args.output != "-":
            out_stream.close()

if __name__ == "__main__":
    main()
