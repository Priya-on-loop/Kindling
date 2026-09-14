import pandas as pd

# Load the cleaned RIASEC dataset
riasec_df = pd.read_csv("Outputs/riasec_wide.csv")

# Check the data
print("RIASEC data shape:", riasec_df.shape)

print("\nColumns:")
print(riasec_df.columns.tolist())

# Select the six RIASEC features for clustering
riasec_columns = [
    "builds_tinkers",
    "investigates_why",
    "creates_expresses",
    "works_with_people",
    "organizes_systems",
    "leads_persuades"
]

X = riasec_df[riasec_columns]

print("\nClustering data shape:")
print(X.shape)

from sklearn.preprocessing import StandardScaler

# Scale the RIASEC features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

print("\nScaled data shape:")
print(X_scaled.shape)

from sklearn.mixture import GaussianMixture

# Test different numbers of GMM components
bic_scores = []

for n in range(2, 11):
    gmm = GaussianMixture(
        n_components=n,
        random_state=42
    )
    
    gmm.fit(X_scaled)
    bic_scores.append(gmm.bic(X_scaled))

print("\nBIC scores:")
for n, bic in zip(range(2, 11), bic_scores):
    print(f"{n} components: {bic:.2f}")

    # Create the final GMM model with 10 components
gmm = GaussianMixture(
    n_components=10,
    random_state=42
)

# Fit the model
gmm.fit(X_scaled)

# Assign each occupation to a cluster
riasec_df["family"] = gmm.predict(X_scaled)

print("\nCluster distribution:")
print(riasec_df["family"].value_counts().sort_index())

# Load occupation and task datasets
occupation_df = pd.read_csv("Data/occupation_data.csv")
task_df = pd.read_csv("Data/task_statements.csv")

# Check column names
print("\nOccupation columns:")
print(occupation_df.columns.tolist())

print("\nTask columns:")
print(task_df.columns.tolist())

# Keep only the columns we need from occupation data
occupation_info = occupation_df[
    ["O*NET-SOC Code", "Title", "Description"]
].copy()

# Merge occupation information with RIASEC + family
graph_df = riasec_df.merge(
    occupation_info,
    on="O*NET-SOC Code",
    how="inner"
)

print("\nAfter merging occupation data:")
print(graph_df.shape)

# Select 2-3 Core tasks for each occupation
core_tasks = task_df[task_df["Task Type"] == "Core"].copy()

sample_tasks = (
    core_tasks
    .groupby("O*NET-SOC Code")["Task"]
    .apply(lambda x: x.head(3).tolist())
    .reset_index(name="sample_tasks")
)

# Add sample tasks to the graph data
graph_df = graph_df.merge(
    sample_tasks,
    on="O*NET-SOC Code",
    how="left"
)

print("\nAfter adding tasks:")
print(graph_df.shape)

# Check first occupation
print("\nFirst occupation:")
print(graph_df.iloc[0])


import json

# RIASEC columns used in Kindling
riasec_columns = [
    "builds_tinkers",
    "investigates_why",
    "creates_expresses",
    "works_with_people",
    "organizes_systems",
    "leads_persuades"
]

# Create the career graph
career_graph = []

for _, row in graph_df.iterrows():

    # Get sample tasks
    tasks = row["sample_tasks"]

    # Handle occupations where tasks are missing
    if not isinstance(tasks, list):
        tasks = []

    career = {
        "id": row["O*NET-SOC Code"],
        "title": row["Title"],
        "description": row["Description"],
        "riasec": {
            column: float(row[column])
            for column in riasec_columns
        },
        "sample_tasks": tasks,
        "family": int(row["family"])
    }

    career_graph.append(career)

# Save as JSON
with open("Outputs/career_graph.json", "w", encoding="utf-8") as f:
    json.dump(career_graph, f, indent=2, ensure_ascii=False)

print("\nCareer graph created successfully!")
print("Number of occupations:", len(career_graph))
print("Saved to: Outputs/career_graph.json")


# Validate the career graph
with open("Outputs/career_graph.json", "r", encoding="utf-8") as f:
    loaded_graph = json.load(f)

required_fields = [
    "id",
    "title",
    "description",
    "riasec",
    "sample_tasks",
    "family"
]

print("\n--- Career Graph Validation ---")
print("Total occupations:", len(loaded_graph))

# Check required fields
missing_fields = []

for career in loaded_graph:
    for field in required_fields:
        if field not in career:
            missing_fields.append((career["id"], field))

print("Missing fields:", len(missing_fields))

# Check RIASEC fields
required_riasec = [
    "builds_tinkers",
    "investigates_why",
    "creates_expresses",
    "works_with_people",
    "organizes_systems",
    "leads_persuades"
]

missing_riasec = []

for career in loaded_graph:
    for field in required_riasec:
        if field not in career["riasec"]:
            missing_riasec.append((career["id"], field))

print("Missing RIASEC fields:", len(missing_riasec))

print("Validation complete!")