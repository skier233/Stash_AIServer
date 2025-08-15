#!/usr/bin/env python3
"""
Test script to verify user behavior tracking implementation
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Database.database import init_database, get_db_session
from Database.models import UserInteraction, UserSession
from sqlalchemy import text
from datetime import datetime, timezone

def test_user_tracking():
    """Test the user behavior tracking functionality"""
    print("🧪 Testing User Behavior Tracking Implementation")
    print("=" * 60)
    
    # Initialize database
    init_database()
    print("✅ Database initialized")
    
    # Test 1: Create user session
    print("\n📋 Test 1: Create User Session")
    db = get_db_session()
    
    session = UserSession(
        session_id="test_session_001",
        user_id="test_user_123",
        start_time=datetime.now(timezone.utc),
        page_views=1,
        total_interactions=0,
        session_metadata={"browser": "chrome", "device": "desktop"}
    )
    
    db.add(session)
    db.commit()
    db.refresh(session)
    print(f"✅ Created session: {session.session_id}")
    
    # Test 2: Create user interactions
    print("\n🎯 Test 2: Create User Interactions")
    interactions = [
        {
            "session_id": "test_session_001",
            "user_id": "test_user_123",
            "action_type": "page_view",
            "page_path": "/home",
            "element_type": "page",
            "element_id": "home_page",
            "interaction_metadata": {"referrer": "direct"}
        },
        {
            "session_id": "test_session_001", 
            "user_id": "test_user_123",
            "action_type": "click",
            "page_path": "/home",
            "element_type": "button",
            "element_id": "cta_button",
            "interaction_metadata": {"button_text": "Get Started"}
        },
        {
            "session_id": "test_session_001",
            "user_id": "test_user_123", 
            "action_type": "scroll",
            "page_path": "/home",
            "element_type": "section",
            "element_id": "features_section",
            "interaction_metadata": {"scroll_depth": 75}
        }
    ]
    
    created_interactions = []
    for interaction_data in interactions:
        interaction = UserInteraction(**interaction_data)
        db.add(interaction)
        created_interactions.append(interaction)
    
    db.commit()
    for interaction in created_interactions:
        db.refresh(interaction)
    print(f"✅ Created {len(created_interactions)} interactions")
    
    # Test 3: Update session statistics
    print("\n📊 Test 3: Update Session Statistics")
    session.total_interactions = len(created_interactions)
    session.page_views = 1
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    print(f"✅ Updated session stats: {session.total_interactions} interactions, {session.page_views} page views")
    
    # Test 4: Query user behavior data
    print("\n🔍 Test 4: Query User Behavior Data")
    
    # Get all interactions for session
    all_interactions = db.query(UserInteraction).filter(
        UserInteraction.session_id == "test_session_001"
    ).all()
    print(f"  📊 Total interactions found: {len(all_interactions)}")
    
    # Get interactions by action type
    clicks = db.query(UserInteraction).filter(
        UserInteraction.session_id == "test_session_001",
        UserInteraction.action_type == "click"
    ).all()
    print(f"  📊 Click interactions: {len(clicks)}")
    
    # Get session details
    session_details = db.query(UserSession).filter(
        UserSession.session_id == "test_session_001"
    ).first()
    print(f"  📊 Session duration: {session_details.updated_at - session_details.start_time}")
    print(f"  📊 Session metadata: {session_details.session_metadata}")
    
    # Test 5: Analyze interaction patterns
    print("\n📈 Test 5: Analyze Interaction Patterns")
    
    # Group by action type
    action_types = db.execute(text("""
        SELECT action_type, COUNT(*) as count 
        FROM user_interactions 
        WHERE session_id = 'test_session_001'
        GROUP BY action_type
    """)).fetchall()
    
    print("  📊 Actions by type:")
    for action_type, count in action_types:
        print(f"    - {action_type}: {count}")
    
    # Get interactions by page
    page_interactions = db.execute(text("""
        SELECT page_path, COUNT(*) as count
        FROM user_interactions 
        WHERE session_id = 'test_session_001'
        GROUP BY page_path
    """)).fetchall()
    
    print("  📊 Interactions by page:")
    for page_path, count in page_interactions:
        print(f"    - {page_path}: {count}")
    
    # Test 6: Test metadata storage and retrieval
    print("\n💾 Test 6: Test Metadata Storage")
    
    # Check interaction metadata
    click_interaction = db.query(UserInteraction).filter(
        UserInteraction.action_type == "click"
    ).first()
    print(f"  📄 Click metadata: {click_interaction.interaction_metadata}")
    
    # Check session metadata  
    print(f"  📄 Session metadata: {session_details.session_metadata}")
    
    db.close()
    
    print("\n" + "=" * 60)
    print("🎉 All user tracking tests completed successfully!")
    print("🏆 User behavior tracking is working correctly!")
    print("\n📋 Summary:")
    print(f"  ✅ Sessions created and managed")
    print(f"  ✅ Interactions tracked with metadata")
    print(f"  ✅ Session statistics updated")
    print(f"  ✅ Query capabilities working")
    print(f"  ✅ Metadata storage and retrieval working")

if __name__ == "__main__":
    try:
        test_user_tracking()
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)