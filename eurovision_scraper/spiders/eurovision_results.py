import scrapy
import os

class EurovisionResultsSpider(scrapy.Spider):
    """
    A Scrapy spider to scrape Eurovision Song Contest results from Wikipedia.
    This spider supports scraping for specific years or ranges of years provided
    as a command-line argument. It also handles CSV output, appending new data
    to an existing file without duplicating the header row.
    """
    name = 'eurovision_results'

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        """
        This class method is used by Scrapy to create your spider.
        It's the ideal place to access settings and pass them to the spider's __init__.
        """
        output_file = 'eurovision_result_data.csv'
        file_exists_and_is_not_empty = os.path.exists(output_file) and os.path.getsize(output_file) > 0

        crawler.settings.set('FEEDS', {
            output_file: {
                'format': 'csv',
                'fields': ['year', 'country', 'runningOrder', 'place'],
                'overwrite': not file_exists_and_is_not_empty,
            }
        })

        spider = cls(*args, **kwargs)
        spider._set_crawler(crawler)
        return spider

    def __init__(self, years=None, *args, **kwargs):
        super(EurovisionResultsSpider, self).__init__(*args, **kwargs)

        if years:
            self.years_to_scrape = self._parse_years(years)
        else:
            self.years_to_scrape = list(range(1956, 2020)) + list(range(2021, 2025))

        self.start_urls = [f'https://en.wikipedia.org/wiki/Eurovision_Song_Contest_{year}'
                           for year in self.years_to_scrape]

        self.logger.info(f"Scraping Eurovision results for years: {sorted(self.years_to_scrape)}")


    def _parse_years(self, years_input):
        years = set()
        parts = years_input.split(',')

        for part in parts:
            part = part.strip()
            if '-' in part:
                try:
                    start, end = part.split('-')
                    for year in range(int(start.strip()), int(end.strip()) + 1):
                        if year != 2020:
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
        
        # ✨ NEW: Added a specific rule for the 2025 page structure
        elif year == '2025':
            # On the 2025 page, the table is for participants and has a different caption
            table = response.xpath('//table[contains(@class, "wikitable") and contains(./caption, "Participants in the")]')
            
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

        # The rest of the logic can handle multiple tables (e.g., semi-finals and final)
        for a_table in table:
            for row in a_table.xpath('.//tr[position() > 1]'):
                running_order = row.xpath('./th/text()').get()
                if not running_order or not running_order.strip().isdigit():
                    continue

                country = row.xpath('./td[1]//a[@title or text()]/text()').get()
                if not country:
                    continue

                place = row.xpath('./td[last()]//text()').get()

                yield {
                    'year': year,
                    'country': country.strip(),
                    'runningOrder': running_order.strip(),
                    'place': place.strip() if place else ''
                }