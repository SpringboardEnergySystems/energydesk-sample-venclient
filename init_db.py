#!/usr/bin/env python3
"""
Database initialization and migration script for VEN Server.

This script can be used to:
1. Initialize the database with Alembic
2. Create an initial admin user
3. Run migrations
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

import argparse
from datetime import datetime
from dotenv import load_dotenv

from venserver.datamodel.database import SessionLocal, engine, build_db_url
from venserver.datamodel.models import Base, User, UserRole


def init_database():
    """Initialize database by creating all tables"""
    print(f"Connecting to: {build_db_url()}")
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    print("✓ Database initialized successfully")


def create_admin_user(email: str, first_name: str = None, last_name: str = None):
    """Create an admin user"""
    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"✗ User with email {email} already exists")
            return

        # Create new admin user
        admin_user = User(
            email=email,
            first_name=first_name or "Admin",
            last_name=last_name or "User",
            role=UserRole.ADMIN,
            is_admin=True,
            is_active=True,
            oauth_provider="manual"
        )

        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        print(f"✓ Admin user created successfully:")
        print(f"  Email: {admin_user.email}")
        print(f"  Name: {admin_user.full_name}")
        print(f"  Role: {admin_user.role}")
        print(f"  ID: {admin_user.id}")

    except Exception as e:
        print(f"✗ Error creating admin user: {e}")
        db.rollback()
    finally:
        db.close()


def list_users():
    """List all users in the database"""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        if not users:
            print("No users found in database")
            return

        print(f"\nFound {len(users)} user(s):")
        print("-" * 80)
        for user in users:
            print(f"Email: {user.email}")
            print(f"Name: {user.full_name}")
            print(f"Role: {user.role}")
            print(f"Admin: {user.is_admin}")
            print(f"Active: {user.is_active}")
            print(f"Created: {user.created_at}")
            print("-" * 80)

    finally:
        db.close()


def drop_all_tables():
    """Drop all tables - USE WITH CAUTION"""
    print("WARNING: This will delete all data!")
    confirm = input("Type 'yes' to confirm: ")
    if confirm.lower() == 'yes':
        print("Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        print("✓ All tables dropped")
    else:
        print("Operation cancelled")


def main():
    parser = argparse.ArgumentParser(description="VEN Server Database Management")
    parser.add_argument('command', choices=['init', 'create-admin', 'list-users', 'drop-all'],
                       help='Command to execute')
    parser.add_argument('--email', help='Email for admin user')
    parser.add_argument('--first-name', help='First name for admin user')
    parser.add_argument('--last-name', help='Last name for admin user')

    args = parser.parse_args()

    # Load environment variables
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded environment from: {env_path}")

    if args.command == 'init':
        init_database()
    elif args.command == 'create-admin':
        if not args.email:
            print("Error: --email is required for create-admin command")
            sys.exit(1)
        create_admin_user(args.email, args.first_name, args.last_name)
    elif args.command == 'list-users':
        list_users()
    elif args.command == 'drop-all':
        drop_all_tables()


if __name__ == '__main__':
    main()
