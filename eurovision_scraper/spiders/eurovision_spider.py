import scrapy
import time
from eurovision_scraper.spiders.country_data import country_map


class EurovisionSpider(scrapy.Spider):
    name = 'eurovision'
    start_urls = [f'https://en.wikipedia.org/wiki/Eurovision_Song_Contest_{year}' for year in range(1957, 2024)]

    def parse(self, response):

        time.sleep(1)  # 1 second delay between requests

        try:
            year = response.url.split('_')[-1]
            results = []

            # there are a few ways that voting results data can be displayed in 
            # each wiki article, which is reflected below. 

            # first try to get the final results from pages where there are also semi-finals
            final_results = self.parse_table(response, year, 'Detailed voting results of the final', 'final', -1)
            results.extend(final_results)

            # if there were no final_results from a semi-final year (2004+), get the final voting results from 
            # the more generically titled results table
            if not final_results or not list(final_results):
                legacy_final_results = self.parse_table(response, year, 'Detailed voting results', 'final', 0)
                results.extend(legacy_final_results)

            # try to get semi-final results (these only exist from 2004 on)
            semi_final1 = self.parse_table(response, year, 'Detailed voting results of semi-final 1', 'semi-final 1', -1)
            results.extend(semi_final1)

            semi_final2 = self.parse_table(response, year, 'Detailed voting results of semi-final 2', 'semi-final 2', -1)
            results.extend(semi_final2)

            # if there were no semi-final 1 and 2 results, try getting semi-final results 
            # using the more generic table label. This captures years where there was 
            # only one semi final (e.g. 2004)
            if not list(semi_final1) and not list(semi_final2):
                semi_final = self.parse_table(response, year, 'Detailed voting results of the semi-final', 'semi-final', -1)
                results.extend(semi_final)

            return results
        except Exception as e:
            self.logger.error(f"Error parsing {response.url}: {e}")
            raise

    def parse_table(self, response, year, table_header, round_name, header_idx_adjust):
        '''
            Returns voting result data if available. First look for a table with the provided
            header name. If none is found, return empty array. Otherwise, parse the country-country
            voting counts. 
            
            The header_ids_adjust is used to account for slight differences in how some tables are 
            structured which can alter the index at which the required column headers (votingCountry) 
            need to be selected 
        '''  
        try:
            # the voting results tables are labeled either via an overhead h2 or a table caption
            table_selector = response.xpath(
                f"//table[contains(@class, 'wikitable') and "
                f"(./preceding::h2[contains(., '{table_header}')] or ./caption[contains(., '{table_header}')])]"
            )
            if not table_selector:
                self.logger.info(f"No '{table_header}' table found for {response.url}")
                return []

            table = table_selector[0]
            rows = table.xpath(".//tr")
            header_row = rows[0]
            data_rows = rows[1:]

            for row in data_rows:
                country_cell = row.xpath(".//th")[0]
                country = country_cell.xpath(".//text()").get().strip()

                if country == 'Contestants':
                    country_cell = row.xpath(".//th")[1]
                    country = country_cell.xpath(".//text()").get().strip()
                    print(country)

                points = [td.xpath(".//text()").get().strip() if td.xpath(".//text()").get() else None
                          for td in row.xpath(".//td")]

                for i, point in enumerate(points, start=2):
                    if point is None or point == '':
                        continue

                    voting_country_cell = header_row.xpath(f".//th[{i + header_idx_adjust}]")[0]
                    voting_country = voting_country_cell.xpath(".//text()").get().strip()

                    # we should skip this point value in two scenarios 
                    # 1. if the voting_country has an html name or is called 'Total score', it's a total count, which we aren't tracking here 
                    # 2. if the voting_country and country are the same, skip it (we don't want totals here)
                    if voting_country.startswith('.') or voting_country == 'Total score' or voting_country == country:
                        continue

                    yield {
                        'year': year,
                        'round': round_name,
                        'country': country_map.get(country, country),
                        'votingCountry': country_map.get(voting_country, voting_country),
                        'points': point.strip()
                    }

        except Exception as e:
            self.logger.error(f"Error in parse_table for {response.url}: {e}")
            return []