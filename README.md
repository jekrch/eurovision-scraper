# Eurovision Scraper :pick:

Eurovision Scraper is a web scraper designed to collect publicly available data from Wikipedia about the Eurovision Song Contest. It gathers voting results and participant details from all contest years (1956 to the present). This can be useful for analysis, visualizations, or building applications related to the Eurovision Song Contest. 

## Prerequisites

- Python 3.x
- [Scrapy](https://scrapy.org/) (can be installed via `pip install scrapy`)

## Installation

1. Clone the repository: `git clone https://github.com/jekrch/eurovision-scraper.git`
2. Navigate to the project directory: `cd eurovision-scraper`
3. Install the required dependencies: `pip install -r requirements.txt`

## Usage

### Direct Execution

1. Execute the voting data scraper: `scrapy crawl eurovision_vote`
   - voting data is saved to `/eurovision_vote_data.csv`

2. Execute the participant data scraper: `scrapy crawl eurovision_participant`
   - participant data is saved to `/eurovision_participant_data.csv`

3. Execute the result data scraper: `scrapy crawl eurovision_results`
   - result data is saved to `/eurovision_result_data.csv`

### Docker

1. Build the Docker image: `docker-compose build`
2. Run the scraper: `docker-compose up`
   - voting data is saved to `/eurovision_vote_data.csv` 
   - participant data is saved to `eurovision_participant_data.csv`
   - result data is saved to `eurovision_result_data.csv`

## Contributing

Contributions are welcome! If you find any issues or have suggestions for improvements, please open an issue or submit a pull request.

## License

This project is licensed under the [MIT License](LICENSE).



## References

- [Eurovision Song Contest on Wikipedia](https://en.wikipedia.org/wiki/Eurovision_Song_Contest)
