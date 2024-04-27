# eurovision-scraper
A web-scraper for collecting publicly available data from Wikipedia on the Eurovision Song Contest.

## getting started

1. install [scrapy](https://scrapy.org/): `pip install scrapy`
2. execute scraper 
    * voting data saved to `/eurovision_vote_data.csv`
        * `scrapy crawl eurovision_vote` or
        * `python -m scrapy crawl eurovision_vote`

   * participant data saved to `/eurovision_participant_data.csv`
        * `scrapy crawl eurovision_participant` or
        * `python -m scrapy crawl eurovision_participant`
