import scrapy
import time # Keep time if used for delays, though not in current parsing logic
import json # Keep json if used elsewhere, though not in current parsing logic
from scrapy.utils.project import get_project_settings
import os
import csv
from scrapy.exceptions import DropItem

# Assuming country_map is in eurovision_scraper/spiders/country_data.py
# If not available, this will need to be created or provided.
try:
    from eurovision_scraper.spiders.country_data import country_map
except ImportError:
    # Placeholder if the country_map module is not found
    country_map = {
        "Czech Republic": "Czechia",
        "Rest of the World": "ROW",
        "San Marino": "SM",
        "United Kingdom": "UK",
        # Add other known mappings here
    }
    print("Warning: country_map not found, using placeholder. Please ensure eurovision_scraper.spiders.country_data.country_map is available.")


class EurovisionSpider(scrapy.Spider):
    '''
    Fetch Eurovision voting data from wiki articles for specified contest years and return it 
    in CSV format: year,round,country,votingCountry,voteType,points
    
    Usage:
    scrapy crawl eurovision_vote -a start_year=1956 -a end_year=2025
    '''
    name = 'eurovision_vote'
    
    def __init__(self, start_year=1956, end_year=2025, *args, **kwargs):
        super(EurovisionSpider, self).__init__(*args, **kwargs)
        self.start_year = int(start_year)
        self.end_year = int(end_year)
        
        # Validate year range
        if self.start_year < 1956 or self.end_year > 2025: 
            raise ValueError("Years must be between 1956 and 2025")
        if self.start_year > self.end_year:
            raise ValueError("Start year must be less than or equal to end year")
            
        # Generate URLs for the specified year range, excluding 2020
        self.start_urls = [
            f'https://en.wikipedia.org/wiki/Eurovision_Song_Contest_{year}'
            for year in range(self.start_year, self.end_year + 1)
            if year != 2020
        ]
        
        # Set custom output filename
        settings = get_project_settings()
        self.output_file = f'eurovision_data_{self.start_year}-{self.end_year}.csv'
        # Ensure CSV exporter uses correct headers if file is new/overwritten
        settings.set('FEED_EXPORT_FIELDS', ['year', 'round', 'country', 'votingCountry', 'voteType', 'points'], priority='cmdline')
        settings.set('FEED_URI', self.output_file, priority='cmdline')
        settings.set('FEED_FORMAT', 'csv', priority='cmdline')
        settings.set('CONCURRENT_REQUESTS', 1, priority='cmdline') 
        
        # Initialize set to track existing entries
        self.existing_entries = set()
        
        # Read existing entries if file exists
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    if reader.fieldnames is None: 
                        self.logger.warning(f"Output file {self.output_file} is empty or not a valid CSV. Starting fresh.")
                    else:
                        required_fields = ['year', 'round', 'country', 'votingCountry', 'voteType', 'points']
                        if not all(field in reader.fieldnames for field in required_fields):
                            self.logger.warning(f"Output file {self.output_file} is missing required columns. Will overwrite or append with correct columns.")
                        else:
                            for row in reader:
                                entry_key = (
                                    row.get('year', ''),
                                    row.get('round', ''),
                                    row.get('country', ''),
                                    row.get('votingCountry', ''),
                                    row.get('voteType', ''),
                                    row.get('points', '')
                                )
                                self.existing_entries.add(entry_key)
            except Exception as e:
                self.logger.error(f"Error reading existing output file {self.output_file}: {e}. Will attempt to overwrite.")
                self.existing_entries.clear()


    def parse(self, response):
        try:
            year = response.url.split('_')[-1]
            year_str = str(year)
            
            results_iterable = [] 
            
            if int(year) > 2015:
                results_iterable = self.get_post_2015_results(response, year_str)
            elif year_str == '2013':
                results_iterable = self.get_2013_results(response, year_str)
            elif int(year) < 2016: 
                results_iterable = self.get_pre_2016_results(response, year_str)
            else: 
                self.logger.error(f'Invalid year logic for {year_str}')
                return

            for row in results_iterable:
                entry_key = (
                    str(row['year']),
                    str(row['round']),
                    str(row['country']),
                    str(row['votingCountry']),
                    str(row['voteType']),
                    str(row['points'])
                )
                
                if entry_key not in self.existing_entries:
                    self.existing_entries.add(entry_key)
                    yield row
                else:
                    self.logger.debug(f"Duplicate entry skipped: {entry_key}")
            
        except Exception as e:
            self.logger.error(f"Error parsing {response.url}: {e}", exc_info=True)


    def get_post_2015_results(self, response, year):
        """
        Parse all contest from 2016 onwards.
        Handles 2025 specifically for its final jury and televote tables.
        """
        if year == '2025':
            self.logger.info(f"Parsing specific 2025 grid tables from: {response.url}")
            
            # Semi-final 1 Grid Table (assumed combined/televote from HTML structure)
            yield from self.parse_table_post_2015(response, year, "Detailed voting results of the first semi-final of the Eurovision Song Contest 2025", 'sf1', 't')
            # Semi-final 2 Grid Table (assumed combined/televote from HTML structure)
            yield from self.parse_table_post_2015(response, year, "Detailed voting results of the second semi-final of the Eurovision Song Contest 2025", 'sf2', 't')
            
            # Final Grid Tables (separate for Jury and Televote for 2025 based on user input)
            self.logger.info(f"Attempting to parse 2025 Final Jury results table.")
            yield from self.parse_table_post_2015(response, year, "Detailed jury voting results of the final of the Eurovision Song Contest 2025", 'f', 'j')
            
            self.logger.info(f"Attempting to parse 2025 Final Televoting results table.")
            yield from self.parse_table_post_2015(response, year, "Detailed televoting results of the final of the Eurovision Song Contest 2025", 'f', 'tv')
            
        else: # Logic for other years (not 2025)
            self.logger.info(f"Attempting to parse standard grid tables for {year} (post-2015 logic) from: {response.url}")
            # Final
            yield from self.parse_table_post_2015(response, year, 'Detailed jury voting results of the final', 'f', 'j')
            yield from self.parse_table_post_2015(response, year, 'Detailed televoting results of the final', 'f', 'tv')
            
            if int(year) < 2023:
                # Semi-final 1 (Jury and Televoting)
                yield from self.parse_table_post_2015(response, year, 'Detailed jury voting results of semi-final 1', 'sf1', 'j')
                yield from self.parse_table_post_2015(response, year, 'Detailed televoting results of semi-final 1', 'sf1', 'tv')
                # Semi-final 2 (Jury and Televoting)
                yield from self.parse_table_post_2015(response, year, 'Detailed jury voting results of semi-final 2', 'sf2', 'j')
                yield from self.parse_table_post_2015(response, year, 'Detailed televoting results of semi-final 2', 'sf2', 'tv')
            else: # 2023 and onwards (real pages, typically televote-only semis, or specific headers)
                yield from self.parse_table_post_2015(response, year, 'Detailed voting results of the first semi-final', 'sf1', 'tv') 
                yield from self.parse_table_post_2015(response, year, 'Detailed voting results of the second semi-final', 'sf2', 'tv')
                # Fallback for more specific 2023+ style headers if the above are too generic
                yield from self.parse_table_post_2015(response, year, 'Detailed voting results of the first semi-final of the Eurovision Song Contest', 'sf1', 'tv')
                yield from self.parse_table_post_2015(response, year, 'Detailed voting results of the second semi-final of the Eurovision Song Contest', 'sf2', 'tv')

    def parse_table_post_2015(self, response, year, table_header_search_term, round_name, vote_type):
        '''
        Returns voting result data if available for post-2015 grid tables.
        '''   
        try:
            header_idx_adjust = -1 # Default adjustment for post-2015 headers
            
            # XPath to find tables:
            # 1. Check for table preceded by an h2/h3 with the specific headline
            # 2. Check for table with a caption containing the specific headline
            # Using contains() for flexibility.
            xpath_query = (
                f"//table[contains(@class, 'wikitable') and ("
                f"preceding-sibling::*[self::h2 or self::h3][1]/span[contains(@class, 'mw-headline') and contains(normalize-space(.), '{table_header_search_term}')] or "
                f"caption[contains(normalize-space(.), '{table_header_search_term}')]"
                f")]"
            )
            table_selector = response.xpath(xpath_query)

            if not table_selector:
                self.logger.info(f'No grid table found for {year} "{round_name}" with header/caption containing "{table_header_search_term}" on {response.url}')
                return

            table = table_selector[0]
            self.logger.info(f"Found grid table for {year} \"{round_name}\" with header/caption containing '{table_header_search_term}'.")
            rows = table.xpath(".//tr")
            
            if len(rows) < 2: # Need at least one header and one data row
                self.logger.warning(f"Grid table for {year} '{table_header_search_term}' has too few rows.")
                return

            # --- Robust Header Row Identification ---
            header_row_for_voting_countries = None
            first_data_row_actual_index = -1

            # Iterate through rows to find the one that contains the voting country names as <th>
            # This row is typically just before the first actual data row.
            for current_row_idx, tr_element in enumerate(rows):
                # Check if this row is a data row (starts with a recipient country)
                _, recipient_country_in_current_row = self.parse_country(tr_element)
                if recipient_country_in_current_row:
                    first_data_row_actual_index = current_row_idx
                    # The header row with voting countries should be directly above this first data row.
                    if current_row_idx > 0:
                        potential_vc_header_row = rows[current_row_idx - 1]
                        # A valid voting country header row has multiple <th> and few/no <td>
                        if len(potential_vc_header_row.xpath("./th")) > 2 and not potential_vc_header_row.xpath("./td"):
                            header_row_for_voting_countries = potential_vc_header_row
                            self.logger.debug(f"Identified voting country header row for '{table_header_search_term}' at table row index {current_row_idx - 1}.")
                            break 
                        # Handle cases where the actual VC header might be two rows up (e.g., if there's a sub-header row like "Jury Vote")
                        elif current_row_idx > 1:
                            potential_vc_header_row_2up = rows[current_row_idx - 2]
                            if len(potential_vc_header_row_2up.xpath("./th")) > 2 and not potential_vc_header_row_2up.xpath("./td"):
                                header_row_for_voting_countries = potential_vc_header_row_2up
                                self.logger.debug(f"Identified voting country header row (2-up) for '{table_header_search_term}' at table row index {current_row_idx - 2}.")
                                break
                    # If first data row is row 0, or no suitable header found above, this is problematic.
                    if not header_row_for_voting_countries:
                         self.logger.warning(f"Could not find a clear voting country header row above the first data row for '{table_header_search_term}'.")
                         return # Cannot proceed without it
            
            if not header_row_for_voting_countries:
                self.logger.warning(f"Failed to identify the header row for voting countries for '{table_header_search_term}'.")
                return
            if first_data_row_actual_index == -1:
                self.logger.warning(f"Failed to identify any data rows for '{table_header_search_term}'.")
                return

            data_rows_elements = rows[first_data_row_actual_index:]
            
            # --- Extract Voting Country Headers ---
            voting_country_headers = []
            # `th_idx` is 0-based index within the `header_row_for_voting_countries`
            for th_idx, th_cell in enumerate(header_row_for_voting_countries.xpath("./th")):
                # `parse_voting_country` expects `i` such that `i + header_idx_adjust` is the target XPath index.
                # We want to target `th[th_idx+1]` (1-based). So `i` should be `th_idx + 1 - header_idx_adjust`.
                current_i_for_parse = (th_idx + 1) - header_idx_adjust
                vc_name = self.parse_voting_country(header_idx_adjust, header_row_for_voting_countries, "dummy_recipient_for_header_parsing", current_i_for_parse)
                if vc_name:
                    # Store the name and its original 0-based index within its own header row
                    voting_country_headers.append({'name': vc_name, 'original_th_idx_in_its_row': th_idx}) 
            
            if not voting_country_headers:
                self.logger.warning(f"No voting country headers identified in grid table {year} '{table_header_search_term}'.")
                return
            self.logger.debug(f"Identified voting country headers for '{table_header_search_term}': {[h['name'] for h in voting_country_headers]}")

            # --- Process Data Rows ---
            for data_row_element in data_rows_elements:
                td_adjust, recipient_country_name = self.parse_country(data_row_element)
                if recipient_country_name is None: 
                    continue

                point_td_elements = data_row_element.xpath(".//td")
                
                # Determine the starting index of actual point columns within the <td> elements of a data row.
                # This needs to skip columns like "Total Score", "Jury Score", "Televote Score" before the grid.
                td_points_column_start_index = 0
                if year == '2025' and round_name == 'f': # Specific for 2025 Final tables
                    # Recipient(th) | Total(td) | Jury(td) | Tele(td) | PtsFromVC1(td)...
                    # If td_adjust is 0 (country in th), points start at td_elements[3] (0-indexed).
                    # If td_adjust is 1 (country in td[0]), points start at td_elements[4].
                    td_points_column_start_index = td_adjust + 3 
                elif year == '2025' and round_name in ['sf1', 'sf2']: # Specific for 2025 SF tables
                    # Recipient(th) | TD(Total Points) | TD(Place) | TD(Pts from VC1)...
                    # If td_adjust is 0, points start at td_elements[2].
                    # If td_adjust is 1, points start at td_elements[3].
                    td_points_column_start_index = td_adjust + 2
                else: # Default for other post-2015 (often Rank, Total Score, then points)
                    td_points_column_start_index = td_adjust + 2 
                
                td_points_column_start_index = max(0, td_points_column_start_index)


                for point_idx_in_vc_list, vc_header_info in enumerate(voting_country_headers):
                    # current_point_td_idx is the 0-based index into point_td_elements
                    current_point_td_idx = td_points_column_start_index + point_idx_in_vc_list
                    
                    if current_point_td_idx < len(point_td_elements):
                        point_cell_td = point_td_elements[current_point_td_idx]
                        point = point_cell_td.xpath("normalize-space(.//text())").get()
                        
                        if not point: 
                            continue
                        if not point.isdigit(): 
                            if point not in ['—', '-', 'X', 'x', '']: 
                                self.logger.debug(f"Skipping non-numeric/non-empty point '{point}' for {recipient_country_name} from {vc_header_info['name']} in {year} {round_name}")
                            continue 
                        
                        mapped_recipient = country_map.get(recipient_country_name, recipient_country_name)
                        mapped_voting_country = country_map.get(vc_header_info['name'], vc_header_info['name'])

                        if mapped_recipient == mapped_voting_country:
                            self.logger.debug(f"Skipping self-vote points: {mapped_recipient} from {mapped_voting_country}, points: {point}")
                            continue
                        
                        yield {
                            'year': str(year),
                            'round': str(round_name),
                            'country': mapped_recipient,
                            'votingCountry': mapped_voting_country,
                            'voteType': str(vote_type), 
                            'points': str(point.strip())
                        }
                    else:
                        self.logger.debug(f"Point cell index {current_point_td_idx} out of bounds for {recipient_country_name} when expecting points from {vc_header_info['name']}")
        
        except Exception as e:
            self.logger.error(f"Error in parse_table_post_2015 for {response.url}, header '{table_header_search_term}': {e}", exc_info=True)
            return

    def parse_voting_country(self, header_idx_adjust, header_row, country_being_voted_for, i):
        """
        Return the name of the voting country. `i` is the column number for XPath.
        """
        xpath_index = i + header_idx_adjust 
        if xpath_index < 1:
            return None

        voting_country_cell_th = header_row.xpath(f"./th[{xpath_index}]")
        voting_country_cell_td = header_row.xpath(f"./td[{xpath_index}]") 
        
        voting_country_cell = None
        if voting_country_cell_th:
            voting_country_cell = voting_country_cell_th[0]
        elif voting_country_cell_td: 
            voting_country_cell = voting_country_cell_td[0]
        else:
            return None
            
        voting_country_name = voting_country_cell.xpath("normalize-space(.//a/text())").get()
        if not voting_country_name: 
            voting_country_name = voting_country_cell.xpath("normalize-space(./descendant-or-self::text()[not(parent::style) and not(parent::script)])").get()

        if not voting_country_name:
            return None
        
        voting_country_name = voting_country_name.strip()

        # More lenient skip_keywords when parsing headers (country_being_voted_for is dummy)
        # Stricter when parsing actual data.
        is_header_parsing = (country_being_voted_for == "dummy_recipient_for_header_parsing")
        
        skip_keywords = [
            'total score', 'total', 'score', 'jury', 'televoting', 'qualifiers', 
            'running order', 'tele', 'combined', 'rank', 'pts.', '(avg)', 'draw',
            'voting procedure used', 'voting procedure used:', 'legend', 'contestants', 'results', 'points',
            '100% televoting', '100% jury vote', 'sum', 'average'
        ]
        if is_header_parsing: # Be more tolerant for headers, actual country names might contain "jury" or "tele" in some contexts
             # For header parsing, we primarily want to skip structural elements like "Total Score", "Rank", etc.
             # Actual country names are less likely to be these exact phrases.
            pass # Keep default skip_keywords, but rely more on structure (being a TH)
        
        voting_country_name_lower = voting_country_name.lower()

        # If it's not header parsing, and the name looks like a country, it's probably okay.
        # If it IS header parsing, we are more strict about what is NOT a country.
        if any(keyword == voting_country_name_lower for keyword in skip_keywords): # Exact match for skip_keywords
             self.logger.debug(f"Skipping '{voting_country_name}' as it matches a skip_keyword. Header parsing: {is_header_parsing}.")
             return None

        if (voting_country_name.startswith('.') or 
            not voting_country_name or
            voting_country_name.isdigit()): 
            self.logger.debug(f"Skipping '{voting_country_name}' due to basic format. Header parsing: {is_header_parsing}.")
            return None
        
        # If it's header parsing, and it's a very long string, it's probably not a country.
        if is_header_parsing and len(voting_country_name.split()) > 4: # Max 4 words for a country name seems reasonable
            self.logger.debug(f"Skipping '{voting_country_name}' (too long) during header parsing.")
            return None


        if voting_country_name == 'Rest of the World':
            return 'ROW' 
            
        return voting_country_name


    def parse_country(self, row_element):
        """
        Returns the name of the country being voted for and td_adjust.
        td_adjust = 0 if country in <th>, 1 if country in first <td>.
        """
        td_adjust = 0
        country_name = None
        
        non_country_row_keywords = [
            'contestants', 'total score', 'rank', 'points', 'jury', 'televote', 
            'voting procedure used', 'voting procedure used:', 'legend', 
            'voting procedure', 'televoting results', 'jury results', 'detailed voting',
            '100% televoting', '100% jury vote', 'sum', 'average', 'r/o', '#',
            'total points', 'place' # Added from 2025 SF table structure
        ]

        th_cells_in_row = row_element.xpath("./th")
        td_cells_in_row = row_element.xpath("./td")

        # If the row has many TH cells and very few TD cells, it's likely a header of voting countries,
        # not a data row for a recipient country.
        if len(th_cells_in_row) > (len(td_cells_in_row) + 1) and len(th_cells_in_row) > 3 : # More than 3 THs and more THs than TDs
            self.logger.debug(f"Skipping row as potential voting country header (many THs): {row_element.get()}")
            return 0, None

        # Try first <th>
        if th_cells_in_row:
            potential_country_th_a = th_cells_in_row[0].xpath("normalize-space(.//a/text())").get()
            if potential_country_th_a:
                country_name = potential_country_th_a
            else: 
                potential_country_th_text = th_cells_in_row[0].xpath("normalize-space(./descendant-or-self::text()[not(parent::style) and not(parent::script)])").get()
                if potential_country_th_text:
                     country_name = potential_country_th_text
            
            if country_name:
                country_name_lower = country_name.lower().strip()
                if country_name_lower.isdigit() or any(keyword == country_name_lower for keyword in non_country_row_keywords): # Exact match for keywords
                    country_name = None 

            # If not found or invalid in first <th>, try second <th>
            if not country_name and len(th_cells_in_row) > 1:
                potential_country_th2_a = th_cells_in_row[1].xpath("normalize-space(.//a/text())").get()
                if potential_country_th2_a:
                    country_name = potential_country_th2_a
                else:
                    potential_country_th2_text = th_cells_in_row[1].xpath("normalize-space(./descendant-or-self::text()[not(parent::style) and not(parent::script)])").get()
                    if potential_country_th2_text:
                        country_name = potential_country_th2_text
                
                if country_name:
                    country_name_lower = country_name.lower().strip()
                    if country_name_lower.isdigit() or any(keyword == country_name_lower for keyword in non_country_row_keywords):
                        country_name = None
        
        # If still not found in <th>, try first <td>
        if not country_name and td_cells_in_row:
            potential_country_td_a = td_cells_in_row[0].xpath("normalize-space(.//a/text())").get()
            if potential_country_td_a:
                country_name = potential_country_td_a
                td_adjust = 1
            else:
                potential_country_td_text = td_cells_in_row[0].xpath("normalize-space(./descendant-or-self::text()[not(parent::style) and not(parent::script)])").get()
                if potential_country_td_text:
                    country_name = potential_country_td_text
                    td_adjust = 1
            
            if country_name:
                country_name_lower = country_name.lower().strip()
                if country_name_lower.isdigit() or any(keyword == country_name_lower for keyword in non_country_row_keywords):
                    country_name = None
                    td_adjust = 0 

        if not country_name:
            return td_adjust, None 
            
        country_name = country_name.replace('\xa0', ' ').strip()
        if any(keyword == country_name.lower() for keyword in non_country_row_keywords):
            return td_adjust, None

        return td_adjust, country_name


    def get_pre_2016_results(self, response, year):
        yield from self.parse_table_pre_2016(response, year, 'Detailed voting results of the final', 'f', 't', -1)
        yield from self.parse_table_pre_2016(response, year, 'Detailed voting results', 'f', 't', 0) 
        yield from self.parse_table_pre_2016(response, year, 'Detailed voting results of semi-final 1', 'sf1', 't', -1)
        yield from self.parse_table_pre_2016(response, year, 'Detailed voting results of semi-final 2', 'sf2', 't', -1)
        yield from self.parse_table_pre_2016(response, year, 'Detailed voting results of the semi-final', 'sf', 't', -1)


    def get_2013_results(self, response, year):
        yield from self.parse_table_pre_2016(response, year, 'Final voting results', 'f', 't', 0)
        yield from self.parse_table_pre_2016(response, year, 'Semi-final 1 voting results', 'sf1', 't', 0)
        yield from self.parse_table_pre_2016(response, year, 'Semi-final 2 voting results', 'sf2', 't', 0)


    def parse_table_pre_2016(self, response, year, table_header_search_term, round_name, vote_type, header_idx_adjust):
        try:
            xpath_query = (
                f"//table[contains(@class, 'wikitable') and ("
                f"preceding-sibling::h2[1]/span[contains(@class, 'mw-headline') and contains(normalize-space(.), '{table_header_search_term}')] or "
                f"caption[contains(normalize-space(.), '{table_header_search_term}')] or "
                f"preceding-sibling::h3[1]/span[contains(@class, 'mw-headline') and contains(normalize-space(.), '{table_header_search_term}')]"
                f")]"
            )
            table_selector = response.xpath(xpath_query)

            if not table_selector:
                self.logger.info(f'No table found for pre-2016 {year} with name containing "{table_header_search_term}" on {response.url}')
                return

            table = table_selector[0]
            rows = table.xpath(".//tr")
            
            if len(rows) < 2: 
                self.logger.warning(f"Table for pre-2016 {year} '{table_header_search_term}' has too few rows.")
                return

            header_row = rows[0] 
            data_rows = rows[1:]

            voting_country_headers = []
            for th_idx, th_cell in enumerate(header_row.xpath("./th")):
                current_i_for_parse = (th_idx + 1) - header_idx_adjust
                vc_name = self.parse_voting_country(header_idx_adjust, header_row, "dummy_recipient_for_header_parsing", current_i_for_parse)
                if vc_name:
                    voting_country_headers.append({'name': vc_name, 'original_th_idx': th_idx})
            
            if not voting_country_headers:
                self.logger.warning(f"No voting country headers identified in pre-2016 table {year} '{table_header_search_term}'.")
                return

            for data_row_element in data_rows:
                td_adjust, recipient_country_name = self.parse_country(data_row_element)
                
                if not recipient_country_name:
                    continue
                
                point_td_elements = data_row_element.xpath(".//td")
                
                td_points_column_start_index = td_adjust 
                
                if td_points_column_start_index < len(point_td_elements):
                    first_potential_point_text = point_td_elements[td_points_column_start_index].xpath("normalize-space(.//text())").get()
                    if not first_potential_point_text.isdigit() and first_potential_point_text not in ['—', '-', 'X', 'x', '']:
                        td_points_column_start_index += 1


                for point_idx_in_vc_list, vc_header_info in enumerate(voting_country_headers):
                    current_point_td_idx = td_points_column_start_index + point_idx_in_vc_list
                    
                    if current_point_td_idx < len(point_td_elements):
                        point_cell_td = point_td_elements[current_point_td_idx]
                        point = point_cell_td.xpath("normalize-space(.//text())").get()
                        
                        if not point or not point.isdigit():
                            if point not in ['—', '-', 'X', 'x', '']:
                                 self.logger.debug(f"Skipping non-numeric/non-empty point '{point}' for {recipient_country_name} from {vc_header_info['name']} in pre-2016 {year} {round_name}")
                            continue
                        
                        mapped_recipient = country_map.get(recipient_country_name, recipient_country_name)
                        mapped_voting_country = country_map.get(vc_header_info['name'], vc_header_info['name'])

                        if mapped_recipient == mapped_voting_country:
                            self.logger.debug(f"Skipping self-vote points (pre-2016): {mapped_recipient} from {mapped_voting_country}, points: {point}")
                            continue

                        yield {
                            'year': str(year),
                            'round': str(round_name),
                            'country': mapped_recipient,
                            'votingCountry': mapped_voting_country,
                            'voteType': str(vote_type), 
                            'points': str(point.strip())
                        }
                    else:
                        self.logger.debug(f"Point cell index {current_point_td_idx} out of bounds for {recipient_country_name} voting for {vc_header_info['name']} in pre-2016 table")

        except Exception as e:
            self.logger.error(f"Error in parse_table_pre_2016 for {response.url}, header '{table_header_search_term}': {e}", exc_info=True)
            return

