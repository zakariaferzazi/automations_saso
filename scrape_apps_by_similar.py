# -*- coding: utf-8 -*-
"""
Google Play Store App Scraper (Similar Apps Method)
===================================================
1. PHASE 1: Crawl & collect app URLs starting from a SEED URL using "Similar Apps" links.
2. PHASE 2: Extract detailed data for each collected app.
"""

import random

import requests
from bs4 import BeautifulSoup
import time
import csv
import os
import re
from datetime import datetime
from collections import deque, Counter
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

app_links = [
"https://play.google.com/store/apps/details?id=com.artmvstd.pregnancyChecker",
"https://play.google.com/store/apps/details?id=com.artmvstd.physicsSolver",
"https://play.google.com/store/apps/details?id=com.artmvstd.chemistrySolver",
"https://play.google.com/store/apps/details?id=com.artmvstd.geometrySolver",
"https://play.google.com/store/apps/details?id=com.artmvstd.mathSolver",
"https://play.google.com/store/apps/details?id=com.artmvstd.daysTracker",
"https://play.google.com/store/apps/details?id=com.artmvstd.jewelryIdentifier",
"https://play.google.com/store/apps/details?id=com.artmvstd.babyGender",
"https://play.google.com/store/apps/details?id=com.artmvstd.biologySolver",
"https://play.google.com/store/apps/details?id=com.artmvstd.stampIdentifier",
"https://play.google.com/store/apps/details?id=com.artmvstd.halalScanner",
"https://play.google.com/store/apps/details?id=com.artmvstd.sportsCard",
"https://play.google.com/store/apps/details?id=com.artmvstd.profitAi",
"https://play.google.com/store/apps/details?id=com.artmvstd.roastBot",
"https://play.google.com/store/apps/details?id=com.artmvstd.cardScanner",
"https://play.google.com/store/apps/details?id=com.artmvstd.repairHelper",
"https://play.google.com/store/apps/details?id=com.artmvstd.waterEject",
"https://play.google.com/store/apps/details?id=com.artmvstd.historySolver",
"https://play.google.com/store/apps/details?id=com.artmvstd.antiqueIdentifier",
"https://play.google.com/store/apps/details?id=com.artmvstd.snakeIdentifier",
"https://play.google.com/store/apps/details?id=com.artmvstd.statisticsSolver",
"https://play.google.com/store/apps/details?id=com.artmvstd.coinIdentifier",
"https://play.google.com/store/apps/details?id=com.artmvstd.convertPdf",
"https://play.google.com/store/apps/details?id=com.artmvstd.rockIdentifier",
"https://play.google.com/store/apps/details?id=com.artmvstd.flashcardsMaker",
"https://play.google.com/store/apps/details?id=com.artmvstd.signDocuments",
"https://play.google.com/store/apps/details?id=com.artmvstd.voiceTranscriber",
"https://play.google.com/store/apps/details?id=com.artmvstd.interiorDesign",
"https://play.google.com/store/apps/details?id=com.artmvstd.headacheTracker",
"https://play.google.com/store/apps/details?id=com.artmvstd.photoCartoon",
"https://play.google.com/store/apps/details?id=com.artmvstd.fishIdentifier",
"https://play.google.com/store/apps/details?id=com.artmvstd.waterTracker",
"https://play.google.com/store/apps/details?id=com.artmvstd.insectIdentifier",
"https://play.google.com/store/apps/details?id=com.artmvstd.plantIdentifier",
"https://play.google.com/store/apps/details?id=com.artmvstd.animalIdentifier",
"https://play.google.com/store/apps/details?id=com.artmvstd.woodIdentifier",
"https://play.google.com/store/apps/details?id=com.artmvstd.fastingTracker",
"https://play.google.com/store/apps/details?id=com.syngmaster.currencyConverter"
]
# ===========================
# CONFIGURATION - EDIT HERE
# ===========================
CONFIG = {
    # How many apps to extract data for (Fast process = smaller number, Long process = larger number)
    'MAX_APPS_TO_SCRAPE': 4000, 
    
    # The starting app URL too find similar apps from
    'SEED_APP_URL': random.choice(app_links),
    
    # Output file name (shared with category scraper)
    'OUTPUT_CSV': 'google_play_similar_apps.csv',
    
    # Filter apps by release date? (True = filter, False = include all apps)
    'ONLY_RECENT_APPS': True,
    
    # How many months back to include (only used if ONLY_RECENT_APPS = True)
    'MONTHS_THRESHOLD': 12,
    
    # Minimum install count required to save the app
    'MIN_INSTALLS': 5000,
    
    # Crawling settings
    'CRAWL_DEPTH': 10,
    'MAX_SIMILAR_APPS_PER_PAGE': 20,
    'DELAY_BETWEEN_REQUESTS': 1
}

PLAY_STORE_BASE_URL = 'https://play.google.com/store/apps/details'
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}
REQUEST_TIMEOUT = 20

# ===========================
# Helper functions
# ===========================
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
        'no', 'nor', 'not', 'only', 'so', 'than', 'as', 'if', 'because', 'while', 'although','your'
    }
    
    # Split and filter words
    words = [word for word in text.split() if len(word) > 2 and word not in stop_words]
    
    if not words:
        return "N/A"
    
    # Count word frequencies and get top keywords
    word_freq = Counter(words)
    top_keywords = [word for word, _ in word_freq.most_common(num_keywords)]
    
    return ', '.join(top_keywords) if top_keywords else "N/A"


def _normalize_description_text(text):
    if not text:
        return 'N/A'

    # Normalize whitespace while keeping paragraph breaks readable.
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

# ===========================
# MAIN SCRAPER CLASS
# ===========================
class SimilarAppsScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(REQUEST_HEADERS)
        self.visited_apps = set()
        self.apps_to_visit = deque()
        self.apps_saved_count = 0
        self.page_cache = {}
        self.fieldnames = [
            'Niche', 'App Name', 'Logo URL', 'Install Count',
            'Release Date', 'Rating', 'Review Count', 'App Link', 'Developer',
            'Description', 'Keywords', 'Screenshot 1', 'Screenshot 2', 'Screenshot 3', 'Screenshot 4'
        ]
        self.all_apps = {}

    def load_existing_csv(self):
        """Load existing CSV rows so new data can be merged by App Link."""
        csv_path = os.path.join(os.path.dirname(__file__), CONFIG['OUTPUT_CSV'])
        try:
            with open(csv_path, 'r', newline='', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                loaded_count = 0
                for row in reader:
                    app_link = self.normalize_app_url(row.get('App Link', '')) or row.get('App Link', '').strip()
                    if not app_link:
                        continue
                    row['App Link'] = app_link
                    self.all_apps[app_link] = row
                    loaded_count += 1
                print(f"Loaded {loaded_count} existing similar-app rows from {csv_path}")
        except FileNotFoundError:
            print(f"No existing similar-app CSV found at {csv_path}; starting fresh.")
    
    def extract_app_id_from_url(self, url):
        """Extract app package ID from Play Store URL"""
        parsed = urlparse(url)
        app_id = parse_qs(parsed.query).get('id', [None])[0]
        if app_id:
            return app_id

        match = re.search(r'id=([a-zA-Z0-9._]+)', url)
        return match.group(1) if match else None

    def build_app_url(self, app_id):
        """Build a canonical Play Store URL with fixed locale for consistent parsing."""
        return f"{PLAY_STORE_BASE_URL}?{urlencode({'id': app_id, 'hl': 'en_US', 'gl': 'US'})}"

    def normalize_app_url(self, url):
        """Normalize app URLs so crawled links deduplicate correctly."""
        app_id = self.extract_app_id_from_url(url)
        return self.build_app_url(app_id) if app_id else None

    def fetch_page(self, app_url):
        """Fetch and cache a Play Store app page."""
        normalized_url = self.normalize_app_url(app_url)
        if not normalized_url:
            return None, None, None

        cached_html = self.page_cache.get(normalized_url)
        if cached_html is None:
            response = self.session.get(normalized_url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            cached_html = response.text
            self.page_cache[normalized_url] = cached_html

        return normalized_url, cached_html, BeautifulSoup(cached_html, 'html.parser')
    
    def get_similar_apps(self, app_url):
        """Get similar apps from an app page (Phase 1)"""
        try:
            current_url, page_source, soup = self.fetch_page(app_url)
            if not page_source or not soup:
                return []

            current_app_id = self.extract_app_id_from_url(current_url)
            candidate_urls = []

            for link in soup.select('a[href*="/store/apps/details?id="]'):
                href = link.get('href')
                if not href:
                    continue
                candidate_urls.append(urljoin('https://play.google.com', href))

            candidate_urls.extend(
                urljoin('https://play.google.com', match)
                for match in re.findall(r'(/store/apps/details\?id=[^"\'&]+)', page_source)
            )

            similar_apps = []
            seen_ids = set()
            for candidate_url in candidate_urls:
                normalized_url = self.normalize_app_url(candidate_url)
                if not normalized_url:
                    continue

                app_id = self.extract_app_id_from_url(normalized_url)
                if not app_id or app_id == current_app_id or app_id in self.visited_apps or app_id in seen_ids:
                    continue

                seen_ids.add(app_id)
                similar_apps.append(normalized_url)

                if len(similar_apps) >= CONFIG['MAX_SIMILAR_APPS_PER_PAGE']:
                    break

            return similar_apps
        except Exception as e:
            print(f"Error collecting similar apps: {e}")
            return []
    
    # ---------------------------------------------------------
    # DATA EXTRACTION METHODS (From scrape_categories_to_csv)
    # ---------------------------------------------------------
    def extract_release_date(self, page_source, app_url):
        target_string = 'dappgame_ratings"]]],["'
        start_index = page_source.find(target_string)
        
        if start_index != -1:
            start_index += len(target_string)
            extracted_value = page_source[start_index:start_index + 12]
            release_date = extracted_value.replace('"', '').strip()
            return release_date
        return "N/A"

    def extract_install_count(self, page_source):
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

    def parse_install_count(self, install_str):
        """Parse install count string to integer"""
        if not install_str or install_str == "N/A":
            return 0
            
        clean_str = install_str.upper().replace(',', '').replace('+', '').replace(' ', '')
        
        try:
            if 'K' in clean_str:
                return int(float(clean_str.replace('K', '')) * 1000)
            elif 'M' in clean_str:
                return int(float(clean_str.replace('M', '')) * 1000000)
            elif 'B' in clean_str:
                return int(float(clean_str.replace('B', '')) * 1000000000)
            else:
                return int(float(clean_str))
        except ValueError:
            return 0

    def extract_app_details(self, app_url):
        """Extract detailed information from the app page (Phase 2)"""
        try:
            normalized_url, page_source, soup = self.fetch_page(app_url)
            if not page_source or not soup:
                return None
            
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
                    app_name = title_text.replace(" - Apps on Google Play", "") if " - Apps on Google Play" in title_text else title_text

            # --- Extract Install Count ---
            install_count = "N/A"
            stats_values = soup.find_all('div', {'class': 'ClM7O'})
            for val in stats_values:
                text = val.text.strip()
                if '+' in text:
                    install_count = text
                    break
            if install_count == "N/A":
                install_count = self.extract_install_count(page_source)

            # --- Extract Developer name ---
            developer_tag = soup.find('div', {'class': 'Vbfug auoIOc'})
            if not developer_tag:
                developer_tag = soup.find('a', {'class': 'Si6A0c Gwdmqd'})
            developer = developer_tag.text.strip() if developer_tag else "N/A"
            
            # --- Extract Logo URL ---
            logo_tag = soup.find('img', {'class': 'T75of arM4bb', 'itemprop': 'image'})
            if not logo_tag:
                logo_tag = soup.find('img', {'itemprop': 'image'})
            logo_url = logo_tag['src'] if logo_tag and 'src' in logo_tag.attrs else "N/A"
            
            # --- Extract up to 4 Screenshots ---
            # Use alt='Screenshot image' attribute which is specific to screenshots in Google Play
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
            
            # --- Extract Rating ---
            rating_tag = soup.find('div', {'class': 'jILTFe'})
            rating = rating_tag.text.strip() if rating_tag else "N/A"
            
            # --- Extract Review Count ---
            review_count_tag = soup.find('div', {'class': 'g1rdde'})
            review_count = review_count_tag.text.strip() if review_count_tag else "N/A"
            if rating == "N/A" or "Download" in review_count or "Install" in review_count:
                review_count = "N/A"
            
            # --- Extract Release Date ---
            release_date = self.extract_release_date(page_source, app_url)
            
            # --- Extract Description (preserve HTML formatting) ---
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
            
            # --- Extract Keywords from Description ---
            keywords = extract_keywords_from_description(description)
            
            # --- Extract Category (Niche) ---
            category_name = "General"

            # --- Date Filter Logic ---
            if CONFIG['ONLY_RECENT_APPS']:
                try:
                    parsed_date = datetime.strptime(release_date, "%b %d, %Y")
                    now = datetime.now()
                    months_diff = (now.year - parsed_date.year) * 12 + (now.month - parsed_date.month)
                    months_threshold = CONFIG.get('MONTHS_THRESHOLD', 3)
                    if not (0 <= months_diff < months_threshold):
                        print(f"    [Skipping] Release date '{release_date}' is outside {months_threshold} month window.")
                        return None
                except Exception as e:
                    print(f"    [Skipping] Could not verify release date: {release_date}")
                    return None

            # --- Install Count Filter Logic ---
            if 'MIN_INSTALLS' in CONFIG and CONFIG['MIN_INSTALLS'] > 0:
                parsed_installs = self.parse_install_count(install_count)
                if parsed_installs < CONFIG['MIN_INSTALLS']:
                    print(f"    [Skipping] Install count '{install_count}' is below {CONFIG['MIN_INSTALLS']} limit.")
                    return None

            return {
                'Niche': category_name,
                'App Name': app_name,
                'Logo URL': logo_url,
                'Install Count': install_count,
                'Release Date': release_date,
                'Rating': rating,
                'Review Count': review_count,
                'App Link': normalized_url,
                'Developer': developer,
                'Description': description,
                'Keywords': keywords,
                'Screenshot 1': screenshots[0],
                'Screenshot 2': screenshots[1],
                'Screenshot 3': screenshots[2],
                'Screenshot 4': screenshots[3],
            }
            
        except Exception as e:
            print(f"Error extracting details for {app_url}: {e}")
            return None

    def save_to_csv(self, app_data):
        """Merge one app row into the in-memory dataset keyed by App Link."""
        if not app_data:
            return

        app_link = self.normalize_app_url(app_data.get('App Link', '')) or app_data.get('App Link', '').strip()
        if not app_link:
            return

        app_data['App Link'] = app_link
        self.all_apps[app_link] = app_data
        self.apps_saved_count += 1
        print(f"    ✓ MERGED: {app_data['App Name']} ({app_data['Install Count']} installs)")

    def write_all_to_csv(self):
        """Write one deduplicated CSV file from the merged app map."""
        csv_path = os.path.join(os.path.dirname(__file__), CONFIG['OUTPUT_CSV'])
        apps_list = sorted(self.all_apps.values(), key=lambda app: app.get('App Name', '').lower())

        with open(csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.fieldnames)
            writer.writeheader()
            writer.writerows(apps_list)

        print(f"Saved {len(apps_list)} deduplicated apps to: {csv_path}")

    def run(self):
        """Run the two-phase scraper"""
        print("="*60)
        print("Google Play Store App Data Scraper (Similar Apps Method)")
        print(f"Max apps target: {CONFIG['MAX_APPS_TO_SCRAPE']}")
        print("="*60)

        self.load_existing_csv()
        self.apps_to_visit.append((CONFIG['SEED_APP_URL'], 0))
        collected_app_urls = set()
        
        # Existing data is loaded first and rewritten as one deduplicated file at the end.
        csv_path = os.path.join(os.path.dirname(__file__), CONFIG['OUTPUT_CSV'])
        print(f"Merging scraped data into: {csv_path}")
            
        try:
            # ==================================
            # PHASE 1: COLLECT URLs
            # ==================================
            print("\n" + "-"*40)
            print("PHASE 1: Collecting App URLs")
            print("-"*40)
            
            while self.apps_to_visit and len(collected_app_urls) < CONFIG['MAX_APPS_TO_SCRAPE']:
                current_url, depth = self.apps_to_visit.popleft()
                app_id = self.extract_app_id_from_url(current_url)
                
                if not app_id or app_id in self.visited_apps:
                    continue
                    
                self.visited_apps.add(app_id)
                normalized_url = self.normalize_app_url(current_url)
                if not normalized_url:
                    continue

                collected_app_urls.add(normalized_url)
                
                print(f"Found [{len(collected_app_urls)}/{CONFIG['MAX_APPS_TO_SCRAPE']}]: {app_id}")
                
                if depth < CONFIG['CRAWL_DEPTH'] and len(collected_app_urls) < CONFIG['MAX_APPS_TO_SCRAPE']:
                    similar = self.get_similar_apps(normalized_url)
                    for url in similar:
                        if self.extract_app_id_from_url(url) not in self.visited_apps:
                            self.apps_to_visit.append((url, depth + 1))
                            
                time.sleep(0.2)
            
            # ==================================
            # PHASE 2: EXTRACT DATA
            # ==================================
            print("\n" + "-"*40)
            print("PHASE 2: Extracting App Data")
            print("-"*40)
            
            for index, url in enumerate(list(collected_app_urls)[:CONFIG['MAX_APPS_TO_SCRAPE']], 1):
                app_id = self.extract_app_id_from_url(url)
                print(f"\nProcessing {index}/{len(collected_app_urls)}: {app_id}")
                
                app_data = self.extract_app_details(url)
                if app_data:
                    self.save_to_csv(app_data)
                    
                time.sleep(CONFIG['DELAY_BETWEEN_REQUESTS'])

            self.write_all_to_csv()
                
            print("\n" + "="*60)
            print("SCRAPING COMPLETE!")
            print(f"Total scraped apps merged this run: {self.apps_saved_count}")
            print(f"Total unique apps in file: {len(self.all_apps)}")
            print(f"Data saved to: {csv_path}")
            print("="*60)

        except KeyboardInterrupt:
            print("\nScraping interrupted by user!")
        except Exception as e:
            print(f"\nCritical Error: {e}")
        finally:
            self.session.close()
            print("HTTP session closed.")

if __name__ == "__main__":
    scraper = SimilarAppsScraper()
    scraper.run()
