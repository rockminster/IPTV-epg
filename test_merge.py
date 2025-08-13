#!/usr/bin/env python3
"""
Test script to validate merge.py functionality without external dependencies
"""
import os, sys, tempfile, gzip, io
sys.path.insert(0, os.path.dirname(__file__))

from merge import (
    normalize_id, normalize_name, parse_m3u_entries, 
    collect_epg_channels, resolve_keep_ids, load_xml_root
)

def test_normalization():
    """Test ID and name normalization"""
    print("Testing normalization...")
    
    # Test ID normalization with aliases
    assert normalize_id("bbcone") == "bbc.one.uk"
    assert normalize_id("BBC1") == "bbc.one.uk"
    assert normalize_id("ITV1") == "itv1.uk"
    assert normalize_id("unknown.channel") == "unknown.channel"
    assert normalize_id("") is None
    
    # Test name normalization
    assert normalize_name("BBC One HD") == "bbc one"
    assert normalize_name("ITV (Yorkshire)") == "itv"
    assert normalize_name("Channel 4+1") == "channel 4"
    assert normalize_name("Sky & Living HD") == "sky and living"
    assert normalize_name("") == ""
    
    print("✓ Normalization tests passed")

def test_m3u_parsing():
    """Test M3U parsing"""
    print("Testing M3U parsing...")
    
    m3u_content = b'''#EXTM3U
#EXTINF:-1 tvg-id="bbc.one.uk" tvg-name="BBC One",BBC One HD
http://example.com/bbc1
#EXTINF:-1 tvg-id="itv1" tvg-name="ITV1",ITV1 Yorkshire
http://example.com/itv1
#EXTINF:-1,Channel 4
http://example.com/ch4
'''
    
    entries = parse_m3u_entries(m3u_content)
    assert len(entries) == 3
    assert entries[0]["id"] == "bbc.one.uk"
    assert entries[0]["name"] == "BBC One"
    assert entries[1]["id"] == "itv1.uk"  # normalized via alias
    assert entries[1]["name"] == "ITV1"
    assert entries[2]["id"] is None
    assert entries[2]["name"] == "Channel 4"
    
    print("✓ M3U parsing tests passed")

def test_epg_channel_collection():
    """Test EPG channel collection"""
    print("Testing EPG channel collection...")
    
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="bbc.one.uk">
    <display-name>BBC One</display-name>
    <display-name>BBC1</display-name>
  </channel>
  <channel id="itv1.uk">
    <display-name>ITV1</display-name>
    <display-name>ITV Yorkshire</display-name>
  </channel>
</tv>'''
    
    root = load_xml_root(xml_content.encode('utf-8'))
    id_to_names, name_index = collect_epg_channels(root)
    
    assert "bbc.one.uk" in id_to_names
    assert "bbc one" in id_to_names["bbc.one.uk"]
    assert "bbc1" in id_to_names["bbc.one.uk"]
    
    assert "bbc one" in name_index
    assert "bbc.one.uk" in name_index["bbc one"]
    
    print("✓ EPG channel collection tests passed")

def test_channel_resolution():
    """Test channel resolution with fallback matching"""
    print("Testing channel resolution...")
    
    # Create mock M3U entries
    m3u_entries = [
        {"id": "bbc.one.uk", "name": "BBC One HD"},  # ID match
        {"id": None, "name": "ITV1 Yorkshire"},      # Name match
        {"id": None, "name": "BBC Two HD"},          # Fuzzy match for "bbc two"
        {"id": "unknown.id", "name": "Unknown Channel"}  # No match
    ]
    
    # Create mock EPG data
    xml_content = '''<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="bbc.one.uk">
    <display-name>BBC One</display-name>
  </channel>
  <channel id="itv1.uk">
    <display-name>ITV1 Yorkshire</display-name>
  </channel>
  <channel id="bbc.two.uk">
    <display-name>BBC Two</display-name>
  </channel>
</tv>'''
    
    root = load_xml_root(xml_content.encode('utf-8'))
    epg_roots = [root]
    
    keep_ids = resolve_keep_ids(m3u_entries, epg_roots, fuzzy_threshold=0.86)
    
    # Should include: bbc.one.uk (ID match), itv1.uk (exact name), bbc.two.uk (fuzzy name)
    assert "bbc.one.uk" in keep_ids, "ID match failed"
    assert "itv1.uk" in keep_ids, "Exact name match failed"  
    assert "bbc.two.uk" in keep_ids, f"Fuzzy name match failed. Got IDs: {keep_ids}"
    assert len(keep_ids) == 3, f"Expected 3 matches, got {len(keep_ids)}: {keep_ids}"
    
    print("✓ Channel resolution tests passed")

def main():
    """Run all tests"""
    print("Running merge.py functionality tests...\n")
    
    try:
        test_normalization()
        test_m3u_parsing()
        test_epg_channel_collection()
        test_channel_resolution()
        print("\n✅ All tests passed! The merge.py functionality is working correctly.")
        return True
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)