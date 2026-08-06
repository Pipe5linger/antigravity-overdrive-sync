import sqlite3

DB_PATH = r"D:\AI\Projects\antigravity-overdrive-sync\db\sync_state.db"

def inspect_persona():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n================================================================================")
    print("                VESPERA PERSONA PROFILE ANALYSIS")
    print("================================================================================")

    # 1. Total traits count
    cursor.execute("SELECT COUNT(*), SUM(frequency) FROM persona_profile")
    total_traits, total_occurrences = cursor.fetchone()
    print(f"[*] Total Unique Traits: {total_traits}")
    print(f"[*] Total Recorded Occurrences: {total_occurrences or 0}\n")

    # 2. Breakdown by category
    print(f"{'CATEGORY':<25} | {'TRAIT COUNT':<12} | {'AVG CONFIDENCE':<14} | {'TOTAL FREQ':<10}")
    print("-" * 70)

    cursor.execute("""
        SELECT category, COUNT(*), AVG(confidence), SUM(frequency)
        FROM persona_profile
        GROUP BY category
        ORDER BY COUNT(*) DESC
    """)
    for category, count, avg_conf, total_freq in cursor.fetchall():
        print(f"{category:<25} | {count:<12} | {avg_conf:<14.2f} | {total_freq:<10}")

    # 3. Top 5 Most Frequent Traits
    print("\n--------------------------------------------------------------------------------")
    print("TOP RECURRING TRAITS")
    print("--------------------------------------------------------------------------------")
    cursor.execute("""
        SELECT category, trait, frequency, confidence
        FROM persona_profile
        ORDER BY frequency DESC, confidence DESC
        LIMIT 5
    """)
    for idx, (cat, trait, freq, conf) in enumerate(cursor.fetchall(), 1):
        print(f"{idx}. [{cat}] {trait} (Freq: {freq}, Conf: {conf})")

    print("================================================================================")
    conn.close()

if __name__ == "__main__":
    inspect_persona()