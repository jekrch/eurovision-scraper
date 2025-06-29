import scrapy
import os

class EurovisionResultsSpider(scrapy.Spider):
    """
    A Scrapy spider to scrape Eurovision Song Contest results from Wikipedia.

    This spider supports scraping for specific years or ranges of years provided
    as a command-line argument. It also handles CSV output, appending new data
    to an existing file without duplicating the header row.

    Attributes:
        name (str): The name of the spider.

    How to Run:
      - Scrape all default years (1956-2024, excluding 2020) and create a new file:
        scrapy crawl eurovision_results

      - Scrape a single year and append to the file:
        scrapy crawl eurovision_results -a years=2024

      - Scrape a range of years:
        scrapy crawl eurovision_results -a years="2015-2019"

      - Scrape multiple specific years and ranges:
        scrapy crawl eurovision_results -a years="2005,2010-2012,2023"
    """
    name = 'eurovision_results'

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        """
        This class method is used by Scrapy to create your spider.
        It's the ideal place to access settings and pass them to the spider's __init__.
        """
        output_file = 'eurovision_result_data.csv'
        # Check if the file exists and has content to avoid writing a duplicate header.
        file_exists_and_is_not_empty = os.path.exists(output_file) and os.path.getsize(output_file) > 0

        # Configure the FEEDS setting to control output.
        # This will append to the file if it exists and has content.
        crawler.settings.set('FEEDS', {
            output_file: {
                'format': 'csv',
                'fields': ['year', 'country', 'runningOrder', 'place'],
                'overwrite': not file_exists_and_is_not_empty,
            }
        })

        # Instantiate the spider and pass all original arguments along.
        spider = cls(*args, **kwargs)
        spider._set_crawler(crawler)
        return spider

    def __init__(self, years=None, *args, **kwargs):
        super(EurovisionResultsSpider, self).__init__(*args, **kwargs)

        # --- Year Parsing and URL Generation ---
        if years:
            self.years_to_scrape = self._parse_years(years)
        else:
            # Default to all years if none are provided
            self.years_to_scrape = list(range(1956, 2020)) + list(range(2021, 2025))

        self.start_urls = [f'https://en.wikipedia.org/wiki/Eurovision_Song_Contest_{year}'
                           for year in self.years_to_scrape]

        self.logger.info(f"Scraping Eurovision results for years: {sorted(self.years_to_scrape)}")


    def _parse_years(self, years_input):
        """
        Parses various year input formats into a list of valid Eurovision years.
        - Single year: "2023"
        - Range: "2015-2020"
        - Comma-separated: "2015,2017,2019"
        - Mixed: "2015-2017,2021"
        """
        years = set()
        parts = years_input.split(',')

        for part in parts:
            part = part.strip()
            if '-' in part:
                try:
                    start, end = part.split('-')
                    for year in range(int(start.strip()), int(end.strip()) + 1):
                        if year != 2020: # Skip the cancelled year
                            years.add(year)
                except ValueError:
                    self.logger.warning(f"Invalid year range format: '{part}'")
            else:
                try:
                    year = int(part)
                    if year != 2020:
                        years.add(year)
                except ValueError:
                    self.logger.warning(f"Invalid year format: '{part}'")

        valid_years = {year for year in years if 1956 <= year <= 2025}
        invalid_years = years - valid_years
        for year in invalid_years:
            self.logger.warning(f"Year {year} is outside Eurovision history (1956-2025).")

        return sorted(list(valid_years))

    def parse(self, response):
        year = response.url.split('_')[-1]
        table = None

        # Locator logic for different Wikipedia page layouts over the years
        if year == '2021':
            table = response.xpath('//p[contains(., "closure of the voting window")]/following-sibling::table[1]')

        elif year == '2025':
            # For 2025, the final results table has a specific caption.
            self.logger.info("Using 2025-specific selector for the final results table.")
            table = response.xpath('//table[contains(./caption, "Participants of the final")]')

        else:
            # Fallback for other years
            table = response.xpath('//table[contains(./caption, "Results of the Eurovision Song Contest")]')
            if not table:
                table = response.xpath('//table[contains(./caption, "esults of the final of the Eurovision Song Contest")]')
            if not table:
                table = response.xpath('//div[@class="legend"][contains(., "Winner")]/following-sibling::table[1][.//th[contains(., "R/O")]]')
            if not table:
                table = response.xpath('//div[@class="legend"][contains(., "Winner")]/following-sibling::table[1]')

        if not table:
            self.logger.warning(f"Could not find a results table for year {year}. The page structure may have changed.")
            return

        # Handle cases where multiple tables might be returned by a selector
        for a_table in table:
            # Iterate through each data row (tr) in the table body, skipping the header
            for row in a_table.xpath('.//tr[position() > 1]'):
                # Extracts running order from the first header cell (th) of the row
                running_order = row.xpath('./th[1]/text()').get()
                if not running_order or not running_order.strip().isdigit():
                    continue

                # Extracts country from the first data cell (td) of the row
                country = row.xpath('./td[1]//a[@title or text()]/text()').get()
                if not country:
                    continue

                # Extracts place from the last data cell (td) of the row
                place = row.xpath('./td[last()]//text()').get()

                yield {
                    'year': year,
                    'country': country.strip(),
                    'runningOrder': running_order.strip(),
                    'place': place.strip() if place else ''
                }