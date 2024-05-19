import scrapy

class EurovisionResultsSpider(scrapy.Spider):
    name = 'eurovision_results'
    custom_settings = {
        'FEED_URI': 'eurovision_result_data.csv',
        'FEED_EXPORT_FIELDS': ['year', 'country', 'runningOrder', 'place'],
    }

    # skipping 2020
    start_urls = [f'https://en.wikipedia.org/wiki/Eurovision_Song_Contest_{year}' for year in list(range(1956, 2020)) + list(range(2021, 2025))]

    def parse(self, response):
        year = response.url.split('_')[-1]

        if year == '2021':
            # Find the table with the header containing "R/O" and no legend above it
            table = response.xpath('//p[contains(., "closure of the voting window")]/following-sibling::table[1]')
        else:
            # Find the table with the caption starting with "Results of the Eurovision Song Contest"
            table = response.xpath('//table[contains(./caption, "Results of the Eurovision Song Contest")]')

            # The table name format changed after the 2003 articles
            if not table:
                table = response.xpath('//table[contains(./caption, "esults of the final of the Eurovision Song Contest")]')

            # If the table is not found using the caption, try finding it using the legend div
            if not table:
                table = response.xpath('//div[@class="legend"][contains(., "Winner")]/following-sibling::table[1][.//th[contains(., "R/O")]]')

            if not table:
                table = response.xpath('//div[@class="legend"][contains(., "Winner")]/following-sibling::table[1]')

        # Extract data from each row of the table
        for row in table.xpath('.//tr[position() > 1]'):
            # Skip the header row
            running_order = row.xpath('./th/text()').get()
            if running_order:
                running_order = running_order.strip()
            else:
                continue

            country = row.xpath('./td[1]//a[@title or text()]/text()').get()
            if country:
                country = country.strip()
            else:
                continue

            place = row.xpath('./td[last()]//text()').get().strip()

            yield {
                'year': year,
                'country': country,
                'runningOrder': running_order,
                'place': place if place else ''
            }