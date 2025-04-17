from flask import Flask, render_template, request, send_file, make_response
import pandas as pd
import os
from datetime import datetime
import sys

app = Flask(__name__)

# Add security headers to all responses
@app.after_request
def add_security_headers(response):

    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    
    return response

def check_file_permissions():
    required_files = ['Live_Data_New_04_09(All_Submissions).csv', 'Live_Data_New_04_09(Inspections).csv', 'Live_Data_New_04_09(Per Diem).csv']
    for file in required_files:
        if not os.path.exists(file):
            return False, f"Required file {file} not found"
        if not os.access(file, os.R_OK):
            return False, f"No read permission for {file}"
    return True, "All files accessible"

def process_data(submission_num):

    print(f"📁 Current working directory: {os.getcwd()}")

    try:
        # Check file permissions first
        can_access, message = check_file_permissions()
        if not can_access:
            return False, message

        # LOAD DATA FROM CSV
        # submissions = pd.read_csv("all_submissions.csv")
        # inspections = pd.read_csv("inspections_new.csv")
        # perdiem = pd.read_csv("per_diem.csv")
        # property_info = pd.read_csv("property.csv")

        submissions = pd.read_csv("Live_Data_New_04_09(All_Submissions).csv", encoding='cp1252')
        inspections = pd.read_csv("Live_Data_New_04_09(Inspections).csv",encoding='cp1252')
        perdiem = pd.read_csv("Live_Data_New_04_09(Per Diem).csv",encoding='cp1252')
        property_info = pd.read_csv("property.csv",encoding='cp1252')



        # FILTER BY SUBMISSION NUMBER TO CREATE REPORT FOR EACH SUBMISSION
        df_submissions = submissions[submissions['Submission Num'] == submission_num]
        df_inspections = inspections[inspections['Submission Num'] == submission_num]
        df_perdiem = perdiem[perdiem['Submission Num'] == submission_num]

        if len(df_submissions) == 0:
                return False, f"Submission number {submission_num} not found"

        inspector_name = df_submissions['Inspector Name'].iloc[0]
        reimbursement_id = df_submissions['Reimbursement RequestID'].iloc[0]


        # REFORMAT DATES (Convert date columns to datetime for proper sorting)
        df_inspections["Inspection Date"] = pd.to_datetime(df_inspections["Inspection Date"], format="%m/%d/%Y")
        df_perdiem["First Day"] = pd.to_datetime(df_perdiem["First Day"], format="%m/%d/%Y")
        df_perdiem["Last Day"] = pd.to_datetime(df_perdiem["Last Day"], format="%m/%d/%Y")


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


        # MERGE INSPECTION WITH PROPERTY INFO 
        df_inspections = pd.merge(
            df_inspections, 
            property_info[['InspectionID', 'PropertyID', 'PropertyType', 'PropertyName', 'PropertyStreetAddress', 'CityState', 'PropertyZip']], 
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
                "InspectionID": set,  # Store multiple IDs in a list
                "PropertyID": set,  # Store multiple Property IDs in a list
                "PropertyType": set,
                "PropertyName": set,
                "PropertyStreetAddress": set,
                "CityState": set,
                "Per Diem": "first",
                "Lodging Rate": "first",
                "Lodging Cost": "first",
                "Lodging Taxes": "first",
                "PropertyZip": "first"
            })
            # .reset_index()
        )

        # Add the "Date" column by mapping Day Number to Date
        final_df['Inspection Date'] = (final_df['Day Number'].map(daynum_to_date)).dt.date
        # final_df['Inspection Date'] = final_df['Day Number'].map(day_to_date_mapping)

        # ADD EXTRA FIELDS 
        final_df['Travel Start Location'] = pd.Series(dtype='int')
        final_df['Travel End Location'] = pd.Series(dtype='int')
        final_df['Total Expenses Per Line Item'] = pd.Series(dtype='int')

        pov_mileage = df_submissions["Miles Driven"].iloc[0]
        pov_mileage_expense = (pov_mileage - 50) * 0.70  
        total_reimbursement = df_submissions["Total Reimbursement"].iloc[0]


        final_df["POV Mileage"] = pov_mileage
        final_df["POV Mileage Expense ($0.70 per mile)"] = pov_mileage_expense
        final_df["Total Reimbursement"] = total_reimbursement



        # ENSURE SAME DATA TYPE
        final_df["Total Reimbursement"] = final_df["Total Reimbursement"].replace('[\$,]', '', regex=True).astype(float)

        # Now assign NaN properly
        final_df.loc[2:, ["POV Mileage", "POV Mileage Expense ($0.70 per mile)", "Total Reimbursement"]] = pd.NA


        # RENAME AND REORDER FOR CONSISTENCY
        final_df.rename(columns={"Inspection Date": "Date of Inspection", "PropertyType": "Program", "PropertyName": "Property Name",
        "PropertyStreetAddress" : "Property Address", "CityState" : "Property City, State", "PropertyZip": "GSA Rate Zip Code",
        "Lodging Rate": "GSA Lodging Rate", "Lodging Cost": "Actual Lodging Cost", "Lodging Taxes": "Lodging Rate Tax"}, inplace=True)

        final_df = final_df[['Day Number', 'Date of Inspection', 'InspectionID', 'PropertyID', 'Program', 'Property Name', 'Property Address', 'Property City, State',
                        'Per Diem', 'GSA Lodging Rate', 'Actual Lodging Cost', 'Lodging Rate Tax', 'GSA Rate Zip Code', 'Travel Start Location', 
                        'Travel End Location', 'POV Mileage', 'POV Mileage Expense ($0.70 per mile)', 'Total Reimbursement','Total Expenses Per Line Item'
                            ]]

        # print(final_df.dtypes)

        # final_df.to_csv('report_submission_37.csv', index=False)
        # final_df.to_excel('report_submission_37.xlsx', index=False)

        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        excel_filename = f'{inspector_name}_{reimbursement_id}_{submission_num}.xlsx'

        # Save to Excel with adjusted column width
        with pd.ExcelWriter(excel_filename, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, sheet_name='Sheet1', index=False)

            # Access the workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['Sheet1']

            # Adjust column width dynamically
            for i, col in enumerate(final_df.columns):
                max_length = max(final_df[col].astype(str).map(len).max(), len(col)) + 8
                worksheet.set_column(i, i, max_length)  # Set column width

            writer._save()  # Save the file
            return True, excel_filename

    except Exception as e:
        return False, f"Error processing data: {str(e)}"

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
        print(f"🔢 Parsed submission number: {submission_num}")
        success, result = process_data(submission_num)
        print(f"✅ process_data() returned: success={success}, result={result}")
        
        if success:
            return send_file(result, as_attachment=True, download_name=result)
        else:
            return render_template('index.html', error=result)
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