import sys
import http.server
import socketserver
import urllib.request
import urllib.error
import json
import time
import uuid

PORT = 11434
OLLAMA_BACKEND = "http://localhost:11434"
KOBOLD_BACKEND = "http://localhost:5001"
QWEN_SPACE_URL = "https://qwen-qwen2-5-coder-72b-instruct.hf.space"

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def check_backend(self, url):
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as response:
                return response.status == 200
        except Exception:
            return False

    def query_qwen_space(self, prompt, system_prompt=""):
        # Gradio Space API client implementation
        # Connect to HF Space Gradio queue
        session_hash = uuid.uuid4().hex[:10]
        
        # 1. Join queue
        join_url = f"{QWEN_SPACE_URL}/queue/join"
        # Qwen 72b Space uses standard Gradio Chatbot format: [ [user, assistant_response] ]
        # Input format is usually: (prompt, history, system_prompt)
        payload = {
            "data": [prompt, [], system_prompt],
            "fn_index": 0, # Index 0 is typically the submit handler
            "session_hash": session_hash
        }
        
        try:
            req = urllib.request.Request(
                join_url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as res:
                res_data = json.loads(res.read().decode('utf-8'))
                event_id = res_data.get("event_id")
        except Exception as e:
            return f"Error connecting to HF Space: {e}"

        # 2. Poll status queue until complete
        status_url = f"{QWEN_SPACE_URL}/queue/data?session_hash={session_hash}"
        text_result = ""
        
        # Poll up to 45 seconds
        for _ in range(45):
            time.sleep(1)
            try:
                # Gradio uses SSE or basic polling for queue data
                # We can request it with a standard GET
                req = urllib.request.Request(status_url, method="GET")
                with urllib.request.urlopen(req, timeout=10) as res:
                    raw_lines = res.read().decode('utf-8').splitlines()
                    for line in raw_lines:
                        if line.startswith("data: "):
                            data_chunk = json.loads(line[6:])
                            msg = data_chunk.get("msg")
                            if msg == "process_completed":
                                output_data = data_chunk.get("output", {}).get("data", [])
                                # Get output from Gradio chatbot widget
                                if output_data and isinstance(output_data[0], list):
                                    text_result = output_data[0][-1][1]
                                return text_result
                            elif msg == "process_generating":
                                output_data = data_chunk.get("output", {}).get("data", [])
                                if output_data and isinstance(output_data[0], list):
                                    text_result = output_data[0][-1][1]
            except Exception:
                pass
        return text_result if text_result else "HF Space Timeout Error."

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def handle_request(self, method):
        # Determine mode: Default to HF space if environment flag HF_SPACE=true
        use_hf_space = (os.getenv("HF_SPACE", "false").lower() == "true")
        
        if use_hf_space and self.path == "/v1/chat/completions" or self.path == "/api/chat":
            self.handle_hf_space_completions()
            return

        # Fallback to local routing
        is_kobold_active = self.check_backend(f"{KOBOLD_BACKEND}/api/v1/model")
        if is_kobold_active:
            target_host = KOBOLD_BACKEND
            print(f"[+] Proxy: Routing {method} {self.path} -> KoboldCpp (Port 5001)")
        else:
            target_host = OLLAMA_BACKEND
            print(f"[+] Proxy: Routing {method} {self.path} -> Ollama (Port 11434)")

        # Read content if POST
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        # Build downstream request
        downstream_url = f"{target_host}{self.path}"
        
        # Translate endpoints for Kobold if needed
        if is_kobold_active and self.path == "/api/tags":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            dummy_response = {
                "models": [
                    {
                        "name": "qwen3-coder-30b",
                        "model": "qwen3-coder-30b",
                        "details": {"parameter_size": "30B", "quantization_level": "Q4"}
                    }
                ]
            }
            self.wfile.write(json.dumps(dummy_response).encode('utf-8'))
            return

        headers = {k: v for k, v in self.headers.items() if k.lower() != 'host'}
        try:
            req = urllib.request.Request(
                downstream_url,
                data=body,
                headers=headers,
                method=method
            )
            with urllib.request.urlopen(req, timeout=90) as response:
                self.send_response(response.status)
                for k, v in response.getheaders():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(response.read())
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            for k, v in e.headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(e.read())
        except Exception as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(f"Proxy Connection Error: {e}".encode('utf-8'))

    def handle_hf_space_completions(self):
        # Parses OpenAI completions format and translates to Qwen HF Space
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        req_data = json.loads(body.decode('utf-8'))
        
        messages = req_data.get("messages", [])
        system_prompt = ""
        user_prompt = ""
        
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            if role == "system":
                system_prompt = content
            elif role == "user":
                user_prompt = content
                
        print(f"[+] Proxy: Redirecting request to HF Space (Qwen2.5-Coder-72B)...")
        result = self.query_qwen_space(user_prompt, system_prompt)
        
        # Build standard OpenAI response structure
        response_data = {
            "id": f"chatcmpl-{uuid.uuid4().hex[:10]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "qwen2.5-coder-72b",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": result
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": len(user_prompt) // 4,
                "completion_tokens": len(result) // 4,
                "total_tokens": (len(user_prompt) + len(result)) // 4
            }
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode('utf-8'))

def main():
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", PORT), ProxyHandler) as httpd:
            print("="*80)
            print(f"[+] VESPERA SYSTEM PORT PROXY RUNNING ON PORT {PORT}")
            print(f"    Point all tools to http://localhost:{PORT}")
            print(f"    Use environment variable HF_SPACE=true to route to Qwen 72B Space!")
            print("    Press Ctrl+C to terminate.")
            print("="*80)
            httpd.serve_forever()
    except OSError as e:
        print(f"[-] Proxy error: Could not bind to port {PORT}. Is Ollama already running? {e}")
        sys.exit(1)

if __name__ == "__main__":
    import os
    main()
