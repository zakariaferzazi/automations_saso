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
    # Filter apps by release date (True = filter, False = include all apps)
    'FILTER_BY_RELEASE_DATE': True,
    
    # How many months back too include (only used if FILTER_BY_RELEASE_DATE = True)
    # Example: 3 = last 3 months, 6 = last 6 months, 12 = last year
    'MONTHS_THRESHOLD': 12,

    # Fixed locale for consistent scraping results
    'LANGUAGE': 'en_US',
    'COUNTRY': 'US',

    # Delay between detail requests
    'DELAY_BETWEEN_REQUESTS': 1,
}

PLAY_STORE_BASE_URL = 'https://play.google.com/store/apps/details'
CATEGORY_BASE_URL = 'https://play.google.com/store/apps/category'
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

# Google Play Store Categories  (names match App Store niches exactly)
CATEGORIES = {
    "Games":               "GAME",
    # "Business":            "BUSINESS",
    # "Education":           "EDUCATION",
    # "Entertainment":       "ENTERTAINMENT",
    # "Finance":             "FINANCE",
    # "Food & Drink":        "FOOD_AND_DRINK",
    # "Health & Fitness":    "HEALTH_AND_FITNESS",
    # "Lifestyle":           "LIFESTYLE",
    # "Medical":             "MEDICAL",
    # "Music":               "MUSIC_AND_AUDIO",
    # "News":                "NEWS_AND_MAGAZINES",
    # "Photo & Video":       "PHOTOGRAPHY",
    # "Productivity":        "PRODUCTIVITY",
    # "Shopping":            "SHOPPING",
    # "Social Networking":   "SOCIAL",
    # "Sports":              "SPORTS",
    # "Travel":              "TRAVEL_AND_LOCAL",
    # "Utilities":           "TOOLS",
}


def create_session():
    """Create a shared HTTP session for category and detail requests."""
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    return session


def extract_app_id_from_url(url):
    """Extract app package ID from a Play Store URL."""
    parsed = urlparse(url)
    app_id = parse_qs(parsed.query).get('id', [None])[0]
    if app_id:
        return app_id

    match = re.search(r'id=([a-zA-Z0-9._]+)', url)
    return match.group(1) if match else None


def build_app_url(app_id):
    """Build a canonical Play Store app URL with fixed locale."""
    return f"{PLAY_STORE_BASE_URL}?{urlencode({'id': app_id, 'hl': CONFIG['LANGUAGE'], 'gl': CONFIG['COUNTRY']})}"


def normalize_app_url(url):
    """Normalize app links so duplicates collapse cleanly."""
    app_id = extract_app_id_from_url(url)
    return build_app_url(app_id) if app_id else None


def build_category_url(category_id):
    """Build a category URL with fixed locale."""
    return f"{CATEGORY_BASE_URL}/{category_id}?{urlencode({'hl': CONFIG['LANGUAGE'], 'gl': CONFIG['COUNTRY']})}"


def fetch_page(session, url, page_cache):
    """Fetch and cache a page to avoid repeat requests."""
    cached_html = page_cache.get(url)
    if cached_html is None:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        cached_html = response.text
        page_cache[url] = cached_html

    return cached_html, BeautifulSoup(cached_html, 'html.parser')


def csv_row_to_app(row):
    """Convert CSV headers to the script's internal field names."""
    app = {}
    for header, field in zip(CSV_HEADERS, INTERNAL_FIELDS):
        app[field] = row.get(header, row.get(field, ''))
    return app


def app_to_csv_row(app):
    """Convert internal field names back to CSV headers."""
    return {
        header: app.get(field, '')
        for header, field in zip(CSV_HEADERS, INTERNAL_FIELDS)
    }


def load_existing_csv(filename='google_play_apps.csv'):
    """Load existing CSV rows and index them by app_link."""
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
        print(f"Loaded {len(existing_apps)} existing Google Play category rows from {csv_path}")
    except FileNotFoundError:
        print(f"No existing Google Play category CSV found at {csv_path}; starting fresh.")

    return existing_apps

def extract_keywords_from_description(description, num_keywords=5):
    """Extract most common keywords from description"""
    if not description or description == "N/A":
        return "N/A"
    
    # Convert to lowercase and remove special characters
    text = description.lower()
    # Remove URLs
    text = re.sub(r'http\S+|www\S+', '', text)
    # Remove special characters but keep spaces
    text = re.sub(r'[^a-z0-9\s]', '', text)
    
    # Common stop words to ignore
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these',
        'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which', 'who', 'when', 'where',
        'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such',
        'no', 'nor', 'not', 'only', 'so', 'than', 'as', 'if', 'because', 'while', 'although'
    }
    
    # Split and filter words
    words = [word for word in text.split() if len(word) > 2 and word not in stop_words]
    
    if not words:
        return "N/A"
    
    # Count word frequencies and get top keywords
    word_freq = Counter(words)
    top_keywords = [word for word, _ in word_freq.most_common(num_keywords)]
    
    return ', '.join(top_keywords) if top_keywords else "N/A"
def extract_release_date(page_source, app_url):
    """Extract release date using the existing pattern"""
    target_string = 'dappgame_ratings"]]],["'
    start_index = page_source.find(target_string)
    
    if start_index != -1:
        # Start from the position of the target string and move 12 characters ahead
        start_index += len(target_string)
        extracted_value = page_source[start_index:start_index + 12]
        release_date = extracted_value.replace('"', '').strip()
        print(f"  Release Date extracted: {release_date}")
        return release_date
    else:
        print(f"  Target string not found for: {app_url}")
        return "N/A"

def extract_install_count(page_source):
    """Extract install count using the existing pattern"""
    target_string = '<div class="w7Iutd"><div class="wVqUob"><div class="ClM7O">'
    start_index = page_source.find(target_string)
    
    if start_index != -1:
        start_index += len(target_string)
        # Extract more characters to capture full install count
        install_text = page_source[start_index:start_index + 20]
        # Find the closing tag
        end_index = install_text.find('<')
        if end_index != -1:
            install_text = install_text[:end_index]
        return install_text.strip()
    return "N/A"

def extract_app_details(session, app_url, category_name, page_cache):
    """Extract detailed information from app page."""
    try:
        normalized_url = normalize_app_url(app_url)
        if not normalized_url:
            return None

        page_source, soup = fetch_page(session, normalized_url, page_cache)
        
        # --- Extract App Name ---
        app_name = "N/A"
        # 1. Try standard H1 with itemprop
        app_name_tag = soup.find('h1', {'itemprop': 'name'})
        if app_name_tag:
            app_name = app_name_tag.text.strip()
        
        # 2. Try class Fd93Bb
        if app_name == "N/A":
            app_name_tag = soup.find('h1', {'class': 'Fd93Bb'})
            if app_name_tag:
                 app_name = app_name_tag.text.strip()
        
        # 3. Try <title> tag fallback
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
        # 1. Search for the class 'ClM7O' which often contains the stats values (Rating, Downloads, Size etc.)
        # We look for one containing '+'
        stats_values = soup.find_all('div', {'class': 'ClM7O'})
        for val in stats_values:
            text = val.text.strip()
            if '+' in text:
                install_count = text
                break
        
        # 2. Fallback to existing string extraction method if soup failed
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
        
        # Extract up to 4 screenshots using alt='Screenshot image' (exact HTML attribute from Google Play)
        screenshot_imgs = [
            img.get('src') for img in soup.find_all('img', alt='Screenshot image')
            if img.get('src') and 'play-lh.googleusercontent.com' in img.get('src', '')
        ]
        # Deduplicate while preserving order
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
        
        # Fix: If rating is N/A or review count looks like Downloads/Installs, set to N/A
        if rating == "N/A" or "Download" in review_count or "Install" in review_count:
            review_count = "N/A"
        
        # Extract description
        description = "N/A"
        description_tag = soup.find('div', {'data-expandable-section': True})
        if description_tag:
            description = description_tag.text.strip()
        else:
            # Try alternative selectors
            desc_tags = soup.find_all('div', {'class': 'bARER'})
            if desc_tags:
                description = ' '.join([tag.text.strip() for tag in desc_tags])
        
        # Extract keywords from description
        keywords = extract_keywords_from_description(description)
        
        # Extract release date
        release_date = extract_release_date(page_source, normalized_url)
        
        # --- Filter by release date (OPTIONAL) ---
        if CONFIG['FILTER_BY_RELEASE_DATE']:
            def is_within_threshold(date_str, months=CONFIG['MONTHS_THRESHOLD']):
                try:
                    # Example format: Feb 11, 2025
                    parsed_date = datetime.strptime(date_str, "%b %d, %Y")
                    now = datetime.now()
                    # Calculate the difference in months
                    months_diff = (now.year - parsed_date.year) * 12 + (now.month - parsed_date.month)
                    # If released within threshold months, keep it
                    return 0 <= months_diff < months
                except Exception as e:
                    print(f"  [Date Filter] Could not parse release date '{date_str}': {e}")
                    return False

            if release_date == "N/A" or not is_within_threshold(release_date):
                print(f"  [Date Filter] Skipping app (release date: {release_date})")
                return None
        
        # Debug print
        print(f"  App: {app_name}, Installs: {install_count}, Date: {release_date}")
        
        return {
            'niche': category_name,
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

def scrape_category(session, page_cache, existing_apps, category_name, category_id, max_apps=100):
    """Scrape apps from a specific category."""
    print(f"\n{'='*60}")
    print(f"Scraping category: {category_name}")
    print(f"{'='*60}")
    
    apps_saved_count = 0
    
    category_url = build_category_url(category_id)
    page_source, soup = fetch_page(session, category_url, page_cache)
    
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
    
    print(f"Found {len(app_links)} app links in {category_name}")
    
    # Extract details for each app and save immediately
    for idx, app_url in enumerate(app_links[:max_apps], 1):
        print(f"Processing app {idx}/{min(len(app_links), max_apps)}: {app_url}")
        
        app_data = extract_app_details(session, app_url, category_name, page_cache)
        
        if app_data:
            existing_apps[app_data['app_link']] = app_data
            apps_saved_count += 1
            print(f"  ✓ {app_data['app_name']} - {app_data['install_count']} installs - {app_data['release_date']}")
        
        # Small delay to avoid rate limiting
        time.sleep(CONFIG['DELAY_BETWEEN_REQUESTS'])
    
    return apps_saved_count

def save_to_csv(apps_data, filename='google_play_apps.csv'):
    """Write one deduplicated CSV file from the merged app map."""
    
    csv_path = os.path.join(os.path.dirname(__file__), filename)
    apps_list = sorted(apps_data.values(), key=lambda app: app.get('app_name', '').lower())
    
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
            writer.writeheader()

            for app in apps_list:
                writer.writerow(app_to_csv_row(app))
        
        print(f"  ✓ Saved {len(apps_list)} deduplicated apps to: {csv_path}")
        
    except Exception as e:
        print(f"  ✗ Error saving to CSV: {e}")

def main():
    """Main function to orchestrate scraping"""
    print("="*60)
    print("Google Play Store Category Scraper")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    total_apps_scraped = 0
    csv_filename = 'google_play_apps.csv'

    csv_path = os.path.join(os.path.dirname(__file__), csv_filename)
    existing_apps = load_existing_csv(csv_filename)

    session = create_session()
    page_cache = {}
    
    try:
        # Scrape each category
        for idx, (category_name, category_id) in enumerate(CATEGORIES.items(), 1):
            try:
                apps_count = scrape_category(session, page_cache, existing_apps, category_name, category_id, max_apps=100)
                
                total_apps_scraped += apps_count
                if apps_count > 0:
                    print(f"✓ Collected {apps_count} apps from {category_name}")
                    print(f"  📊 Total apps saved so far: {total_apps_scraped}\n")
                else:
                    print(f"✗ No apps collected from {category_name}\n")
                    
            except Exception as e:
                print(f"✗ Error scraping {category_name}: {e}\n")
                continue

        save_to_csv(existing_apps, csv_filename)
        
        # Final summary
        print(f"\n{'='*60}")
        print(f"✓ SCRAPING COMPLETE!")
        print(f"✓ Total apps scraped: {total_apps_scraped}")
        print(f"✓ Total unique apps in file: {len(existing_apps)}")
        print(f"✓ Data saved to: {csv_path}")
        print(f"{'='*60}")
        
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user!")
        print(f"Partial data already saved to: {csv_path}")
        print(f"Total apps saved: {total_apps_scraped}")
    
    finally:
        session.close()
        print("\nHTTP session closed.")
        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
