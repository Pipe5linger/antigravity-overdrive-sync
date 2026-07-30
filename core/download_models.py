import os
import sys
import urllib.request

MODEL_DIR = "D:\\AI\\Models\\LLM"

# Hugging Face GGUF source URLs
DOWNLOAD_LIST = {
    "qwen2.5-coder-14b-instruct-q5_k_m.gguf": "https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct-GGUF/resolve/main/qwen2.5-coder-14b-instruct-q5_k_m.gguf",
    "DeepSeek-R1-Distill-Qwen-14B-Q5_K_M.gguf": "https://huggingface.co/brittlewis12/DeepSeek-R1-Distill-Qwen-14B-GGUF/resolve/main/DeepSeek-R1-Distill-Qwen-14B-Q5_K_M.gguf",
    "magnum-12b-v2-q5_k_m.gguf": "https://huggingface.co/mradermacher/Magnum-12b-v2-GGUF/resolve/main/magnum-12b-v2.Q5_K_M.gguf"
}

def report_progress(block_num, block_size, total_size):
    read_so_far = block_num * block_size
    if total_size > 0:
        percent = (read_so_far * 100) / total_size
        sys.stdout.write(f"\r[+] Downloading: {percent:.1f}% ({read_so_far / (1024**2):.1f} MB of {total_size / (1024**2):.1f} MB)")
        sys.stdout.flush()

def main():
    os.makedirs(MODEL_DIR, exist_ok=True)
    
    for filename, url in DOWNLOAD_LIST.items():
        dest_path = os.path.join(MODEL_DIR, filename)
        if os.path.exists(dest_path):
            print(f"[+] Model already exists, skipping: {filename}")
            continue
            
        print(f"\n[*] Requesting {filename}...")
        try:
            urllib.request.urlretrieve(url, dest_path, reporthook=report_progress)
            print(f"\n[+] Successfully downloaded {filename} to {dest_path}")
        except Exception as e:
            print(f"\n[-] Failed to download {filename}: {e}")
            if os.path.exists(dest_path):
                os.remove(dest_path)

if __name__ == "__main__":
    main()
