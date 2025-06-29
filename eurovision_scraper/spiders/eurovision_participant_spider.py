import scrapy
import time
from eurovision_scraper.spiders.country_data import country_map

class EurovisionSpider(scrapy.Spider):
    custom_settings = {
        'FEED_URI': 'eurovision_participant_data.csv',
        'FEED_EXPORT_FIELDS': ['year', 'country', 'broadcaster', 'artist', 'artistWikiUrl', 'song', 'songWikiUrl', 'language', 'songwriters', 'conductors'],
        'FEED_EXPORT_EMPTY_FIELDS': False
    }

    name = 'eurovision_participant'
    
    def __init__(self, years=None, debug=False, *args, **kwargs):
        super(EurovisionSpider, self).__init__(*args, **kwargs)
        
        self.debug = debug.lower() == 'true' if isinstance(debug, str) else debug
        
        if years:
            # Parse the years parameter
            self.years_to_scrape = self._parse_years(years)
        else:
            # Default years (1956-2019, 2021-2024, skipping 2020)
            self.years_to_scrape = list(range(1956, 2020)) + list(range(2021, 2025))
        
        # Generate start URLs based on years
        self.start_urls = [f'https://en.wikipedia.org/wiki/Eurovision_Song_Contest_{year}' 
                          for year in self.years_to_scrape]
        
        self.logger.info(f"Scraping Eurovision data for years: {sorted(self.years_to_scrape)}")
    
    def _parse_years(self, years_input):
        """
        Parse various year input formats:
        - Single year: "2023"
        - Range: "2015-2020"
        - Multiple years: "2015,2017,2019"
        - Multiple ranges: "2015-2017,2020-2023"
        """
        years = set()
        
        # Split by comma for multiple entries
        parts = years_input.split(',')
        
        for part in parts:
            part = part.strip()
            
            # Check if it's a range
            if '-' in part:
                try:
                    start, end = part.split('-')
                    start_year = int(start.strip())
                    end_year = int(end.strip())
                    
                    # Add all years in the range (inclusive)
                    for year in range(start_year, end_year + 1):
                        # Skip 2020 (no contest that year)
                        if year != 2020:
                            years.add(year)
                except ValueError:
                    self.logger.warning(f"Invalid year range format: {part}")
            else:
                # Single year
                try:
                    year = int(part)
                    # Skip 2020
                    if year != 2020:
                        years.add(year)
                except ValueError:
                    self.logger.warning(f"Invalid year format: {part}")
        
        # Validate years are within Eurovision history
        valid_years = set()
        for year in years:
            if 1956 <= year <= 2025:  # Adjust upper bound as needed
                valid_years.add(year)
            else:
                self.logger.warning(f"Year {year} is outside Eurovision history (1956-2025)")
        
        return sorted(list(valid_years))

    def parse(self, response):
        #time.sleep(1)  # 1 second delay between requests
        try:
            year = response.url.split('_')[-1]
            results = []
            
            # Debug mode: save page HTML
            if self.debug:
                filename = f'debug_eurovision_{year}.html'
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                self.logger.info(f"Debug: Saved page HTML to {filename}")

            # Try different table selectors for different page formats
            table_selectors = [
                # Standard participant table with caption
                '//table[contains(@class, "wikitable") and contains(./caption, "Participants of the Eurovision Song Contest")]',
                # Eurovision 2025+ format
                '//table[contains(@class, "wikitable") and contains(./caption, "Eurovision Song Contest") and contains(./caption, "participants")]',
                # Table with participant/competing countries header
                '//table[contains(@class, "wikitable") and (.//th[contains(text(), "Participating countries")] or .//th[contains(text(), "Competing countries")])]',
                # Any wikitable after "Participants" or "Competing entries" heading
                '//h2[span[contains(text(), "Participants")] or span[contains(text(), "Competing entries")]]/following-sibling::*//table[contains(@class, "wikitable")][1]',
                # Sortable wikitable (common format)
                '//table[contains(@class, "wikitable") and contains(@class, "sortable")]'
            ]
            
            table = None
            for selector in table_selectors:
                table = response.xpath(selector)
                if table:
                    self.logger.info(f"Found table using selector: {selector}")
                    break
            
            if not table:
                self.logger.warning(f"No participant table found for year {year}")
                # In debug mode, list all tables found
                if self.debug:
                    all_tables = response.xpath('//table[contains(@class, "wikitable")]')
                    self.logger.info(f"Debug: Found {len(all_tables)} wikitables on page")
                    for i, t in enumerate(all_tables):
                        caption = t.xpath('./caption/text()').get(default='No caption')
                        self.logger.info(f"  Table {i+1}: {caption}")
                return results
            
            # skip header row
            rows = table.xpath('.//tr[position() > 1]')  
            self.logger.info(f"Found {len(rows)} data rows for year {year}")

            # Check if table has conductors column by looking at headers
            headers = table.xpath('.//tr[1]//th/text()').getall()
            has_conductors = any('conductor' in h.lower() for h in headers)
            self.logger.debug(f"Table headers: {headers}, has_conductors: {has_conductors}")
            
            for idx, row in enumerate(rows):
                # Try multiple country selectors
                country = row.xpath('./th//a[contains(@title, "in the Eurovision Song Contest")]/text()').get(default='').strip()
                if not country:
                    # Alternative: first link in th cell
                    country = row.xpath('./th[1]//a/text()').get(default='').strip()
                if not country:
                    # Alternative: direct text in th cell
                    country = row.xpath('./th[1]//text()').get(default='').strip()
                
                if not country:
                    self.logger.debug(f"Row {idx+1}: No country found, skipping")
                    continue  # skip rows without country

                self.logger.debug(f"Row {idx+1}: Processing country {country}")

                # Adjust column indices based on whether conductors column exists
                # Broadcaster - get link text or direct text
                broadcaster = row.xpath('./td[1]//a/text()').get(default='').strip()
                if not broadcaster:
                    broadcaster = row.xpath('./td[1]//text()').get(default='').strip()
                
                # Artist - get text or link text
                artist = row.xpath('./td[2]//a/text()').get(default='').strip()
                if not artist:
                    artist = row.xpath('./td[2]//text()').get(default='').strip()
                artist_url = row.xpath('./td[2]//a/@href').get(default='')

                song_element = row.xpath('./td[3]')
                # Try to get the song link text first
                song = song_element.xpath('.//a/text()').get(default='').strip()
                if not song:
                    # Get all text, clean up quotes
                    song = song_element.xpath('string(.)').get(default='').strip()
                # Remove surrounding quotes if present
                song = song.strip('"').strip('"').strip('"')
                song_url = song_element.xpath('.//a/@href').get(default='')

                # Language - handle multiple formats and clean up
                language_element = row.xpath('./td[4]')
                # Get all text nodes, excluding reference superscripts
                language_texts = language_element.xpath('.//text()[not(parent::sup)]').getall()
                language = ', '.join([t.strip() for t in language_texts if t.strip()])
                if not language:
                    # Fallback to all text
                    language = language_element.xpath('string(.)').get(default='').strip()
                
                # For songwriters, handle both list format and plain text
                songwriters_element = row.xpath('./td[5]')
                # Try the hlist div format first (2025 style)
                songwriters_list = songwriters_element.xpath('.//div[contains(@class, "hlist")]//li//text()').getall()
                if not songwriters_list:
                    # Try regular li elements
                    songwriters_list = songwriters_element.xpath('.//li//text()').getall()
                
                if songwriters_list:
                    songwriters = '|'.join(songwriters_list).strip()
                else:
                    # Try getting all text if no list structure
                    songwriters = '|'.join(songwriters_element.xpath('.//text()').getall()).strip()
                
                # Conductors only if column exists
                conductors = ''
                if has_conductors:
                    conductors = row.xpath('./td[6]//text()').get(default='').strip()
                    if conductors.startswith('['):
                        conductors = ''

                result = {
                    'year': year,
                    'country': country_map.get(country, country),
                    'broadcaster': broadcaster,
                    'artist': artist,
                    'artistWikiUrl': response.urljoin(artist_url) if artist_url else '',
                    'song': song,
                    'songWikiUrl': response.urljoin(song_url) if song_url else '',
                    'language': language,
                    'songwriters': songwriters,
                    'conductors': conductors
                }
                results.append(result)

            self.logger.info(f"Year {year}: Found {len(results)} participants")
            return results

        except Exception as e:
            self.logger.error(f"Error parsing {response.url}: {e}")
            raise