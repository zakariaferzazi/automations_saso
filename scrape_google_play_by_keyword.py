# -*- coding: utf-8 -*-
import csv
import os
import re
import time
from collections import Counter
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ===========================
# CONFIGURATION - EDIT HERE
# ===========================
CONFIG = {
    # List of individual keywords to search for apps
    'TARGET_KEYWORDS': [
    "Subtitle Editor Pro",
    "Subtitle Sync Tool",
    "SRT Editor & Fixer",
    "PDF Metadata Editor",
    "PDF Info Cleaner",
    "PDF Tag Editor",
    "Image Metadata Cleaner",
    "EXIF Remover Pro",
    "Photo Privacy Cleaner",
    "Bulk File Renamer",
    "Smart File Renamer",
    "Batch Rename Tool",
    "Audio Silence Remover",
    "Audio Trim & Clean",
    "Voice Cleaner Pro",
    "Audio Volume Normalizer",
    "Sound Level Fixer",
    "MP3 Volume Booster",
    "Voice to Text Batch",
    "Audio Transcriber Pro",
    "Speech to Text Files",
    "Folder Organizer Pro",
    "Smart Storage Cleaner",
    "Duplicate File Finder",
    "Smart Duplicate Cleaner",
    "Video Metadata Editor",
    "Video Tag Editor",
    "Video Info Fixer",
    "Playlist Organizer Pro",
    "Music Playlist Cleaner",
    "Playlist Sort Tool",
    "Document Format Fixer",
    "File Format Repair Tool",
    "Corrupted File Fixer",
    "ZIP File Inspector",
    "Archive Viewer Pro",
    "Zip Preview Tool",
    "Unit Price Calculator",
    "Best Deal Calculator",
    "Price Per Unit Tool",
    "Smart Alarm Clock Pro",
    "Sleep Cycle Alarm",
    "Smart Wake Up Alarm",
    "Subscription Tracker Pro",
    "Bill Reminder Tracker",
    "Recurring Payment Tracker",
    "Expiry Date Tracker",
    "Product Expiry Manager",
    "Expiration Reminder Pro",
    "Parking Timer Alert",
    "Parking Reminder Tool",
    "Car Parking Timer Pro",
    "Fuel Consumption Tracker",
    "Car Fuel Calculator",
    "Mileage Tracker Pro",
    "Maintenance Reminder Pro",
    "Car Service Tracker",
    "Vehicle Care Manager",
    "Noise Level Meter Pro",
    "Sound Meter Analyzer",
    "Noise Detector Tool",
    "Tip Calculator Smart",
    "Bill Split Calculator",
    "Split Expenses Tool",
    "Time Tracking Tool",
    "Work Time Tracker",
    "Productivity Timer Pro",
    "Daily Habit Reminder",
    "Routine Reminder Tool",
    "Smart Habit Trigger",
    "Shopping List Smart",
    "Grocery List Manager",
    "Smart List Organizer",
    "Meeting Notes Recorder",
    "Meeting Summary Tool",
    "Voice Notes Summarizer",
    "Contract Checker Tool",
    "Document Risk Scanner",
    "Agreement Analyzer",
    "Electricity Cost Calculator",
    "Power Usage Tracker",
    "Energy Cost Estimator",
    "Water Usage Tracker",
    "Water Consumption Tool",
    "Usage Monitor Pro",
    "Room Measurement Tool",
    "Distance Measure Pro",
    "Area Calculator Tool",
    "Unit Converter Pro",
    "All-in-One Converter",
    "Smart Conversion Tool",
    "Currency Converter Pro",
    "Live Exchange Tool",
    "Money Converter Smart",
    "File Search Tool",
    "Fast File Finder",
    "Storage Search Pro",
    "Clipboard Manager Pro",
    "Copy Paste Manager",
    "Clipboard History Tool"
],

    # Filter apps by release date (True = filter, False = include all apps)
    'FILTER_BY_RELEASE_DATE': True,
    
    # How many months back too include (only used if FILTER_BY_RELEASE_DATE = True)
    'MONTHS_THRESHOLD': 12,

    # Fixed locale for consistent scraping results
    'LANGUAGE': 'en_US',
    'COUNTRY': 'US',

    # Minimum install count required to save the app
    'MINIMUM_INSTALLS': 5000,

    # Delay between detail requests
    'DELAY_BETWEEN_REQUESTS': 1,
}

PLAY_STORE_BASE_URL = 'https://play.google.com/store/apps/details'
SEARCH_BASE_URL = 'https://play.google.com/store/search'
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}
REQUEST_TIMEOUT = 20
CSV_HEADERS = [
    'Niche',
    'App Name',
    'Logo URL',
    'Install Count',
    'Release Date',
    'Rating',
    'Review Count',
    'App Link',
    'Developer',
    'Description',
    'Keywords',
    'Screenshot 1',
    'Screenshot 2',
    'Screenshot 3',
    'Screenshot 4'
]
INTERNAL_FIELDS = [
    'niche', 'app_name', 'logo_url', 'install_count', 'release_date', 'rating', 'review_count',
    'app_link', 'developer', 'description', 'keywords', 'screenshot_1', 'screenshot_2', 'screenshot_3', 'screenshot_4'
]


def create_session():
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    return session


def extract_app_id_from_url(url):
    parsed = urlparse(url)
    app_id = parse_qs(parsed.query).get('id', [None])[0]
    if app_id:
        return app_id

    match = re.search(r'id=([a-zA-Z0-9._]+)', url)
    return match.group(1) if match else None


def build_app_url(app_id):
    return f"{PLAY_STORE_BASE_URL}?{urlencode({'id': app_id, 'hl': CONFIG['LANGUAGE'], 'gl': CONFIG['COUNTRY']})}"


def normalize_app_url(url):
    app_id = extract_app_id_from_url(url)
    return build_app_url(app_id) if app_id else None


def build_search_url(keyword):
    return f"{SEARCH_BASE_URL}?{urlencode({'q': keyword, 'c': 'apps', 'hl': CONFIG['LANGUAGE'], 'gl': CONFIG['COUNTRY']})}"


def fetch_page(session, url, page_cache):
    cached_html = page_cache.get(url)
    if cached_html is None:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        cached_html = response.text
        page_cache[url] = cached_html

    return cached_html, BeautifulSoup(cached_html, 'html.parser')


def csv_row_to_app(row):
    app = {}
    for header, field in zip(CSV_HEADERS, INTERNAL_FIELDS):
        app[field] = row.get(header, row.get(field, ''))
    return app


def app_to_csv_row(app):
    return {
        header: app.get(field, '')
        for header, field in zip(CSV_HEADERS, INTERNAL_FIELDS)
    }


def load_existing_csv(filename='google_play_apps.csv'):
    csv_path = os.path.join(os.path.dirname(__file__), filename)
    existing_apps = {}

    try:
        with open(csv_path, 'r', newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                app = csv_row_to_app(row)
                app_link = normalize_app_url(app.get('app_link', '')) or app.get('app_link', '').strip()
                if not app_link:
                    continue
                app['app_link'] = app_link
                existing_apps[app_link] = app
        print(f"Loaded {len(existing_apps)} existing rows from {csv_path}")
    except FileNotFoundError:
        print(f"No existing CSV found at {csv_path}; starting fresh.")

    return existing_apps

def extract_keywords_from_description(description, num_keywords=5):
    if not description or description == "N/A":
        return "N/A"
    
    text = description.lower()
    text = re.sub(r'http\S+|www\S+', '', text)
    text = re.sub(r'[^a-z0-9\s]', '', text)
    
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these',
        'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which', 'who', 'when', 'where',
        'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such',
        'no', 'nor', 'not', 'only', 'so', 'than', 'as', 'if', 'because', 'while', 'although','your'
    }
    
    words = [word for word in text.split() if len(word) > 2 and word not in stop_words]
    
    if not words:
        return "N/A"
    
    word_freq = Counter(words)
    top_keywords = [word for word, _ in word_freq.most_common(num_keywords)]
    
    return ', '.join(top_keywords) if top_keywords else "N/A"


def _normalize_description_text(text):
    if not text:
        return 'N/A'

    normalized = str(text).replace('\r\n', '\n').replace('\r', '\n')
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in normalized.split('\n')]

    compact = []
    prev_blank = False
    for line in lines:
        if line:
            compact.append(line)
            prev_blank = False
        elif not prev_blank and compact:
            compact.append('')
            prev_blank = True

    result = '\n'.join(compact).strip()
    return result if result else 'N/A'


def extract_release_date(page_source, app_url):
    target_string = 'dappgame_ratings"]]],["'
    start_index = page_source.find(target_string)
    
    if start_index != -1:
        start_index += len(target_string)
        extracted_value = page_source[start_index:start_index + 12]
        release_date = extracted_value.replace('"', '').strip()
        print(f"  Release Date extracted: {release_date}")
        return release_date
    else:
        print(f"  Target string not found for: {app_url}")
        return "N/A"

def extract_install_count(page_source):
    target_string = '<div class="w7Iutd"><div class="wVqUob"><div class="ClM7O">'
    start_index = page_source.find(target_string)
    
    if start_index != -1:
        start_index += len(target_string)
        install_text = page_source[start_index:start_index + 20]
        end_index = install_text.find('<')
        if end_index != -1:
            install_text = install_text[:end_index]
        return install_text.strip()
    return "N/A"

def extract_app_details(session, app_url, target_keyword, page_cache):
    try:
        normalized_url = normalize_app_url(app_url)
        if not normalized_url:
            return None

        page_source, soup = fetch_page(session, normalized_url, page_cache)
        
        # --- Extract App Name ---
        app_name = "N/A"
        app_name_tag = soup.find('h1', {'itemprop': 'name'})
        if app_name_tag:
            app_name = app_name_tag.text.strip()
        
        if app_name == "N/A":
            app_name_tag = soup.find('h1', {'class': 'Fd93Bb'})
            if app_name_tag:
                 app_name = app_name_tag.text.strip()
        
        if app_name == "N/A":
            title_tag = soup.find('title')
            if title_tag:
                title_text = title_tag.text.strip()
                if " - Apps on Google Play" in title_text:
                    app_name = title_text.replace(" - Apps on Google Play", "")
                else:
                    app_name = title_text

        # --- Extract Install Count ---
        install_count = "N/A"
        stats_values = soup.find_all('div', {'class': 'ClM7O'})
        for val in stats_values:
            text = val.text.strip()
            if '+' in text:
                install_count = text
                break
        
        if install_count == "N/A":
            install_count = extract_install_count(page_source)

        
        # Extract developer name
        developer_tag = soup.find('div', {'class': 'Vbfug auoIOc'})
        if not developer_tag:
            developer_tag = soup.find('a', {'class': 'Si6A0c Gwdmqd'})
        developer = developer_tag.text.strip() if developer_tag else "N/A"
        
        # Extract logo URL
        logo_tag = soup.find('img', {'class': 'T75of arM4bb', 'itemprop': 'image'})
        if not logo_tag:
            logo_tag = soup.find('img', {'itemprop': 'image'})
        logo_url = logo_tag['src'] if logo_tag and 'src' in logo_tag.attrs else "N/A"
        
        # Extract up to 4 screenshots
        screenshot_imgs = [
            img.get('src') for img in soup.find_all('img', alt='Screenshot image')
            if img.get('src') and 'play-lh.googleusercontent.com' in img.get('src', '')
        ]
        
        seen = set()
        screenshot_imgs_deduped = []
        for s in screenshot_imgs:
            if s not in seen:
                seen.add(s)
                screenshot_imgs_deduped.append(s)
        screenshots = screenshot_imgs_deduped[:4]
        while len(screenshots) < 4:
            screenshots.append('N/A')
        
        # Extract rating
        rating_tag = soup.find('div', {'class': 'jILTFe'})
        rating = rating_tag.text.strip() if rating_tag else "N/A"
        
        # Extract review count
        review_count_tag = soup.find('div', {'class': 'g1rdde'})
        review_count = review_count_tag.text.strip() if review_count_tag else "N/A"
        
        if rating == "N/A" or "Download" in review_count or "Install" in review_count:
            review_count = "N/A"
        
        # Extract description
        description = "N/A"
        description_tag = soup.find('div', {'data-expandable-section': True})
        if description_tag:
            for br in description_tag.find_all('br'):
                br.replace_with('\n')
            description = description_tag.get_text('\n').strip()
        else:
            desc_tags = soup.find_all('div', {'class': 'bARER'})
            if desc_tags:
                for tag in desc_tags:
                    for br in tag.find_all('br'):
                        br.replace_with('\n')
                description = '\n'.join([tag.get_text('\n').strip() for tag in desc_tags])

        description = _normalize_description_text(description)
        keywords = extract_keywords_from_description(description)
        release_date = extract_release_date(page_source, normalized_url)
        
        # Filter by release date
        if CONFIG['FILTER_BY_RELEASE_DATE']:
            def is_within_threshold(date_str, months=CONFIG['MONTHS_THRESHOLD']):
                try:
                    parsed_date = datetime.strptime(date_str, "%b %d, %Y")
                    now = datetime.now()
                    months_diff = (now.year - parsed_date.year) * 12 + (now.month - parsed_date.month)
                    return 0 <= months_diff < months
                except Exception as e:
                    print(f"  [Date Filter] Could not parse release date '{date_str}': {e}")
                    return False

            if release_date == "N/A" or not is_within_threshold(release_date):
                print(f"  [Date Filter] Skipping app (release date: {release_date})")
                return None
        
        # Filter by minimum installs
        def parse_install_count(installs_str):
            if not installs_str or installs_str == "N/A":
                return 0
            
            clean_str = str(installs_str).replace('+', '').replace(',', '').upper().strip()
            if not clean_str:
                return 0
                
            multiplier = 1
            if 'B' in clean_str:
                multiplier = 1_000_000_000
                clean_str = clean_str.replace('B', '')
            elif 'M' in clean_str:
                multiplier = 1_000_000
                clean_str = clean_str.replace('M', '')
            elif 'K' in clean_str:
                multiplier = 1_000
                clean_str = clean_str.replace('K', '')
                
            try:
                return int(float(clean_str) * multiplier)
            except ValueError:
                return 0

        if parse_install_count(install_count) < CONFIG.get('MINIMUM_INSTALLS', 5000):
            print(f"  [Install Filter] Skipping app (installs: {install_count})")
            return None

        print(f"  App: {app_name}, Installs: {install_count}, Date: {release_date}")
        
        return {
            'niche': target_keyword,
            'app_name': app_name,
            'logo_url': logo_url,
            'install_count': install_count,
            'release_date': release_date,
            'rating': rating,
            'review_count': review_count,
            'app_link': normalized_url,
            'developer': developer,
            'description': description,
            'keywords': keywords,
            'screenshot_1': screenshots[0],
            'screenshot_2': screenshots[1],
            'screenshot_3': screenshots[2],
            'screenshot_4': screenshots[3],
        }
        
    except Exception as e:
        print(f"Error extracting details for {app_url}: {e}")
        return None

def process_search_keyword(session, page_cache, existing_apps, keyword, max_apps=100):
    print(f"\n{'='*60}")
    print(f"Searching Google Play for keyword: '{keyword}'")
    print(f"{'='*60}")
    
    apps_saved_count = 0
    search_url = build_search_url(keyword)
    page_source, soup = fetch_page(session, search_url, page_cache)
    
    app_links = []
    seen_ids = set()

    all_links = [link.get('href') for link in soup.find_all('a', href=True)]
    all_links.extend(re.findall(r'(/store/apps/details\?id=[^"\'&]+)', page_source))
    
    for href in all_links:
        if not href:
            continue
        if '/store/apps/details?id=' in href:
            full_url = urljoin('https://play.google.com', href)
            normalized_url = normalize_app_url(full_url)
            if not normalized_url:
                continue

            app_id = extract_app_id_from_url(normalized_url)
            if not app_id or app_id in seen_ids:
                continue

            seen_ids.add(app_id)
            app_links.append(normalized_url)
            
            if len(app_links) >= max_apps:
                break
    
    print(f"Found {len(app_links)} app links for keyword '{keyword}'")
    
    for idx, app_url in enumerate(app_links[:max_apps], 1):
        print(f"Processing app {idx}/{min(len(app_links), max_apps)}: {app_url}")
        app_data = extract_app_details(session, app_url, keyword, page_cache)
        
        if app_data:
            existing_apps[app_data['app_link']] = app_data
            apps_saved_count += 1
            print(f"  √ {app_data['app_name']} - {app_data['install_count']} installs - {app_data['release_date']}")
        
        time.sleep(CONFIG['DELAY_BETWEEN_REQUESTS'])
    
    return apps_saved_count

def save_to_csv(apps_data, filename='google_play_apps.csv'):
    csv_path = os.path.join(os.path.dirname(__file__), filename)
    apps_list = sorted(apps_data.values(), key=lambda app: app.get('app_name', '').lower())
    
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
            writer.writeheader()

            for app in apps_list:
                writer.writerow(app_to_csv_row(app))
        
        print(f"  √ Saved {len(apps_list)} deduplicated apps to: {csv_path}")
        
    except Exception as e:
        print(f"  × Error saving to CSV: {e}")

def main():
    print("="*60)
    print("Google Play Store Keyword Scraper")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    total_apps_scraped = 0
    csv_filename = 'google_play_apps.csv'
    csv_path = os.path.join(os.path.dirname(__file__), csv_filename)
    
    existing_apps = load_existing_csv(csv_filename)
    session = create_session()
    page_cache = {}
    
    try:
        for keyword in CONFIG['TARGET_KEYWORDS']:
            try:
                apps_count = process_search_keyword(session, page_cache, existing_apps, keyword, max_apps=100)
                total_apps_scraped += apps_count
                
                if apps_count > 0:
                    print(f"√ Collected {apps_count} apps for '{keyword}'")
                    print(f"  📊 Total apps saved so far: {total_apps_scraped}\n")
                else:
                    print(f"× No apps collected for '{keyword}'\n")
                    
            except Exception as e:
                print(f"× Error scraping keyword '{keyword}': {e}\n")
                continue

        save_to_csv(existing_apps, csv_filename)
        
        print(f"\n{'='*60}")
        print(f"√ SCRAPING COMPLETE!")
        print(f"√ Total apps scraped this run: {total_apps_scraped}")
        print(f"√ Total unique apps in file: {len(existing_apps)}")
        print(f"√ Data saved to: {csv_path}")
        print(f"{'='*60}")
        
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user!")
        print(f"Partial data already saved to: {csv_path}")
    
    finally:
        session.close()
        print("\nHTTP session closed.")
        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()