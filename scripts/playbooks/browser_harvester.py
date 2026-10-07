import os
import asyncio
import sqlite3
import json
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'db', 'sync_state.db'))

async def main():
    print("[*] Starting ULM Browser Chat Harvester via MCP...")
    
    # Connect to local SQLite DB to track ingested docs
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS harvested_docs (
            doc_id TEXT PRIMARY KEY,
            doc_name TEXT,
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            content TEXT,
            source TEXT,
            relevance_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    
    # Set up MCP client
    # Note: This requires Node.js to be installed.
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-google-workspace"],
    )
    
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("[*] Connected to Google Workspace MCP Server.")
                
                print("[*] Searching Drive for Gemini exported chats in ULM_Browser_Exports...")
                # We can search by name or folder, but we'll just pull recent docs and filter
                result = await session.call_tool("drive_search", {"query": "mimeType='application/vnd.google-apps.document'"})
                
                files_json = result.content[0].text
                try:
                    docs = json.loads(files_json)
                except Exception as e:
                    print(f"[!] Failed to parse drive_search result: {e}")
                    return
                    
                print(f"[*] Found {len(docs)} documents. Checking for uningested chats...")
                
                ingested_count = 0
                for doc in docs:
                    doc_id = doc.get("id")
                    doc_name = doc.get("name")
                    
                    # Check if already ingested
                    cursor.execute('SELECT 1 FROM harvested_docs WHERE doc_id = ?', (doc_id,))
                    if cursor.fetchone():
                        continue
                        
                    print(f"  [>] Inspecting: {doc_name} ({doc_id})")
                    
                    try:
                        # Read the doc text
                        text_result = await session.call_tool("docs_read_text", {"document_id": doc_id})
                        text = text_result.content[0].text
                        
                        if "User prompt:" in text and "Response:" in text:
                            print(f"      [+] Identified as Gemini Chat. Ingesting...")
                            
                            # In a full pipeline, you'd route this through the DynamicPromptAssembler or Ollama
                            # for semantic extraction. Here we inject the raw summary block as a fact.
                            snippet = text[:1500] + "\n...[truncated]"
                            cursor.execute('INSERT INTO facts (category, content, source, relevance_score) VALUES (?, ?, ?, ?)', 
                                         ("browser_chat", f"Transcript Snippet [{doc_name}]:\n{snippet}", doc_name, 0.8))
                            
                            cursor.execute('INSERT INTO harvested_docs (doc_id, doc_name) VALUES (?, ?)', (doc_id, doc_name))
                            conn.commit()
                            ingested_count += 1
                        else:
                            print(f"      [-] Skipping (Not a recognized chat format).")
                            
                    except Exception as e:
                        print(f"      [!] Failed to read doc {doc_id}: {e}")
                        
                print(f"\n[*] Harvest complete. {ingested_count} new chats ingested into ULM.")
    except Exception as e:
        print(f"[!] Critical Error running MCP Client: {e}")

if __name__ == "__main__":
    asyncio.run(main())
