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
    # skipping 2020
    start_urls = [f'https://en.wikipedia.org/wiki/Eurovision_Song_Contest_{year}' for year in list(range(1956, 2020)) + list(range(2021, 2024))]

    def parse(self, response):
        #time.sleep(1)  # 1 second delay between requests
        try:
            year = response.url.split('_')[-1]
            results = []

            # fetch the participant table 
            table = response.xpath('//table[contains(@class, "wikitable") and contains(./caption, "Participants of the Eurovision Song Contest")]')
            
            # skip header row
            rows = table.xpath('.//tr[position() > 1]')  

            for row in rows:
                country = row.xpath('./th//a[contains(@title, "in the Eurovision Song Contest")]/text()').get(default='').strip()
                if not country:
                    continue  # skip rows without country

                broadcaster = row.xpath('./td[1]//text()').get(default='').strip()
                artist = row.xpath('./td[2]//text()').get(default='').strip()
                artist_url = row.xpath('./td[2]//a/@href').get(default='')

                song_element = row.xpath('./td[3]')
                song = song_element.xpath('string(.)').get(default='').strip().strip('"')
                song_url = song_element.xpath('.//a/@href').get(default='')

                language = row.xpath('./td[4]//text()').get(default='').strip()
                songwriters = '|'.join(row.xpath('./td[5]//li//text()').getall()).strip()
                conductors = row.xpath('./td[6]//text()').get(default='').strip()

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
                    'conductors': conductors if not conductors.startswith('[') else ''
                }
                results.append(result)

            return results

        except Exception as e:
            self.logger.error(f"Error parsing {response.url}: {e}")
            raise