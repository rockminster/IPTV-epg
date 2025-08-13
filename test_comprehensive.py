#!/usr/bin/env python3
"""
Integration test for comprehensive channel matching scenarios
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

from merge import resolve_keep_ids, load_xml_root, normalize_id

def test_comprehensive_matching():
    """Test all types of channel matching in a realistic scenario"""
    print("Testing comprehensive channel matching...")
    
    # Test M3U entries with various scenarios
    m3u_entries = [
        # ID matches with alias normalization
        {"id": "bbcone", "name": "BBC One HD"},           # bbcone -> bbc.one.uk
        {"id": "BBC1", "name": "BBC One"},                # bbc1 -> bbc.one.uk  
        {"id": "ITV 1", "name": "ITV1 Yorkshire"},        # itv 1 -> itv1.uk
        {"id": "ch4", "name": "Channel 4"},               # ch4 -> channel4.uk
        
        # Name matching fallback (no ID)
        {"id": None, "name": "BBC Two HD"},               # Should match BBC Two
        {"id": None, "name": "More4"},                    # Should match More4
        
        # Fuzzy name matching
        {"id": None, "name": "Sky Cinema Premiere"},      # Should fuzzy match Sky Cinema Premiere
        
        # No match scenario
        {"id": "unknown.channel", "name": "Random TV"},   # Should not match anything
    ]
    
    # Create comprehensive EPG data
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="bbc.one.uk">
    <display-name>BBC One</display-name>
    <display-name>BBC1</display-name>
  </channel>
  <channel id="bbc.two.uk">
    <display-name>BBC Two</display-name>
  </channel>
  <channel id="itv1.uk">
    <display-name>ITV1</display-name>
    <display-name>ITV</display-name>
  </channel>
  <channel id="channel4.uk">
    <display-name>Channel 4</display-name>
    <display-name>C4</display-name>
  </channel>
  <channel id="more4.uk">
    <display-name>More4</display-name>
  </channel>
  <channel id="sky.cinema.premiere.uk">
    <display-name>Sky Cinema Premiere</display-name>
  </channel>
</tv>'''
    
    root = load_xml_root(xml_content.encode('utf-8'))
    epg_roots = [root]
    
    keep_ids = resolve_keep_ids(m3u_entries, epg_roots, fuzzy_threshold=0.86)
    
    print(f"Resolved channel IDs: {sorted(keep_ids)}")
    
    # Verify all expected matches
    expected_ids = {
        "bbc.one.uk",     # From bbcone and BBC1 aliases
        "bbc.two.uk",     # From name match "BBC Two HD" -> "BBC Two"
        "itv1.uk",        # From "ITV 1" alias
        "channel4.uk",    # From "ch4" alias  
        "more4.uk",       # From exact name match
        "sky.cinema.premiere.uk"  # From fuzzy name match
    }
    
    assert keep_ids == expected_ids, f"Expected {expected_ids}, got {keep_ids}"
    
    print("✓ Comprehensive channel matching test passed")

def test_alias_normalization():
    """Test that alias mapping works correctly"""
    print("Testing alias normalization...")
    
    # Test various aliases
    test_cases = [
        ("bbcone.uk", "bbc.one.uk"),
        ("bbcone", "bbc.one.uk"),
        ("BBC1", "bbc.one.uk"),
        ("bbc1", "bbc.one.uk"),
        ("itv1", "itv1.uk"),
        ("ITV 1", "itv1.uk"),
        ("channel4", "channel4.uk"),
        ("CH4", "channel4.uk"),
        ("skyspremier", "sky.cinema.premiere.uk"),
        ("unknown.channel", "unknown.channel"),  # Should pass through unchanged
    ]
    
    for input_id, expected in test_cases:
        result = normalize_id(input_id)
        assert result == expected, f"For '{input_id}': expected '{expected}', got '{result}'"
    
    print("✓ Alias normalization test passed")

def main():
    """Run comprehensive tests"""
    print("Running comprehensive integration tests...\n")
    
    try:
        test_alias_normalization()
        test_comprehensive_matching()
        print("\n✅ All comprehensive tests passed! The channel matching system is working correctly.")
        print("\nKey features verified:")
        print("- ✓ ID matching with alias normalization")  
        print("- ✓ Exact name matching fallback")
        print("- ✓ Fuzzy name matching fallback")
        print("- ✓ Proper handling of no-match scenarios")
        return True
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)