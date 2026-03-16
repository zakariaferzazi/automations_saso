import requests
import csv
import time
import random
import json
from datetime import datetime, timedelta
from collections import Counter
import re
from bs4 import BeautifulSoup

# ===========================
# CONFIGURATION - EDIT HERE
# ===========================
CONFIG = {
    # Filter apps by release date (True = filter, False = include all apps)
    'FILTER_BY_RELEASE_DATE': True,
    
    # How many days back too include (only used if FILTER_BY_RELEASE_DATE = True)
    # Example: 90 = last 90 days, 180 = last 6 months, `365` = last year
    'DAYS_THRESHOLD': 365,
}

# App Store category IDs for RSS feeds
# App Store Categories (iTunes genre IDs — names match Play Store niches exactly)
CATEGORIES = {
    "Games":               6014,
    # "Business":            6000,
    # "Education":           6017,
    # "Entertainment":       6016,
    # "Finance":             6015,
    # "Food & Drink":        6023,
    # "Health & Fitness":    6013,
    # "Lifestyle":           6010,
    # "Medical":             6020,
    # "Music":               6011,
    # "News":                6009,
    # "Photo & Video":       6008,
    # "Productivity":        6007,
    # "Shopping":            6024,
    # "Social Networking":   6005,
    # "Sports":              6004,
    # "Travel":              6003,
    # "Utilities":           6002,
}

# Countries to search (using correct iTunes store country codes)
COUNTRIES = ['us', 'gb', 'ca', 'fr', 'de', 'ie', 'nl', 'no', 'ch']

def extract_keywords_from_description(description, num_keywords=5):
    """Extract most common keywords from description"""
    if not description or description == "":
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

# Date formats the iTunes API may return
_ITUNES_DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%SZ",     # standard:   2024-01-15T08:00:00Z
    "%Y-%m-%dT%H:%M:%S.%fZ",  # with ms:    2024-01-15T08:00:00.000Z
    "%Y-%m-%dT%H:%M:%S%z",    # with tz:    2024-01-15T08:00:00+00:00
    "%Y-%m-%dT%H:%M:%S.%f%z", # ms + tz:    2024-01-15T08:00:00.000+00:00
)


def _parse_itunes_date(date_str: str):
    """Parse an iTunes API date string, handling all known Apple date formats."""
    if not date_str:
        return None
    for fmt in _ITUNES_DATE_FORMATS:
        try:
            dt = datetime.strptime(date_str, fmt)
            # Strip tzinfo so comparisons with datetime.now() work cleanly
            return dt.replace(tzinfo=None)
        except ValueError:
            continue
    return None


class AppStoreSearcher:
    def __init__(self, days_threshold=None):
        """
        Initialize the App Store searcher
        
        :param days_threshold: Only fetch apps released within this many days (overrides CONFIG if provided)
        """
        self.rss_url_template = "https://itunes.apple.com/{country}/rss/topfreeapplications/limit=200/genre={genre_id}/json"
        self.lookup_url = "https://itunes.apple.com/lookup"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
            'Accept': 'application/json',
        }
        self.filter_by_date = CONFIG['FILTER_BY_RELEASE_DATE']
        self.days_threshold = days_threshold if days_threshold is not None else CONFIG['DAYS_THRESHOLD']
        self.cutoff_date = datetime.now() - timedelta(days=self.days_threshold)
        self.fieldnames = ['Niche', 'App Name', 'Logo URL', 'Install Count', 'Release Date', 'Rating', 'Review Count', 'App Link', 'Developer', 'Description', 'Keywords', 'Screenshot 1', 'Screenshot 2', 'Screenshot 3', 'Screenshot 4']
        self.all_apps = {}  # Use dict to avoid duplicates (key: App Link)

    def load_existing_csv(self, filename='app_store_apps.csv'):
        """Load existing CSV rows so new data can be merged by App Link."""
        try:
            with open(filename, 'r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                loaded_count = 0
                for row in reader:
                    app_link = row.get('App Link', '').strip()
                    if not app_link:
                        continue
                    self.all_apps[app_link] = row
                    loaded_count += 1
                print(f"Loaded {loaded_count} existing App Store rows from {filename}")
        except FileNotFoundError:
            print(f"No existing App Store CSV found at {filename}; starting fresh.")
    
    def estimate_install_count(self, review_count):
        """
        Estimate install count based on review count.
        Returns a single random number within the estimated range.
        """
        def fmt(n):
            if n >= 1_000_000:
                return f"{n/1_000_000:.1f}M".replace('.0M', 'M')
            elif n >= 1_000:
                return f"{n/1_000:.1f}K".replace('.0K', 'K')
            return str(n)

        if review_count <= 10:
            return fmt(random.randint(500, 1_200))
        elif review_count <= 50:
            return fmt(random.randint(1_200, 6_000))
        elif review_count <= 200:
            return fmt(random.randint(6_000, 24_000))
        elif review_count <= 1000:
            return fmt(random.randint(24_000, 120_000))
        elif review_count <= 5000:
            return fmt(random.randint(120_000, 600_000))
        elif review_count <= 20000:
            return fmt(random.randint(600_000, 2_400_000))
        elif review_count <= 100000:
            return fmt(random.randint(2_400_000, 12_000_000))
        else:
            return fmt(random.randint(12_000_000, 50_000_000))
        
    def search_by_category(self, category_id, country='us', limit=200):
        """
        Search for apps by category using RSS feeds
        
        :param category_id: Category ID to search
        :param country: Two-letter country code
        :param limit: Maximum number of results (max 200)
        :return: List of app IDs
        """
        # RSS feeds support up to 200
        url = self.rss_url_template.format(country=country, genre_id=category_id)
        url = url.replace('limit=200', f'limit={limit}')
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract app IDs from RSS feed
            app_ids = []
            if 'feed' in data and 'entry' in data['feed']:
                for entry in data['feed']['entry']:
                    app_id = entry.get('id', {}).get('attributes', {}).get('im:id')
                    if app_id:
                        app_ids.append(int(app_id))
            
            return app_ids
        
        except requests.RequestException as e:
            print(f"Error searching category {category_id} in {country}: {e}")
            return []
        except (KeyError, ValueError) as e:
            print(f"Error parsing response for category {category_id} in {country}: {e}")
            return []

    def _get_screenshots_from_page(self, app_id):
        """
        Fallback: fetch the App Store web page and extract screenshot URLs
        from the embedded serialized-server-data JSON when the iTunes API
        returns an empty screenshotUrls list.
        """
        try:
            url = f'https://apps.apple.com/us/app/id{app_id}'
            page_resp = requests.get(url, headers=self.headers, timeout=15)
            if page_resp.status_code != 200:
                return []
            soup_page = BeautifulSoup(page_resp.text, 'html.parser')
            tag = soup_page.find('script', id='serialized-server-data')
            if not tag or not tag.string:
                return []
            data = json.loads(tag.string)

            # Walk the JSON tree collecting objects keyed 'screenshot'
            results = []

            def collect(obj, depth=0):
                if depth > 20:
                    return
                if isinstance(obj, dict):
                    if 'screenshot' in obj and isinstance(obj['screenshot'], dict):
                        ss = obj['screenshot']
                        template = ss.get('template', '')
                        if template and 'mzstatic.com' in template:
                            width = ss.get('width', 0)
                            height = ss.get('height', 0)
                            variants = ss.get('variants', [])
                            fmt = variants[0].get('format', 'jpg') if variants else 'jpg'
                            real_url = (template
                                .replace('{w}', str(width))
                                .replace('{h}', str(height))
                                .replace('{c}', 'bb')
                                .replace('{f}', fmt))
                            results.append(real_url)
                    for v in obj.values():
                        collect(v, depth + 1)
                elif isinstance(obj, list):
                    for item in obj:
                        collect(item, depth)

            collect(data)

            # Deduplicate while preserving order
            seen = set()
            unique = []
            for u in results:
                if u not in seen:
                    seen.add(u)
                    unique.append(u)
            return unique
        except Exception:
            return []

    def get_app_metadata(self, app_id):
        """
        Retrieve detailed metadata for a specific app
        
        :param app_id: App ID to fetch
        :return: Dictionary with app metadata or None
        """
        try:
            url = f'{self.lookup_url}?id={app_id}'
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            app_data = response.json()
            
            if app_data['resultCount'] == 0:
                print(f"No app found with ID {app_id}")
                return None
            
            app_info = app_data['results'][0]
            
            # Parse release date.
            # releaseDate = original first-publish date on the App Store.
            release_date_str = app_info.get('releaseDate', '')
            if not release_date_str:
                return None

            release_date = _parse_itunes_date(release_date_str)
            if release_date is None:
                print(f"  Skipped (unparseable date: {release_date_str!r})")
                return None

            # Check if app was released within the threshold (OPTIONAL)
            if self.filter_by_date and release_date < self.cutoff_date:
                return None

            # Calculate days since release for filtering and display
            days_since_release = (datetime.now() - release_date).days
            
            # Get review count for install estimation
            review_count = app_info.get('userRatingCount', 0)
            
            # Skip apps with no reviews at all
            if review_count == 0:
                print(f"  Skipped (no reviews)")
                return None
            
            # Format rating (e.g. 4.7)
            rating_val = app_info.get('averageUserRating', 0)
            formatted_rating = round(float(rating_val), 1) if rating_val else 0
            
            # Format review count (e.g. 122k)
            if review_count >= 1000000:
                formatted_review_count = f"{review_count/1000000:.1f}M".replace(".0M", "M")
            elif review_count >= 1000:
                formatted_review_count = f"{review_count/1000:.0f}k"
            else:
                formatted_review_count = str(review_count)
            
            # Prepare metadata dictionary (simplified fields only)
            description = app_info.get('description', '')
            keywords = extract_keywords_from_description(description)
            
            # Extract up to 4 screenshots (prefer iPhone, fallback to iPad, then page scrape)
            screenshot_urls = app_info.get('screenshotUrls', []) or app_info.get('ipadScreenshotUrls', [])
            if not screenshot_urls:
                screenshot_urls = self._get_screenshots_from_page(app_id)
            screenshots = screenshot_urls[:4]
            while len(screenshots) < 4:
                screenshots.append('N/A')
            
            metadata = {
                'Niche': app_info.get('primaryGenreName', ''),
                'App Name': app_info.get('trackName', ''),
                'Logo URL': app_info.get('artworkUrl512', app_info.get('artworkUrl100', '')),
                'Install Count': self.estimate_install_count(review_count),
                'Release Date': release_date.strftime('%B %d, %Y'),
                'Rating': formatted_rating,
                'Review Count': formatted_review_count,
                'App Link': app_info.get('trackViewUrl', ''),
                'Developer': app_info.get('artistName', ''),
                'Description': description,
                'Keywords': keywords,
                'Screenshot 1': screenshots[0],
                'Screenshot 2': screenshots[1],
                'Screenshot 3': screenshots[2],
                'Screenshot 4': screenshots[3],
            }
            
            print(f"✓ App {app_id}: {metadata['App Name']} - Released {days_since_release} days ago")
            return metadata
        
        except Exception as e:
            print(f"Error fetching metadata for app {app_id}: {e}")
            return None
    
    def search_all_categories(self, categories=None, countries=None, output_file='app_store_apps.csv'):
        """
        Search apps across multiple categories and countries and save immediately
        
        :param categories: List of category names (uses all if None)
        :param countries: List of country codes (uses default if None)
        :param output_file: Filename to save results to incrementally
        """
        if categories is None:
            categories = list(CATEGORIES.keys())
        if countries is None:
            countries = COUNTRIES

        self.load_existing_csv(output_file)
        
        # Collect all unique app IDs first
        print(f"\n{'='*70}")
        print(f"PHASE 1: Searching for apps in {len(categories)} categories across {len(countries)} countries")
        print(f"{'='*70}\n")
        
        # Map app_id -> category_name so we can stamp the correct niche later
        app_id_to_category = {}
        
        for category_name in categories:
            if category_name not in CATEGORIES:
                print(f"⚠ Warning: Unknown category '{category_name}', skipping...")
                continue
                
            category_id = CATEGORIES[category_name]
            print(f"\n📂 Searching category: {category_name} (ID: {category_id})")
            
            for country in countries:
                print(f"  → Country: {country.upper()}", end=' ')
                app_ids = self.search_by_category(category_id, country)
                new_ids = 0
                for aid in app_ids:
                    if aid not in app_id_to_category:
                        app_id_to_category[aid] = category_name
                        new_ids += 1
                print(f"({len(app_ids)} found, {new_ids} new)")
                time.sleep(0.5)  # Rate limiting
        
        print(f"\n{'='*70}")
        print(f"PHASE 2: Fetching metadata for {len(app_id_to_category)} unique apps")
        print(f"Filtering for apps released within the last {self.days_threshold} days")
        print(f"Merging results into existing data from {output_file}")
        print(f"{'='*70}\n")
        
        # Fetch metadata for each unique app ID
        total = len(app_id_to_category)
        for i, (app_id, niche_name) in enumerate(app_id_to_category.items(), 1):
            print(f"[{i}/{total}] ", end='')
            metadata = self.get_app_metadata(app_id)
            
            if metadata:
                # Use the category we searched, not primaryGenreName, so niche names match Play Store
                metadata['Niche'] = niche_name
                app_link = metadata.get('App Link', '').strip()
                if app_link:
                    self.all_apps[app_link] = metadata
            
            time.sleep(0.3)  # Rate limiting
        
        print(f"\n{'='*70}")
        print(f"✓ Found {len(self.all_apps)} apps released within the last {self.days_threshold} days")
        print(f"✓ Merged results ready to write to {output_file}")
        print(f"{'='*70}\n")
    
    def save_to_csv(self, filename='app_store_apps.csv'):
        """
        Save app details to CSV
        
        :param filename: Output CSV filename
        """
        if not self.all_apps:
            print("No apps to save.")
            return
        
        apps_list = list(self.all_apps.values())
        
        # Sort by app name alphabetically
        apps_list.sort(key=lambda x: x['App Name'])
        
        with open(filename, 'w', newline='', encoding='utf-8') as file:
            dict_writer = csv.DictWriter(file, self.fieldnames)
            dict_writer.writeheader()
            dict_writer.writerows(apps_list)
        
        print(f"✓ Saved {len(apps_list)} apps to {filename}")
        
        # Print summary statistics
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        print(f"Total apps found: {len(apps_list)}")
        print(f"Date range: Last {self.days_threshold} days")
        print(f"{'='*70}\n")


def main():
    # Initialize searcher (90 days threshold)
    searcher = AppStoreSearcher(days_threshold=90)
    
    # Select categories to search (you can customize this list)
    categories_to_search = [
        'Utilities',
        'Productivity',
        'Lifestyle',
        'Entertainment',
        'Photo & Video',
        'Health & Fitness',
        'Social Networking',
        'Games',
        'Music',
        'Food & Drink',
    ]
    
    # Or search all categories:
    # searcher.search_all_categories()
    
    # Search selected categories across all countries
    searcher.search_all_categories(
        categories=categories_to_search,
        countries=COUNTRIES,
        output_file='app_store_apps.csv'
    )
    
    # Sort results at the end
    searcher.save_to_csv('app_store_apps.csv')


if __name__ == '__main__':
    main()
