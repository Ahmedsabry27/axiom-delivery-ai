from app.database.session import engine

try:
    with engine.connect() as conn:
        print("✅ PostgreSQL connected successfully!")

except Exception as e:
    print(e)
