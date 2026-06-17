import chromadb

# 1. Connect to the database
db_path = r"E:\_Sanctuary_Backups\Scripts" 
client = chromadb.PersistentClient(path=db_path)
collection = client.get_collection(name="system_memory")

# 2. Fetch the latest 10 records
results = collection.peek(limit=10)

print("\n=== SYSTEM MEMORY: STORED FACTS ===\n")

if "documents" in results and results["documents"]:
    for i, (doc, meta) in enumerate(zip(results["documents"], results["metadatas"])):
        print(f"--- Record {i + 1} ---")
        if meta:
            category = meta.get("category", "Unknown")
            source = meta.get("source", "Unknown")
            print(f"Category: {category} | Source: {source}")
        
        print(f"Fact Data:\n{doc}\n")
else:
    print("[!] Database connected and collection exists, but it is completely empty.")