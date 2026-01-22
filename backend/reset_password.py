import asyncio
import argparse
import sys
import os

# Add the parent directory to sys.path to allow imports from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.future import select
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.core.security import get_password_hash

async def reset_password(email: str, new_password: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        
        if not user:
            print(f"Error: User with email '{email}' not found.")
            return
        
        print(f"User found: {user.email}")
        user.hashed_password = get_password_hash(new_password)
        session.add(user)
        await session.commit()
        print(f"Password for user '{email}' has been successfully reset.")

def main():
    parser = argparse.ArgumentParser(description="Reset a user's password.")
    parser.add_argument("email", help="The email of the user")
    parser.add_argument("password", help="The new password")
    
    args = parser.parse_args()
    
    asyncio.run(reset_password(args.email, args.password))

if __name__ == "__main__":
    main()
