import pandas as pd
import datetime

# Load the data from CSV files
submissions = pd.read_csv("all_submissions.csv")
inspections = pd.read_csv("inspections_new.csv")
perdiem = pd.read_csv("per_diem.csv")
property_info = pd.read_csv("property.csv")


# filter by submission number to organize data by each submission
RJ_submissions = submissions[submissions['Submission Num'] == 38]
RJ_inspections = inspections[inspections['Submission Num'] == 38]
RJ_perdiem = perdiem[perdiem['Submission Num'] == 38]


# Convert date columns to datetime for proper sorting
RJ_inspections["Inspection Date"] = pd.to_datetime(RJ_inspections["Inspection Date"], format="%m/%d/%Y")

# RJ_inspections["Inspection Date"] = pd.to_datetime(RJ_inspections["Inspection Date"], format="%d/%b/%y")
RJ_perdiem["First Day"] = pd.to_datetime(RJ_perdiem["First Day"], format="%m/%d/%Y")
RJ_perdiem["Last Day"] = pd.to_datetime(RJ_perdiem["Last Day"], format="%m/%d/%Y")

# Assign day numbers based on sorted inspection dates
sorted_dates = RJ_inspections["Inspection Date"].sort_values().unique()
date_to_daynum = {date: i+1 for i, date in enumerate(sorted_dates)}

# Map day number to inspections
RJ_inspections["Day Number"] = RJ_inspections["Inspection Date"].map(date_to_daynum)

# print(RJ_inspections[["Inspection Date", "Day Number"]])


output_columns = [
    "Trip", "Date Of Inspection", "Inspection ID", "Property ID", "Per Diem",
    "GSA Lodging Rate", "Actual Lodging Cost", "Lodging Rate Tax", "GSA Rate Zip Code","POV Mileage",
    "POV Mileage Expense ($0.70 per mile)", "Total Expenses Per Line Item"
]

# rename for consistence
RJ_inspections.rename(columns={"Inspection Id": "InspectionID"}, inplace=True)
# RJ_inspections.rename(columns={"Property Id": "PropertyID"}, inplace=True)



# merge inspections with property info first 
RJ_inspections = pd.merge(
    RJ_inspections, 
    property_info[['InspectionID', 'PropertyID', 'PropertyType', 'PropertyName', 'PropertyStreetAddress', 'CityState', 'PropertyZip']], 
    on='InspectionID', 
    how='left'
)

# Now merge inspections with perdiem data
merged_df = pd.merge(
    RJ_inspections,
    RJ_perdiem,
    on=['Submission Num', 'Reimbursement RequestID','Day Number'],
    how='left'
)
# # merged_df.to_csv('merge2.csv', index=False)


# # Group by date and aggregate inspection IDs into a dictionary
# # Group by date and aggregate inspection IDs into a dictionary
final_df = (
    merged_df.groupby("Inspection Date")
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
    .reset_index()
)

final_df['Travel Start Location'] = pd.Series(dtype='int')
final_df['Travel End Location'] = pd.Series(dtype='int')

# # Extract values from RJ_submissions
pov_mileage = RJ_submissions["Miles Driven"].iloc[0]
pov_mileage_expense = pov_mileage * 0.70  # Example calculation
total_reimbursement = RJ_submissions["Total Reimbursement"].iloc[0]

# # Add these values as new columns to final_df
final_df["POV Mileage"] = pov_mileage
final_df["POV Mileage Expense ($0.70 per mile)"] = pov_mileage_expense
final_df["Total Reimbursement"] = total_reimbursement



# # Display final structured output
# print(final_df)

# # Rename for clarity
final_df.rename(columns={"Inspection Date": "Date", "PropertyType": "Program", "PropertyName": "Property Name",
"PropertyStreetAddress" : "Property Address", "CityState" : "Property City, State", "Zip Code": "GSA Rate Zip Code",
"Lodging Rate": "GSA Lodging Rate", "Lodging Cost": "Actual Lodging Cost", "Lodging Taxes": "Lodging Rate Tax"}, inplace=True)


final_df.to_csv('final_output_prop.csv', index=False)





