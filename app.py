from flask import Flask, render_template, request, send_file, make_response
import pandas as pd
import os
from datetime import datetime
import sys
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Base path where app.py lives

app = Flask(__name__)

GSA_API_KEY = "ZXji2qaMJo1JNcfoARGX4xgpUdnjDHqcTUiCAAUT"

# Add security headers to all responses
@app.after_request
def add_security_headers(response):

    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    
    return response

def get_perdiem_by_zip(zips, months):

    year = "2025"
    results = []
    # GSA_BASE_URL = "https://api.gsa.gov/travel/perdiem/v2/rates/zip/{zip}/year/{year}?api_key={GSA_API_KEY}"
    
    for zip_code in zips:
        # zip_code = str(int(float(zip_code_raw))).zfill(5)
        if zip_code == "00000":
            continue
        url = f"https://api.gsa.gov/travel/perdiem/v2/rates/zip/{zip_code}/year/{year}?api_key={GSA_API_KEY}"
        headers = {
        "Accept": "application/json"
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            rates = data.get("rates", [])
            if not rates or not rates[0].get("rate"):
                results.append({"zip": zip_code, "error": "Missing rate data"})
                continue
            
            mie = rates[0]["rate"][0]["meals"]
            first_last_day = round(0.75 * int(mie), 2)

            month_rates = rates[0]["rate"][0]["months"]["month"]
            for month in months:
                lodging_rate = next(
                    (m["value"] for m in month_rates if m["long"].lower() == month.lower()),
                    None
                )
                if lodging_rate is None:
                    results.append({
                        "Zip Code": zip_code,
                        "Month": month,
                        "Error": "Month data not found"
                    })
                    continue

                results.append({
                    "Zip Code": zip_code,
                    "Month": month,
                    "MI&E": mie,
                    "First/Last Day": first_last_day,
                    "Lodging Rate": lodging_rate
                })

        except (requests.HTTPError, KeyError, IndexError) as e:
            results.append({"zip": zip_code, "error": str(e)})

    gsa_df = pd.DataFrame(results)
    return (gsa_df, results) # return both dataframe and dictionary 

def check_file_permissions():
    required_files = ['Live_Data_New_04_09(All_Submissions).csv', 'Live_Data_New_04_09(Inspections).csv', 'Live_Data_New_04_09(Per Diem).csv', 'Live_Data_New_04_09(Transportation Expenses).csv']
    for file in required_files:
        file_path = os.path.join(BASE_DIR, file)
        if not os.path.exists(file_path):
            return False, f"Required file {file} not found"
        if not os.access(file_path, os.R_OK):
            return False, f"No read permission for {file}"
    return True, "All files accessible"


def highlight_non_nan(val):
    """Highlights non-NaN values yellow."""
    return 'background-color: yellow' if pd.notna(val) else ''

def process_data(submission_num):

    print(f"📁 Current working directory: {os.getcwd()}")

    try:
        # Check file permissions first
        can_access, message = check_file_permissions()
        if not can_access:
            return False, message
        
        submissions = pd.read_csv(os.path.join(BASE_DIR, "Live_Data_New_04_09(All_Submissions).csv"), encoding='cp1252')
        # inspections = pd.read_csv(os.path.join(BASE_DIR, "Live_Data_New_04_09(Inspections).csv"), encoding='cp1252')
        inspections = pd.read_csv(os.path.join(BASE_DIR, "Live_Data_New_04_09(Inspections).csv"), encoding='cp1252', names=[
            'Submission Num','Reimbursement RequestID','Inspector Name','Inspection Id_OG','Inspection Date','Property Id','Inspection Id','Status'],
            header=0, keep_default_na=True)

        perdiem = pd.read_csv(os.path.join(BASE_DIR, "Live_Data_New_04_09(Per Diem).csv"), encoding='cp1252')
        property_info = pd.read_csv(os.path.join(BASE_DIR, "property.csv"), encoding='utf-8-sig')
        transportation = pd.read_csv(os.path.join(BASE_DIR, "Live_Data_New_04_09(Transportation Expenses).csv"), encoding='cp1252')
        
        
        # FILTER BY SUBMISSION NUMBER TO CREATE REPORT FOR EACH SUBMISSION
        df_submissions = submissions[submissions['Submission Num'] == submission_num]

        if len(df_submissions) == 0:
                return False, f"Submission number {submission_num} not found"

        df_inspections = inspections[inspections['Submission Num'] == submission_num]
        df_perdiem = perdiem[perdiem['Submission Num'] == submission_num]
        df_transportation = transportation[transportation['Submission Num'] == submission_num]

        print(df_perdiem.columns)
        # print(property_info.dtypes)

        # get information that will be individually displayed 
        inspector_name = df_submissions['Inspector Name'].iloc[0]
        reimbursement_id = df_submissions['Reimbursement RequestID'].iloc[0]
        transportation_expenses = df_transportation['Transportation Expenses'].iloc[0]
        travel_location_info = df_submissions[['Depart City','Depart State','Dest City','Dest State','Dest Zip']]
        comments = df_submissions['Comments'].iloc[0]

        # REFORMAT DATES (Convert date columns to datetime for proper sorting)
        df_inspections["Inspection Date"] = pd.to_datetime(df_inspections["Inspection Date"], format="%m/%d/%Y")
        df_perdiem["First Day"] = pd.to_datetime(df_perdiem["First Day"], format="%m/%d/%Y")
        df_perdiem["Last Day"] = pd.to_datetime(df_perdiem["Last Day"], format="%m/%d/%Y")

        # get months for GSA API Usage 
        inspection_months = set(
            pd.concat([
                df_perdiem["First Day"].dt.strftime("%B"),
                df_perdiem["Last Day"].dt.strftime("%B")
            ])
        )

        # GENERATE DATES FROM FIRST TO LAST DAY IN PER DIEM
        sorted_dates = pd.date_range(start=df_perdiem["First Day"].min(), end=df_perdiem["Last Day"].max())

        # ASSIGN DAY NUMBER TO EACH DATE
        date_to_daynum = {date: i+1 for i, date in enumerate(sorted_dates)}
        # Reverse the date_to_daynum mapping (Day Number -> Date)
        daynum_to_date = {daynum: date for date, daynum in date_to_daynum.items()}

        # MAP DAY NUMBER TO INSPECTION FOR PER DIEM RATES TO MATCH 
        df_inspections["Day Number"] = df_inspections["Inspection Date"].map(date_to_daynum)


        # RENAME FOR MERGE TO WORK BASED ON INSPECTION ID 
        df_inspections.rename(columns={"Inspection Id": "InspectionID"}, inplace=True)
        # print(f"✅ Found {len(df_inspections)} inspection rows for submission {submission_num}")
        
        # MERGE INSPECTION WITH PROPERTY INFO 
        df_inspections = pd.merge(
            df_inspections, 
            property_info[['InspectionID', 'PropertyID', 'PropertyType', 'PropertyName', 'PropertyStreetAddress', 'CityState']], 
            on='InspectionID', 
            how='left'
        )

        # MERGE INSPECTION WITH PER DIEM 
        merged_df = pd.merge(
            df_inspections,
            df_perdiem,
            on=['Submission Num', 'Reimbursement RequestID','Day Number'],
            how='right'
        )

        # GROUP BY DAY NUMBER AND AGGREGATE INSPECTIONS IDS USING A SET
        final_df = (
            merged_df.groupby("Day Number")
            .agg({
                "Day Number": "first",
                "InspectionID": list,  # Store multiple IDs in a list
                "PropertyID": list,  # Store multiple Property IDs in a list
                "PropertyType": list,
                "PropertyName": list,
                "PropertyStreetAddress": list,
                "CityState": list,
                "Per Diem": "first",
                "Lodging Rate": "first",
                "Lodging Cost": "first",
                "Lodging Taxes": "first",
                "Zip Code": "first"
            })
            # .reset_index()
        )

        # Add the "Date" column by mapping Day Number to Date
        final_df['Inspection Date'] = (final_df['Day Number'].map(daynum_to_date)).dt.date
        # final_df['Inspection Date'] = final_df['Day Number'].map(day_to_date_mapping)

        pov_mileage = df_submissions["Miles Driven"].iloc[0]
        pov_mileage_expense = 0 if pov_mileage == 0 else (pov_mileage - 50) * 0.70
        total_reimbursement = df_submissions["Total Reimbursement"].iloc[0]


        final_df["POV Mileage"] = pov_mileage
        final_df["POV Mileage Expense ($0.70 per mile)"] = pov_mileage_expense
        final_df["Total Reimbursement"] = total_reimbursement

        # ENSURE SAME DATA TYPE
        # final_df["Total Reimbursement"] = final_df["Total Reimbursement"].replace('[\$,]', '', regex=True).astype(float)

        # Now assign NaN properly
        # final_df.loc[2:, ["POV Mileage", "POV Mileage Expense ($0.70 per mile)", "Total Reimbursement"]] = pd.NA


        # RENAME AND REORDER FOR CONSISTENCY
        final_df.rename(columns={"Inspection Date": "Date of Inspection", "PropertyType": "Program", "PropertyName": "Property Name",
        "PropertyStreetAddress" : "Property Address", "CityState" : "Property City, State", "Zip Code": "Zip Code",
        "Lodging Rate": "GSA Lodging Rate", "Lodging Cost": "Actual Lodging Cost", "Lodging Taxes": "Lodging Rate Tax"}, inplace=True)

        final_df = final_df[['Day Number', 'Date of Inspection', 'InspectionID', 'PropertyID', 'Program', 'Property Name', 'Property Address', 'Property City, State',
                        'Per Diem', 'GSA Lodging Rate', 'Actual Lodging Cost', 'Lodging Rate Tax', 'Zip Code'
                            ]]

        final_df['Zip Code'] = final_df['Zip Code'].apply(lambda x: str(int(x)).zfill(5) if pd.notna(x) else '00000')
        # final_df['Zip Code'] = final_df['Zip Code'].astype(str).str.zfill(5)
        zip_codes = set(final_df['Zip Code'])
        # print(inspection_months)
        
        return True, (submission_num, reimbursement_id, inspector_name, pov_mileage, pov_mileage_expense, total_reimbursement,
            travel_location_info, transportation_expenses, comments, final_df, zip_codes, inspection_months)
        

    except Exception as e:
        return False, f"Error processing data: {str(e)}"

def highlight_perdiem(gsa_dict, final_df):

    # gsa_dict is a list of dictionaries so we want to convert to a lookup format 
    # key: (zip, month) --> value: {zip, month}
    gsa_lookup = {
    (entry['Zip Code'].zfill(5), entry['Month'].strip().lower()): entry
    for entry in gsa_dict
    }

    first_idx = final_df.index[0]
    last_idx = final_df.index[-1]

    print("WHAT IS INDEX")
    print(first_idx, last_idx)

    for idx in [first_idx, last_idx]:
        row = final_df.loc[idx]
        zip_code = row['Zip Code']
        try:
            month = pd.to_datetime(row['Date of Inspection']).strftime('%B').lower()
            actual_perdiem = float(str(row['Per Diem']).replace('$', '').replace(',', '').strip())
        except Exception:
            continue

        gsa_entry = gsa_lookup.get((zip_code, month))
        if not gsa_entry:
            continue

        expected_rate = gsa_entry.get('First/Last Day')
        try:
            if float(actual_perdiem) != float(expected_rate):
                # Wrap the value with a span + inline style
                original_value = final_df.at[idx, 'Per Diem']
                final_df.at[idx, 'Per Diem'] = f'FLAG {original_value}'
        except Exception:
            continue

    return final_df

def highlight_mie(gsa_dict, final_df):

    # gsa_dict is a list of dictionaries so we want to convert to a lookup format 
    # key: (zip, month) --> value: {zip, month}
    gsa_lookup = {
    (entry['Zip Code'].zfill(5), entry['Month'].strip().lower()): entry
    for entry in gsa_dict
    }

    # first_idx = final_df.index[0]
    last_idx = final_df.index[-1]

    for idx in range(2, last_idx):
        row = final_df.loc[idx]
        zip_code = row['Zip Code']
        try:
            month = pd.to_datetime(row['Date of Inspection']).strftime('%B').lower()
            actual_perdiem = float(str(row['Per Diem']).replace('$', '').replace(',', '').strip())
        except Exception:
            continue

        gsa_entry = gsa_lookup.get((zip_code, month))
        if not gsa_entry:
            continue

        expected_rate = gsa_entry.get('MI&E')
        try:
            if float(actual_perdiem) != float(expected_rate):
                # Wrap the value with a span + inline style
                original_value = final_df.at[idx, 'Per Diem']
                final_df.at[idx, 'Per Diem'] = f'FLAG {original_value}'
        except Exception:
            continue

    return final_df

def highlight_lodging(gsa_dict, final_df):

    # gsa_dict is a list of dictionaries so we want to convert to a lookup format 
    # key: (zip, month) --> value: {zip, month}
    gsa_lookup = {
    (entry['Zip Code'].zfill(5), entry['Month'].strip().lower()): entry
    for entry in gsa_dict
    }

    # first_idx = final_df.index[0]
    last_idx = final_df.index[-1]

    for idx in range(1, last_idx + 1): # checking all rows now for lodging 
        row = final_df.loc[idx]
        zip_code = row['Zip Code']
        try:
            month = pd.to_datetime(row['Date of Inspection']).strftime('%B').lower()
            actual_lodging = float(str(row['GSA Lodging Rate']).replace('$', '').replace(',', '').strip())
        except Exception:
            continue

        gsa_entry = gsa_lookup.get((zip_code, month))
        if not gsa_entry:
            continue

        expected_rate = gsa_entry.get('Lodging Rate')
        try:
            if float(actual_lodging) != float(expected_rate):
                # Wrap the value with a span + inline style
                original_value = final_df.at[idx, 'GSA Lodging Rate']
                final_df.at[idx, 'GSA Lodging Rate'] = f'FLAG {original_value}'
        except Exception:
            continue

    return final_df


@app.route('/', methods=['GET'])
def index():
    can_access, message = check_file_permissions()
    if not can_access:
        return render_template('index.html', error=message)
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    try:
        submission_num = int(request.form['submission_num'])
        # print(f"🔢 Parsed submission number: {submission_num}")
        success, result = process_data(submission_num)
        # print(f"🔍 Debug result from process_data: success={success}, result={result}")
        # print(f"✅ process_data() returned: success={success}, result={result}")
        
        if success:
            # file_name = os.path.basename(result)
            (submission_num, reimbursement_id, inspector_name, pov_mileage, pov_mileage_expense, total_reimbursement,
            travel_location_info, transportation_expenses, comments, final_df, zip_codes, inspection_months) = result

            # USE ZIP CODES AND MONTHS FOR API USAGE 
            (gsa_df, gsa_dict) = get_perdiem_by_zip(zip_codes, inspection_months)

            # new = highlight_perdiem(gsa_dict, final_df)
            flagged_perdiem_df = highlight_perdiem(gsa_dict, final_df)
            flagged_mie_df = highlight_mie(gsa_dict, flagged_perdiem_df)
            flagged_final_df = highlight_lodging(gsa_dict, flagged_mie_df)

            table_html = flagged_final_df.to_html(classes='table table-bordered table-striped', index=False, border=0)
            
            # table_html = final_df.to_html(classes='table table-bordered table-striped', index=False, border=0)
            location_html = travel_location_info.to_html(classes='table table-bordered table-striped', index=False, border=0)
            gsa_html = gsa_df.to_html(classes='table table-bordered table-striped', index=False, border=0)
            # return send_file(result, as_attachment=True, download_name=file_name)
            return render_template('index.html',
                                   submission_num = submission_num,
                                   reimbursement_id = reimbursement_id, 
                                   inspector_name = inspector_name,
                                   pov_mileage = pov_mileage,
                                   pov_mileage_expense = pov_mileage_expense,
                                   total_reimbursement = total_reimbursement,
                                   location_table = location_html, 
                                   transportation_expenses=transportation_expenses,
                                   comments = comments,
                                   excel_table=table_html,
                                   gsa_table = gsa_html)
        else:
            return render_template('index.html', submission_num=submission_num, error=result)
    except ValueError:
        return render_template('index.html', error="Please enter a valid submission number")
    except Exception as e:
        return render_template('index.html', error=f"An error occurred: {str(e)}")

if __name__ == '__main__':
    # Try different port numbers if 3000 is blocked
    for port in range(3000, 3010):
        try:
            print(f"Trying port {port}...")
            app.run(host='127.0.0.1', port=port, debug=True)
            break
        except OSError:
            continue 