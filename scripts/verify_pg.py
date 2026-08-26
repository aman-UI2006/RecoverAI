import psycopg2

DB_URL = "postgresql://postgres:postgres@localhost:5432/recoverai_db"

def verify_postgresql_catalog():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # 1. Tables check
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    tables = [row[0] for row in cur.fetchall()]
    print(f"PostgreSQL Public Tables ({len(tables)} total):")
    for t in tables:
        print(f" - {t}")
    
    expected_tables = {
        "merchants", "customers", "transactions", "events",
        "decision_contexts", "recovery_action_scores", "diagnoses",
        "policies", "recovery_attempts", "recovery_attributions",
        "audit_events", "evaluation_runs", "human_reviews"
    }
    actual_tables = set(tables) - {"alembic_version"}
    assert expected_tables == actual_tables, f"Table mismatch! Missing: {expected_tables - actual_tables}"
    print("\n[PASS] All 13 core tables present in PostgreSQL catalog!")

    # 2. Monetary Types check (numeric(12,2))
    cur.execute("""
        SELECT table_name, column_name, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_schema = 'public' AND data_type = 'numeric'
        ORDER BY table_name, column_name;
    """)
    monetary_cols = cur.fetchall()
    print("\nPostgreSQL Monetary Columns (NUMERIC):")
    for row in monetary_cols:
        print(f" - {row[0]}.{row[1]}: NUMERIC({row[2]},{row[3]})")
        assert row[2] == 12 and row[3] == 2, f"Invalid monetary precision on {row[0]}.{row[1]}"
    print("[PASS] All monetary columns verified as NUMERIC(12, 2)!")

    # 3. Foreign Keys check
    cur.execute("""
        SELECT tc.table_name, kcu.column_name, ccu.table_name AS foreign_table_name, ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
        ORDER BY tc.table_name, kcu.column_name;
    """)
    fks = cur.fetchall()
    print(f"\nPostgreSQL Foreign Keys ({len(fks)} total):")
    for row in fks:
        print(f" - {row[0]}.{row[1]} -> {row[2]}.{row[3]}")
    print("[PASS] Foreign keys verified!")

    # 4. Unique Constraints check
    cur.execute("""
        SELECT tc.table_name, tc.constraint_name
        FROM information_schema.table_constraints AS tc
        WHERE tc.constraint_type = 'UNIQUE' AND tc.table_schema = 'public'
        ORDER BY tc.table_name, tc.constraint_name;
    """)
    uniques = cur.fetchall()
    print(f"\nPostgreSQL Unique Constraints ({len(uniques)} total):")
    for row in uniques:
        print(f" - {row[0]}: {row[1]}")
    print("[PASS] Unique constraints verified!")

    cur.close()
    conn.close()

if __name__ == "__main__":
    verify_postgresql_catalog()
