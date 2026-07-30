import os
import sys
import urllib.request

MODEL_DIR = "D:\\AI\\Models\\LLM"

# Hugging Face Direct Download URLs (Verified filenames)
DOWNLOAD_LIST = {
    "supergemma4-26b-uncensored-fast-v2-Q4_K_M.gguf": "https://huggingface.co/Jiunsong/supergemma4-26b-uncensored-gguf-v2/resolve/main/supergemma4-26b-uncensored-fast-v2-Q4_K_M.gguf",
    "Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf": "https://huggingface.co/HauhauCS/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive/resolve/main/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf",
    "Huihui-gemma-4-12B-coder-fable5-composer2.5-v1-abliterated-Q5_K_M.gguf": "https://huggingface.co/KakTakOne/Huihui-gemma-4-12B-coder-fable5-composer2.5-v1-abliterated-GGUF/resolve/main/Huihui-gemma-4-12B-coder-fable5-composer2.5-v1-abliterated-Q5_K_M.gguf"
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
