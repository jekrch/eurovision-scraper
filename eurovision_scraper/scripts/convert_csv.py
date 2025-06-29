import csv

def convert_eurovision_csv(input_filepath, output_filepath):
    """
    Converts a CSV file from an old Eurovision vote format to a new format.

    Input format: year,round,country,votingCountry,voteType,points
    Output format: year,round,from_country_id,to_country_id,total_points,tele_points,jury_points
    
    Handles vote types:
    - 't', 'tv': Summed into tele_points.
    - 'j': Summed into jury_points.
    - 'f': Points contribute to total_points but are not in a separate column.
    
    If tele_points or jury_points are not found for a pair, they will be empty in the output.
    Total_points will sum available points from t, tv, j, and f.
    """
    # Stores aggregated results: 
    # {(year, round, from, to) -> {'tele_points': X or None, 
    #                              'jury_points': Y or None,
    #                              'f_points': Z or None}}
    aggregated_data = {} 

    # Expected columns in the input CSV
    expected_input_columns = ['year', 'round', 'country', 'votingCountry', 'voteType', 'points']
    
    # Keep track of vote types encountered to provide a summary
    encountered_vote_types = set()
    unmapped_vote_types_for_summary = set()


    # --- Read the input CSV and aggregate data ---
    try:
        with open(input_filepath, mode='r', newline='', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            
            if not reader.fieldnames or not all(col in reader.fieldnames for col in expected_input_columns):
                print(f"Error: Input CSV header is missing or does not match expected columns: {expected_input_columns}")
                print(f"Found header: {reader.fieldnames}")
                return

            for i, row in enumerate(reader):
                try:
                    year = row['year']
                    round_val = row['round']
                    to_country = row['country']       # Country being voted FOR
                    from_country = row['votingCountry'] # Country GIVING votes
                    vote_type_original = row['voteType']
                    vote_type = vote_type_original.strip().lower()
                    points = int(row['points'])
                    
                    encountered_vote_types.add(vote_type_original) # Store original casing for summary
                except KeyError as e:
                    print(f"Warning: Row {i+2}: Missing key {e}. Skipping row: {row}")
                    continue
                except ValueError:
                    print(f"Warning: Row {i+2}: Could not parse 'points' as an integer for row: {row}. Skipping row.")
                    continue
                
                key = (year, round_val, from_country, to_country)

                # Initialize with None if key is new
                if key not in aggregated_data:
                    aggregated_data[key] = {'tele_points': None, 'jury_points': None, 'f_points': None}

                # Aggregate points based on vote type
                if vote_type == 't' or vote_type == 'tv':
                    current_val = aggregated_data[key]['tele_points']
                    aggregated_data[key]['tele_points'] = points if current_val is None else current_val + points
                elif vote_type == 'j':
                    current_val = aggregated_data[key]['jury_points']
                    aggregated_data[key]['jury_points'] = points if current_val is None else current_val + points
                elif vote_type == 'f': # 'f' votes contribute to their own sum, then to total
                    current_val = aggregated_data[key]['f_points']
                    aggregated_data[key]['f_points'] = points if current_val is None else current_val + points
                else:
                    # Log truly unknown vote types once
                    if vote_type_original not in unmapped_vote_types_for_summary:
                         print(f"Info: Row {i+2}: VoteType '{vote_type_original}' is not explicitly mapped to tele/jury/f. Its points will not be included in tele_points, jury_points, or f_points (and thus not total_points unless logic changes).")
                         unmapped_vote_types_for_summary.add(vote_type_original)


    except FileNotFoundError:
        print(f"Error: Input file not found at '{input_filepath}'")
        return
    except Exception as e:
        print(f"An unexpected error occurred while reading the input file: {e}")
        return

    if not aggregated_data:
        print("No data processed from the input file.")
        return
        
    print(f"Encountered vote types in input: {encountered_vote_types}")
    if unmapped_vote_types_for_summary:
        print(f"Unmapped vote types (points not included in output aggregates): {unmapped_vote_types_for_summary}")


    # --- Write the aggregated data to the output CSV ---
    try:
        with open(output_filepath, mode='w', newline='', encoding='utf-8') as outfile:
            fieldnames = ['year', 'round', 'from_country_id', 'to_country_id', 'total_points', 'tele_points', 'jury_points']
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()

            for key, data in aggregated_data.items():
                year_out, round_out, from_country_out, to_country_out = key
                
                tele_pts_val = data['tele_points']
                jury_pts_val = data['jury_points']
                f_pts_val = data['f_points'] # Used for total_points calculation

                # Calculate total_points: sum of tele, jury, and f points, treating None as 0 for summation
                total_pts = (tele_pts_val if tele_pts_val is not None else 0) + \
                              (jury_pts_val if jury_pts_val is not None else 0) + \
                              (f_pts_val if f_pts_val is not None else 0)

                # Prepare display values for tele and jury: None becomes empty string, otherwise use the value
                tele_pts_display = 0 if tele_pts_val is None else tele_pts_val
                jury_pts_display = 0 if jury_pts_val is None else jury_pts_val

                writer.writerow({
                    'year': year_out,
                    'round': round_out,
                    'from_country_id': from_country_out,
                    'to_country_id': to_country_out,
                    'total_points': total_pts,
                    'tele_points': tele_pts_display,
                    'jury_points': jury_pts_display
                })
        print(f"Successfully converted CSV. Output saved to '{output_filepath}'")

    except Exception as e:
        print(f"An error occurred while writing the output file: {e}")

if __name__ == "__main__":



    convert_eurovision_csv('./source.csv', './target.csv')

