import scrapy
import time
import json
from eurovision_scraper.spiders.country_data import country_map


class EurovisionSpider(scrapy.Spider):
    '''
        Fetch all ESC voting data from the wiki article for each contest year and return it 
        the following CSV format:
        
        year,round,country,votingCountry,voteType,points
        
        e.g.
        1957,f,be,ch,t,1 
        
        Note that two character country codes are used except for when the voting source 
        is 'Rest of the World', which is represented with the three character code 'row'
    '''
    custom_settings = {
        'FEED_URI': 'eurovision_vote_data.csv',
        'CONCURRENT_REQUESTS': 1
    }
    
    name = 'eurovision_vote'
    start_urls = [f'https://en.wikipedia.org/wiki/Eurovision_Song_Contest_{year}' for year in list(range(1956, 2020)) + list(range(2021, 2024))] # note that we're skipping 2020

    def parse(self, response):

        #time.sleep(1)  # 1 second delay between requests

        try:
            year = response.url.split('_')[-1]
            results = []
            
            # parse the different voting results tables
            if int(year) > 2015:
                self.get_post_2015_results(response, year, results)
                
            elif year == '2013':
                self.get_2013_results(response, year, results)
                
            elif int(year) < 2016: 
                self.get_pre_2016_results(response, year, results)
                
            else: 
                raise Exception(f'Invalid year {year}')
                
            # deduplicate results 
            unique_rows = set() 

            for row in results:
                key = tuple(row.values()) 
                if key not in unique_rows:
                    unique_rows.add(key)
                    yield row
            
            #return results
                
        except Exception as e:
            self.logger.error(f"Error parsing {response.url}: {e}")
            raise

    def get_post_2015_results(self, response, year, results):
        '''
            Parse all contest from 2016 on. These articles are generally more consistent than 
            those for previous years
        '''
        
        jury_results = self.parse_table_post_2015(response, year, 'Detailed jury voting results of the final', 'f', 'j')
        results.extend(jury_results)
                
        tele_results = self.parse_table_post_2015(response, year, 'Detailed televoting results of the final', 'f', 'tv')
        results.extend(tele_results)
                
        # semi final 1
        sf_1_jury_results = self.parse_table_post_2015(response, year, 'Detailed jury voting results of semi-final 1', 'sf1', 'j')
        results.extend(sf_1_jury_results)
                
        sf_1_tele_results = self.parse_table_post_2015(response, year, 'Detailed televoting results of semi-final 1', 'sf1', 'tv')
        results.extend(sf_1_tele_results)
                
        # semi final 2
        sf_2_jury_results = self.parse_table_post_2015(response, year, 'Detailed jury voting results of semi-final 2', 'sf2', 'j')
        results.extend(sf_2_jury_results)
                
        sf_2_tele_results = self.parse_table_post_2015(response, year, 'Detailed televoting results of semi-final 2', 'sf2', 'tv')
        results.extend(sf_2_tele_results)


    def parse_table_post_2015(self, response, year, table_header, round_name, vote_type):
        '''
            Returns voting result data if available. First look for a table with the provided
            header name. If none is found, return empty array. Otherwise, parse the country-country
            voting counts. 
            
            The header_ids_adjust is used to account for slight differences in how some tables are 
            structured which can alter the index at which the required column headers (votingCountry) 
            need to be selected 
        '''  
        try:
            
            # some index positioning variables used for parsing tables. these may need to be tweeked 
            header_idx_adjust = -1
            row_idx_adjust = 1
            start_point_idx = 3
             
            # the voting results tables are labeled either via an overhead h2 or a table caption
            table_selector = response.xpath(
                f"//table[contains(@class, 'wikitable') and "
                f"(./preceding::h2[contains(., '{table_header}')] or ./caption[contains(., '{table_header}')])]"
            )

            if not table_selector:
                print(f'No table found for {year} with name "{table_header}"')
                return
                
            table = table_selector[0]
            rows = table.xpath(".//tr")
            
            header_row = rows[0 + row_idx_adjust]
            data_rows = rows[1 + row_idx_adjust:]
                        
            for row in data_rows:
                
                td_adjust, country = self.parse_country(row)

                points = [td.xpath(".//text()").get().strip() if td.xpath(".//text()").get() else None
                          for td in row.xpath(".//td")][start_point_idx + td_adjust:]                         

                for i, point in enumerate(points, start = 2):
                    if point is None or point == '':
                        continue
                
                    voting_country = self.parse_voting_country(header_idx_adjust, header_row, country, i)
                        
                    if voting_country is None:
                        continue
                    
                    yield {
                        'year': year,
                        'round': round_name,
                        'country': country_map.get(country, country),
                        'votingCountry': country_map.get(voting_country, voting_country),
                        'voteType': vote_type, 
                        'points': point.strip()
                    }

        except Exception as e:
            self.logger.error(f"Error in parse_table for {response.url}: {e}")
            return []

    def parse_voting_country(self, header_idx_adjust, header_row, country, i):
        '''
            Return the name of the voting country responsible for the points at the provided 
            index, i. This is taken from the header_row with header_idx_adjust used to adjust 
            the positioning as needed (some tables from certain years have slightly different 
            formatting)
        '''
        
        voting_country_cell = header_row.xpath(f".//th[{i + header_idx_adjust}]")[0]                   
        voting_country = voting_country_cell.xpath(".//text()").get().strip()

        # we should skip this point value in two scenarios 
        # 1. if the voting_country has an html name or is called 'Total score', it's a total count, which we aren't tracking here 
        # 2. if the voting_country and country are the same, skip it (we don't want totals here)
        #print(voting_country)
        if voting_country.startswith('.') or voting_country == 'Total score' or voting_country == country or ' score' in voting_country or voting_country == 'Jury':
            return None

        # represent the 'Rest of the World' vote as the country pseudo-code 'row'
        if voting_country == 'Rest of the World':
            voting_country = 'row'
            
        return voting_country


    def parse_country(self, row):
        '''
            Returns the name of the country being voted for within the provided row. If there's 
            no th element, the country name is in the first td element instead. In that case set 
            the td_adjust variable to 1 instead of 0 so that the points are extracted at the correct 
            index 
        '''
        td_adjust = 0
                
        country_cell = row.xpath(".//th")
                
        if not country_cell:                    # If no <th> elements are found
            country_cell = row.xpath(".//td")   # Get the <td> elements in the current row
                    
            if country_cell:                    # If any <td> elements are found
                country_cell = country_cell[0]  # Take the first <td> element
                td_adjust = 1
        else:                                   # If <th> elements are found
            country_cell = country_cell[0]      # Take the first <th> element
                    
        country = country_cell.xpath(".//text()").get().strip()
                #print(country)
                
        if country == 'Contestants':
            country_cell = row.xpath(".//td")[0]
            td_adjust = 1
            country = country_cell.xpath(".//text()").get().strip()
            
        if country.isnumeric():
            td_adjust = 1
            
        numeric_shift = False
        
        while country == 'Contestants' or country.isnumeric():
            numeric_shift = True
            country_cell = row.xpath(".//th")[td_adjust]
            td_adjust += 1
            country = country_cell.xpath(".//text()").get().strip()

        
        if (numeric_shift):
            td_adjust -= 2
                     
        return td_adjust, country
    
    
    
    def parse_table_pre_2016(self, response, year, table_header, round_name, vote_type, header_idx_adjust):
        '''
            Returns voting result data if available. First look for a table with the provided
            header name. If none is found, return empty array. Otherwise, parse the country-country
            voting counts. 
            
            The header_ids_adjust is used to account for slight differences in how some tables are 
            structured which can alter the index at which the required column headers (votingCountry) 
            need to be selected 
        '''  
        try:
            row_idx_adjust = 0
                
            # the voting results tables are labeled either via an overhead h2 or a table caption
            table_selector = response.xpath(
                f"//table[contains(@class, 'wikitable') and "
                f"(./preceding::h2[contains(., '{table_header}')] or ./caption[contains(., '{table_header}')])]"
            )

            if not table_selector:
                print(f'No table found for {year} with name "{table_header}"')
                return

            table = table_selector[0]
            rows = table.xpath(".//tr")
            
            header_row = rows[0 + row_idx_adjust]
            data_rows = rows[1 + row_idx_adjust:]

            for row in data_rows:
                
                if not row.xpath(".//th"):
                    print(row)
                    continue
                
                country_cell = row.xpath(".//th")[0]
                country = country_cell.xpath(".//text()").get().strip()

                if country == 'Contestants':
                    country_cell = row.xpath(".//th")[1]
                    country = country_cell.xpath(".//text()").get().strip()
                    #print(country)

                points = [td.xpath(".//text()").get().strip() if td.xpath(".//text()").get() else None
                            for td in row.xpath(".//td")]                          

                for i, point in enumerate(points, start=2):
                    if point is None or point == '':
                        continue
                
                    voting_country_cell = header_row.xpath(f".//th[{i + header_idx_adjust}]")
                    
                    if not voting_country_cell:
                        voting_country_cell = header_row.xpath(f".//td[{i + header_idx_adjust}]")
                    
                    if not voting_country_cell:
                        print('skipping ' + country)
                        continue; 
                    
                    voting_country_cell = voting_country_cell[0]
                    
                    voting_country = voting_country_cell.xpath(".//text()").get().strip()

                    # we should skip this point value in two scenarios 
                    # 1. if the voting_country has an html name or is called 'Total score', it's a total count, which we aren't tracking here 
                    # 2. if the voting_country and country are the same, skip it (we don't want totals here)
                    if voting_country.startswith('.') or voting_country == 'Total score' or voting_country == country or ' score' in voting_country or country_map.get(voting_country) == None:
                        continue

                    yield {
                        'year': year,
                        'round': round_name,
                        'country': country_map.get(country, country),
                        'votingCountry': country_map.get(voting_country, voting_country),
                        'voteType': vote_type, 
                        'points': point.strip()
                    }

        except Exception as e:
            self.logger.error(f"Error in parse_table for {response.url}: {e}")
            raise
            return []
        
    def get_pre_2016_results(self, response, year, results):
        '''
            Fetches results from contests up to 2015. There are a few ways that voting results data 
            can be displayed in each wiki article, which is reflected below. 
        '''    
         
        # first try to get the final results from pages where there are also semi-finals
        final_results = self.parse_table_pre_2016(response, year, 'Detailed voting results of the final', 'f', 't', -1)
        results.extend(final_results)

        # if there were no final_results from a semi-final year (2004+), get the final voting results from 
        # the more generically titled results table
        if not final_results or not list(final_results):
            legacy_final_results = self.parse_table_pre_2016(response, year, 'Detailed voting results', 'f', 't', 0)
            results.extend(legacy_final_results)

        # try to get semi-final results (these only exist from 2004 on)
        semi_final1 = self.parse_table_pre_2016(response, year, 'Detailed voting results of semi-final 1', 'sf1', 't', -1)
        results.extend(semi_final1)

        semi_final2 = self.parse_table_pre_2016(response, year, 'Detailed voting results of semi-final 2', 'sf2', 't', -1)
        results.extend(semi_final2)

        # if there were no semi-final 1 and 2 results, try getting semi-final results 
        # using the more generic table label. This captures years where there was 
        # only one semi final (e.g. 2004)
        if not list(semi_final1) and not list(semi_final2):
            semi_final = self.parse_table_pre_2016(response, year, 'Detailed voting results of the semi-final', 'sf', 't', -1)
            results.extend(semi_final)
            
            
    def get_2013_results(self, response, year, results):
        final_results = self.parse_table_pre_2016(response, year, 'Final voting results', 'f', 't', 0)
        results.extend(final_results)
            
        semi_final1 = self.parse_table_pre_2016(response, year, 'Semi-final 1 voting results', 'sf1', 't', 0)
        results.extend(semi_final1)

        semi_final2 = self.parse_table_pre_2016(response, year, 'Semi-final 2 voting results', 'sf2', 't', 0)
        results.extend(semi_final2)
            #raise

