import json
import numpy as np
import faiss


# Adjustable weighting constants
LLM_WEIGHT = 0.6
ENGAGEMENT_WEIGHT = 0.4


RIASEC_COLUMNS = [
    "creates_expresses",
    "organizes_systems",
    "investigates_why",
    "builds_tinkers",
    "works_with_people",
    "leads_persuades"
]


def load_career_graph():
    """Load occupation data from career_graph.json."""

    with open("Outputs/career_graph.json", "r", encoding="utf-8") as file:
        occupations = json.load(file)

    return occupations


def get_occupation_vectors(occupations):
    """Extract the 6-dimensional RIASEC vectors."""

    vectors = []

    for occupation in occupations:
        vector = [
            occupation["riasec"][column]
            for column in RIASEC_COLUMNS
        ]

        vectors.append(vector)

    return np.array(vectors, dtype=np.float32)


def build_faiss_index(occupation_vectors):
    """
    Build a FAISS Flat index using inner product.

    After L2 normalization, inner product is equivalent
    to cosine similarity.
    """

    vectors = occupation_vectors.copy()

    # Normalize occupation vectors
    faiss.normalize_L2(vectors)

    # 6 = number of RIASEC dimensions
    index = faiss.IndexFlatIP(6)

    # Add all occupation vectors
    index.add(vectors)

    return index


def combine_student_vectors(llm_vector, engagement_vector):
    """
    Combine LLM-derived and engagement-derived vectors
    using adjustable weights.
    """

    llm_vector = np.array(llm_vector, dtype=np.float32)
    engagement_vector = np.array(
        engagement_vector,
        dtype=np.float32
    )

    combined_vector = (
        LLM_WEIGHT * llm_vector
        + ENGAGEMENT_WEIGHT * engagement_vector
    )

    return combined_vector


def match_occupations(student_vector, top_k=5):
    """
    Compare a student's combined vector against all
    occupations using FAISS cosine similarity.

    Returns a ranked shortlist.
    """

    # Load occupations
    occupations = load_career_graph()

    # Extract occupation vectors
    occupation_vectors = get_occupation_vectors(occupations)

    # Build FAISS index
    index = build_faiss_index(occupation_vectors)

    # Convert student vector to float32
    student_vector = np.array(
        student_vector,
        dtype=np.float32
    ).reshape(1, -1)

    # Normalize student vector
    faiss.normalize_L2(student_vector)

    # Search FAISS index
    similarities, indices = index.search(
        student_vector,
        top_k
    )

    results = []

    for similarity, index_position in zip(
        similarities[0],
        indices[0]
    ):
        occupation = occupations[index_position]

        results.append({
            "id": occupation["id"],
            "title": occupation["title"],
            "similarity": float(similarity)
        })

    return results


if __name__ == "__main__":

    # Example LLM-generated interest vector
    llm_vector = [
        5.0,
        3.0,
        4.0,
        2.0,
        5.0,
        4.0
    ]

    # Example engagement-based interest vector
    engagement_vector = [
        4.0,
        4.0,
        3.0,
        2.0,
        5.0,
        3.0
    ]

    # Combine both vectors
    combined_vector = combine_student_vectors(
        llm_vector,
        engagement_vector
    )

    print("\nLLM weight:", LLM_WEIGHT)
    print("Engagement weight:", ENGAGEMENT_WEIGHT)
    print("Combined student vector:", combined_vector)

    matches = match_occupations(
        combined_vector,
        top_k=5
    )

    print("\nTop occupation matches:\n")

    for match in matches:
        print(
            match["title"],
            "->",
            round(match["similarity"], 4)
        )