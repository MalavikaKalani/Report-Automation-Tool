import pandas as pd
import datetime

# LOAD DATA FROM CSV
# submissions = pd.read_csv("Live_Data(All_Submissions).csv")
# inspections = pd.read_csv("Live_Data(Inspections).csv")
# perdiem = pd.read_csv("Live_Data(Per Diem).csv")
# property_info = pd.read_csv("property.csv")

submissions = pd.read_csv("Live_Data(All_Submissions).csv", encoding='cp1252')
inspections = pd.read_csv("Live_Data(Inspections).csv",encoding='cp1252')
perdiem = pd.read_csv("Live_Data(Per Diem).csv",encoding='cp1252')
property_info = pd.read_csv("property.csv",encoding='cp1252')


# submissions = pd.read_csv("all_submissions.csv")
# inspections = pd.read_csv("inspections_new.csv")
# perdiem = pd.read_csv("per_diem.csv")
# property_info = pd.read_csv("property.csv")


# FILTER BY SUBMISSION NUMBER TO CREATE REPORT FOR EACH SUBMISSION
RJ_submissions = submissions[submissions['Submission Num'] == 334]
RJ_inspections = inspections[inspections['Submission Num'] == 334]
RJ_perdiem = perdiem[perdiem['Submission Num'] == 334]


# REFORMAT DATES (Convert date columns to datetime for proper sorting)
RJ_inspections["Inspection Date"] = pd.to_datetime(RJ_inspections["Inspection Date"], format="%m/%d/%Y")
RJ_perdiem["First Day"] = pd.to_datetime(RJ_perdiem["First Day"], format="%m/%d/%Y")
RJ_perdiem["Last Day"] = pd.to_datetime(RJ_perdiem["Last Day"], format="%m/%d/%Y")


# GENERATE DATES FROM FIRST TO LAST DAY IN PER DIEM
sorted_dates = pd.date_range(start=RJ_perdiem["First Day"].min(), end=RJ_perdiem["Last Day"].max())

# ASSIGN DAY NUMBER TO EACH DATE
date_to_daynum = {date: i+1 for i, date in enumerate(sorted_dates)}
# Reverse the date_to_daynum mapping (Day Number -> Date)
daynum_to_date = {daynum: date for date, daynum in date_to_daynum.items()}

# MAP DAY NUMBER TO INSPECTION FOR PER DIEM RATES TO MATCH 
RJ_inspections["Day Number"] = RJ_inspections["Inspection Date"].map(date_to_daynum)


# RENAME FOR MERGE TO WORK BASED ON INSPECTION ID 
RJ_inspections.rename(columns={"Inspection Id": "InspectionID"}, inplace=True)


# MERGE INSPECTION WITH PROPERTY INFO 
RJ_inspections = pd.merge(
    RJ_inspections, 
    property_info[['InspectionID', 'PropertyID', 'PropertyType', 'PropertyName', 'PropertyStreetAddress', 'CityState', 'PropertyZip']], 
    on='InspectionID', 
    how='left'
)

# MERGE INSPECTION WITH PER DIEM 
merged_df = pd.merge(
    RJ_inspections,
    RJ_perdiem,
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

print(final_df['InspectionID'])
# Add the "Date" column by mapping Day Number to Date
final_df['Inspection Date'] = final_df['Day Number'].map(daynum_to_date)
# final_df['Inspection Date'] = final_df['Day Number'].map(day_to_date_mapping)

# ADD EXTRA FIELDS 
final_df['Travel Start Location'] = pd.Series(dtype='int')
final_df['Travel End Location'] = pd.Series(dtype='int')
final_df['Total Expenses Per Line Item'] = pd.Series(dtype='int')

pov_mileage = RJ_submissions["Miles Driven"].iloc[0]
pov_mileage_expense = (pov_mileage - 50) * 0.70  
total_reimbursement = RJ_submissions["Total Reimbursement"].iloc[0]


final_df["POV Mileage"] = pov_mileage
final_df["POV Mileage Expense ($0.70 per mile)"] = pov_mileage_expense
final_df["Total Reimbursement"] = total_reimbursement



# ENSURE SAME DATA TYPE
final_df["Total Reimbursement"] = final_df["Total Reimbursement"].replace('[\$,]', '', regex=True).astype(float)

# Now assign NaN properly
final_df.loc[2:, ["POV Mileage", "POV Mileage Expense ($0.70 per mile)", "Total Reimbursement"]] = pd.NA


# RENAME AND REORDER FOR CONSISTENCY
final_df.rename(columns={"Inspection Date": "Date", "PropertyType": "Program", "PropertyName": "Property Name",
"PropertyStreetAddress" : "Property Address", "CityState" : "Property City, State", "PropertyZip": "GSA Rate Zip Code",
"Lodging Rate": "GSA Lodging Rate", "Lodging Cost": "Actual Lodging Cost", "Lodging Taxes": "Lodging Rate Tax"}, inplace=True)

final_df = final_df[['Day Number', 'Date', 'InspectionID', 'PropertyID', 'Program', 'Property Name', 'Property Address', 'Property City, State',
                   'Per Diem', 'GSA Lodging Rate', 'Actual Lodging Cost', 'Lodging Rate Tax', 'GSA Rate Zip Code', 'Travel Start Location', 
                   'Travel End Location', 'POV Mileage', 'POV Mileage Expense ($0.70 per mile)', 'Total Reimbursement','Total Expenses Per Line Item'
                    ]]

print(final_df.dtypes)

# final_df.to_csv('report_submission_37.csv', index=False)
# final_df.to_excel('report_submission_37.xlsx', index=False)

# Save to Excel with adjusted column width
excel_filename = 'report_submission_192.xlsx'
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




