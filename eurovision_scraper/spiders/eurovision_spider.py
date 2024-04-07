import scrapy
import time

class EurovisionSpider(scrapy.Spider):
    name = 'eurovision'
    start_urls = ['https://en.wikipedia.org/wiki/Eurovision_Song_Contest_{}'.format(year) for year in range(1957, 2024)]

    def parse(self, response):
        try:
            year = response.url.split('_')[-1]

            # Find the "Detailed voting results" table
            table = response.xpath("//table[contains(@class, 'wikitable') and ./preceding::h2[contains(., 'Detailed voting results')]]")[0]
            
            rows = table.xpath(".//tr")
            
            header_row = rows[0]
            data_rows = rows[2:]
            
            for row in data_rows:
                print('##')
                print(row)
                print('##')
                country_cell = row.xpath(".//th")[0]
                country = country_cell.xpath(".//text()").get().strip()
                
                points = row.xpath(".//td/text()").getall()
                
                for i, point in enumerate(points, start=2):

                    voting_country_cell = header_row.xpath(f".//th[{i}]")[0]
                    voting_country = voting_country_cell.xpath(".//text()").get().strip()
                    
                    if voting_country.startswith('.'):
                        voting_country = 'TOTAL'
                    
                    yield {
                        'year': year,
                        'round': 'final',
                        'votingCountry': voting_country,
                        'country': country,
                        'points': point.strip() or '0'
                    }

        except IndexError:
            self.logger.info(f"No 'Detailed voting results' table found for {response.url}")
        except Exception as e:
            self.logger.error(f"Error parsing {response.url}: {e}")
            
        time.sleep(1)  # 2 second delay between requests

