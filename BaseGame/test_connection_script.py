from database_manager import DatabaseManager

# Database configuration - UPDATE PASSWORD!
db = DatabaseManager(
    host='localhost',
    database='zombie_game',
    user='zombie_user',
    password='your_secure_password'  # UPDATE THIS!
)

try:
    db.connect()
    print("✅ Connected successfully!")
    
    db.initialize_schema()
    print("✅ Schema initialized!")
    
    game_id = db.create_game_session(grid_size=20)
    print(f"✅ Created game session: {game_id}")
    
    print("\n🎉 Database setup complete!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
