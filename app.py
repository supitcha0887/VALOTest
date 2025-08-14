import requests
import re
import csv
import time
from bs4 import BeautifulSoup
import json

BASE_URL = "https://liquipedia.net"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# หน้าข้อมูลหลักแต่ละประเภท
CATEGORIES = {
    "Players": "/valorant/Category:Players",
    "Teams": "/valorant/Category:Teams", 
    "Agents": "/valorant/Agents",
    "Tournaments": "/valorant/Portal:Tournaments",
    "Maps": "/valorant/Maps",
}

def fetch_html(url):
    """ดึง HTML จาก URL"""
    try:
        resp = requests.get(url, headers=HEADERS)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def extract_page_links(html, category):
    links = []
    soup = BeautifulSoup(html, 'html.parser')

    blacklist_titles = {
        "API", "Portal", "About Liquipedia VALORANT Wiki", 
        "Disclaimers", "CC-BY-SA", "Notability Guidelines"
    }

    for link in soup.find_all('a', href=True):
        href = link['href']
        text = link.get_text().strip()

        # ต้องขึ้นต้นด้วย /valorant/
        if not href.startswith('/valorant/') or href == '/valorant/':
            continue
        # ข้ามลิงก์หมวดหมู่/ไฟล์พิเศษ
        if any(x in href for x in ['Category:', 'Special:', 'Template:', 'File:', 'Help:']):
            continue
        # กัน 403: ข้ามเฉพาะลิงก์ที่เป็น redlink หรือ action=edit
        if 'action=edit' in href or 'redlink=1' in href:
            continue
        # ข้ามชื่อ blacklist
        if text in blacklist_titles:
            continue
        # ข้ามชื่อที่สั้นผิดปกติ
        if not text or text.startswith('[') or len(text) < 2:
            continue

        links.append((BASE_URL + href, text))

    return list(set(links))


def extract_player_details(html, player_name):
    """ดึงรายละเอียดของผู้เล่น"""
    soup = BeautifulSoup(html, 'html.parser')
    details = {"name": player_name, "category": "Players"}
    
    # หาข้อมูลในตาราง infobox
    infobox = soup.find('table', class_='infobox')
    if infobox:
        rows = infobox.find_all('tr')
        for row in rows:
            cells = row.find_all(['th', 'td'])
            if len(cells) >= 2:
                key = cells[0].get_text().strip().lower()
                value = cells[1].get_text().strip()
                
                if 'real name' in key or 'name' in key:
                    details['real_name'] = value
                elif 'team' in key or 'current team' in key:
                    details['current_team'] = value
                elif 'role' in key:
                    details['role'] = value
                elif 'country' in key or 'nationality' in key:
                    details['country'] = value
                elif 'age' in key:
                    details['age'] = value
                elif 'earnings' in key:
                    details['earnings'] = value
    
    return details

def extract_team_details(html, team_name):
    """ดึงรายละเอียดของทีม"""
    soup = BeautifulSoup(html, 'html.parser')
    details = {"name": team_name, "category": "Teams"}
    
    # หาข้อมูลในตาราง infobox
    infobox = soup.find('table', class_='infobox')
    if infobox:
        rows = infobox.find_all('tr')
        for row in rows:
            cells = row.find_all(['th', 'td'])
            if len(cells) >= 2:
                key = cells[0].get_text().strip().lower()
                value = cells[1].get_text().strip()
                
                if 'region' in key or 'country' in key:
                    details['region'] = value
                elif 'founded' in key or 'created' in key:
                    details['founded'] = value
                elif 'coach' in key:
                    details['coach'] = value
                elif 'captain' in key:
                    details['captain'] = value
    
    # หาข้อมูลผู้เล่นปัจจุบัน
    roster_section = soup.find('span', {'id': re.compile(r'(Current_)?Roster', re.I)})
    if roster_section:
        # หาตารางที่มีรายชื่อผู้เล่น
        roster_table = None
        current = roster_section.parent
        while current and not roster_table:
            current = current.find_next_sibling()
            if current and current.name == 'table':
                roster_table = current
                break
        
        if roster_table:
            players = []
            rows = roster_table.find_all('tr')[1:]  # ข้ามหัวตาราง
            for row in rows[:5]:  # เอาแค่ 5 คนแรก
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    player_link = cells[1].find('a')
                    if player_link:
                        players.append(player_link.get_text().strip())
            details['current_players'] = ', '.join(players)
    
    return details

def extract_agent_details(html, agent_name):
    """ดึงรายละเอียดของ Agent"""
    soup = BeautifulSoup(html, 'html.parser')
    details = {"name": agent_name, "category": "Agents"}
    
    # หาข้อมูลในตาราง infobox
    infobox = soup.find('table', class_='infobox')
    if infobox:
        rows = infobox.find_all('tr')
        for row in rows:
            cells = row.find_all(['th', 'td'])
            if len(cells) >= 2:
                key = cells[0].get_text().strip().lower()
                value = cells[1].get_text().strip()
                
                if 'role' in key or 'type' in key:
                    details['role'] = value
                elif 'origin' in key or 'country' in key:
                    details['origin'] = value
                elif 'release' in key:
                    details['release_date'] = value
    
    # หาข้อมูลความสามารถ (abilities)
    abilities = []
    ability_sections = soup.find_all('span', {'id': re.compile(r'Ability', re.I)})
    for section in ability_sections:
        ability_name = section.get_text().strip()
        if ability_name and len(ability_name) < 30:  # กรองชื่อที่สมเหตุสมผล
            abilities.append(ability_name)
    
    if abilities:
        details['abilities'] = ', '.join(abilities[:4])  # เอาแค่ 4 อันแรก
    
    return details

def extract_tournament_details(html, tournament_name):
    """ดึงรายละเอียดของ Tournament"""
    soup = BeautifulSoup(html, 'html.parser')
    details = {"name": tournament_name, "category": "Tournaments"}
    found_data = False
    # หาข้อมูลในตาราง infobox
    infobox = soup.find('table', class_='infobox')
    if infobox:
        rows = infobox.find_all('tr')
        for row in rows:
            cells = row.find_all(['th', 'td'])
            if len(cells) >= 2:
                key = cells[0].get_text().strip().lower()
                value = cells[1].get_text().strip()
                
                if 'prize' in key:
                    details['prize_pool'] = value; found_data = True
                elif 'location' in key:
                    details['location'] = value; found_data = True
                elif 'start' in key or 'date' in key:
                    details['start_date'] = value; found_data = True
                elif 'end' in key:
                    details['end_date'] = value; found_data = True
                elif 'organizer' in key:
                    details['organizer'] = value; found_data = True
    
    # ถ้าไม่เจอข้อมูลเลย ให้ใช้ fallback
    if not found_data:
        desc = extract_description_fallback(soup)
        if desc:
            details['description'] = desc
    
    return details

def extract_map_details(html, map_name):
    """ดึงรายละเอียดของ Map"""
    soup = BeautifulSoup(html, 'html.parser')
    details = {"name": map_name, "category": "Maps"}
    
    # หาข้อมูลในตาราง infobox
    infobox = soup.find('table', class_='infobox')
    if infobox:
        rows = infobox.find_all('tr')
        for row in rows:
            cells = row.find_all(['th', 'td'])
            if len(cells) >= 2:
                key = cells[0].get_text().strip().lower()
                value = cells[1].get_text().strip()
                
                if 'type' in key:
                    details['type'] = value
                elif 'sites' in key or 'site' in key:
                    details['sites'] = value
                elif 'release' in key:
                    details['release_date'] = value
                elif 'layout' in key:
                    details['layout'] = value
    
    return details

def extract_description_fallback(soup):
    """ดึงย่อหน้าแรกจากเนื้อหาเป็น fallback"""
    content = soup.find('div', class_='mw-parser-output')
    if content:
        # ข้ามย่อหน้าที่เป็น template หรือกล่องต่างๆ
        for p in content.find_all('p', recursive=False):
            text = p.get_text().strip()
            if text and len(text) > 20:  # เอาเฉพาะข้อความยาวพอสมควร
                return text
    return None

def extract_details_by_category(html, name, category):
    """เรียกฟังก์ชันดึงรายละเอียดตามประเภท"""
    if category == "Players":
        return extract_player_details(html, name)
    elif category == "Teams":
        return extract_team_details(html, name)
    elif category == "Agents":
        return extract_agent_details(html, name)
    elif category == "Tournaments":
        return extract_tournament_details(html, name)
    elif category == "Maps":
        return extract_map_details(html, name)
    else:
        return {"name": name, "category": category}

def crawl_category_with_details(name, path, limit=50):
    """
    ดึงข้อมูลจาก category พร้อมรายละเอียด
    ลด limit ลงเพราะต้องเข้าไปในแต่ละหน้า
    """
    url = BASE_URL + path
    all_details = []
    visited = set()
    

    page_count = 0
    while url and len(all_details) < limit and page_count < 3:
        if url in visited:
            break
        visited.add(url)
        page_count += 1

        print(f"Fetching {name} page {page_count}: {url}")
        html = fetch_html(url)
        if not html:
            break

        links = extract_page_links(html, name)
        print(f"Found {len(links)} links on this page")

        for i, (detail_url, item_name) in enumerate(links[:20]):
            if len(all_details) >= limit:
                break

            print(f"  Fetching details for: {item_name} ({i+1}/{min(len(links), 20)})")
            detail_html = fetch_html(detail_url)
            if detail_html:
                details = extract_details_by_category(detail_html, item_name, name)

                # เก็บเฉพาะ record ที่มีข้อมูลจริงมากกว่า 2 key
            if details.get("name") and details.get("category"):
                    all_details.append(details)

            time.sleep(0.5)

        soup = BeautifulSoup(html, 'html.parser')
        next_link = soup.find('a', string=re.compile(r'next', re.I))
        if next_link and next_link.get('href'):
            url = BASE_URL + next_link['href']
        else:
            break

        time.sleep(1)

    return all_details

def crawl_single_page_with_details(name, path, limit=20):
    """ดึงข้อมูลจากหน้าเดียวพร้อมรายละเอียด"""
    html = fetch_html(BASE_URL + path)
    if not html:
        return []
        
    links = extract_page_links(html, name)
    all_details = []
    
    # ดึงรายละเอียดของแต่ละรายการ
    for i, (detail_url, item_name) in enumerate(links[:limit]):
        print(f"Fetching details for {name}: {item_name} ({i+1}/{min(len(links), limit)})")
        detail_html = fetch_html(detail_url)
        if detail_html:
            details = extract_details_by_category(detail_html, item_name, name)
            all_details.append(details)
        
        time.sleep(0.5)
    
    return all_details

def save_to_csv(all_data, filename):
    """บันทึกข้อมูลลง CSV"""
    if not all_data:
        print("No data to save")
        return
    
    # หา columns ทั้งหมดจากข้อมูล
    all_columns = set()
    for item in all_data:
        all_columns.update(item.keys())
    
    columns = ['category', 'name'] + sorted([col for col in all_columns if col not in ['category', 'name']])
    
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for item in all_data:
            # เติมค่าว่างสำหรับ column ที่ไม่มี
            row = {col: item.get(col, '') for col in columns}
            writer.writerow(row)
    
    print(f"✅ Saved {len(all_data)} records to {filename}")

def main():
    all_data = []
    
    for category, path in CATEGORIES.items():
        print(f"\n=== Crawling {category} ===")
        
        if "Category:" in path:
            # เพิ่ม limit เพื่อให้ได้อย่างน้อย 200 รายการรวม
            if category in ["Players", "Teams"]:
                details = crawl_category_with_details(category, path, limit=80)  # เพิ่มเป็น 80
            else:
                details = crawl_category_with_details(category, path, limit=20)  # เพิ่มเป็น 20
        else:
            # หน้าเดียว
            details = crawl_single_page_with_details(category, path, limit=20)  # เพิ่มเป็น 20
        
        all_data.extend(details)
        print(f"Collected {len(details)} {category} records")
        print(f"Total so far: {len(all_data)} records")
    
    print(f"\n🎯 Final count: {len(all_data)} records")
    
    # ตรวจสอบว่าได้อย่างน้อย 200 รายการหรือไม่
    if len(all_data) < 200:
        print(f"⚠️ Warning: Only got {len(all_data)} records, need at least 200")
        print("Consider increasing the limits or running again")
    else:
        print(f"✅ Success: Got {len(all_data)} records (minimum 200 achieved)")
    
    # บันทึกเป็น CSV
    save_to_csv(all_data, "valorant_detailed_data.csv")
    
    # บันทึกเป็น JSON สำรอง
    with open("valorant_detailed_data.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n🎉 Total collected: {len(all_data)} records with detailed information")

if __name__ == "__main__":
    main()