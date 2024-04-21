# eurovision-scraper
A web-scraper for collecting publicly available data from Wikipedia on the Eurovision Song Contest.

## getting started

1. install [scrapy](https://scrapy.org/): `pip install scrapy`
2. execute scraper: 
    
    a. up to 2015
    * `scrapy crawl eurovision` or
    * `python -m scrapy crawl eurovision`

    b. after 2015
    * `scrapy crawl eurovision_post_15` or
    * `python -m scrapy crawl eurovision_post_15`
3. data is saved to `/eurovision_data.csv`