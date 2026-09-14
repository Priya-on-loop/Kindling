import pandas as pd

occupation_df = pd.read_csv("Data/occupation_data.csv")
interest_df = pd.read_csv("Data/career_interest_types.csv")
task_df = pd.read_csv("Data/task_statements.csv")

print("Occupation data:", occupation_df.shape)
print("Career interest data:", interest_df.shape)
print("Task data:", task_df.shape)

print("\nScale ID counts:")
print(interest_df["Scale ID"].value_counts())


# Keep only Occupational Interest (OI) data
oi_df = interest_df[interest_df["Scale ID"] == "OI"].copy()

print("\nOI data shape:")
print(oi_df.shape)


# Check the six RIASEC interest types
print("\nInterest types:")
print(oi_df["Element Name"].value_counts())

# Convert RIASEC data from long format to wide format
riasec_wide = oi_df.pivot(
    index="O*NET-SOC Code",
    columns="Element Name",
    values="Data Value"
).reset_index()

print("\nRIASEC wide data shape:")
print(riasec_wide.shape)

print("\nFirst 5 rows:")
print(riasec_wide.head())

# Rename RIASEC columns to Kindling names
riasec_wide = riasec_wide.rename(columns={
    "Realistic": "builds_tinkers",
    "Investigative": "investigates_why",
    "Artistic": "creates_expresses",
    "Social": "works_with_people",
    "Conventional": "organizes_systems",
    "Enterprising": "leads_persuades"
})

print("\nRenamed columns:")
print(riasec_wide.columns.tolist())

# Check for missing values
print("\nMissing values:")
print(riasec_wide.isnull().sum())

# Check for duplicate occupation codes
print("\nDuplicate occupation codes:")
print(riasec_wide["O*NET-SOC Code"].duplicated().sum())

# Save the cleaned RIASEC dataset
riasec_wide.to_csv("Outputs/riasec_wide.csv", index=False)

print("\nClean RIASEC dataset saved successfully!")