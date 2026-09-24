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
    """
    Extract the 6-dimensional RIASEC vectors and min-max
    normalize each dimension onto 0.0-1.0.

    The raw O*NET importance ratings run 1.0-7.0 and — because
    that scale has no true zero — every occupation vector has a
    "floor" of at least 1.0 in every dimension. After L2
    normalization for cosine similarity, that floor pulls every
    occupation's direction toward the same all-ones neighborhood
    in 6D space, regardless of the LLM/engagement-derived student
    vector's own scale (0.0-1.0). That's what caused similarity
    scores to cluster at 0.96-0.99 for nearly every match: cosine
    similarity is invariant to a vector's magnitude, but not to an
    additive shift, and the shared 1.0 floor across every
    occupation vector was exactly that shift. Rescaling each
    column with its own observed min/max removes the floor and
    lets genuinely weak dimensions reach 0.0, restoring real
    directional spread between occupations.
    """

    vectors = []

    for occupation in occupations:
        vector = [
            occupation["riasec"][column]
            for column in RIASEC_COLUMNS
        ]

        vectors.append(vector)

    vectors = np.array(vectors, dtype=np.float32)

    column_min = vectors.min(axis=0)
    column_max = vectors.max(axis=0)
    column_range = column_max - column_min
    # Guard against a dimension with zero spread (would divide by 0).
    column_range[column_range == 0] = 1.0

    normalized = (vectors - column_min) / column_range

    return normalized.astype(np.float32)


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


SIMILARITY_THRESHOLD = 0.95
MAX_RESULTS = 15
MIN_RESULTS = 2


def match_occupations(
    student_vector,
    threshold=SIMILARITY_THRESHOLD,
    max_results=MAX_RESULTS,
    min_results=MIN_RESULTS
):
    """
    Compare a student's combined vector against every
    occupation using FAISS cosine similarity, on min-max
    normalized RIASEC vectors (see get_occupation_vectors).

    Returns every occupation at or above `threshold`, ranked by
    similarity — not a fixed count. A sharply-shaped profile
    (2-3 dominant RIASEC dimensions, per Holland's theory) will
    genuinely match fewer real occupations than a flatter one;
    that's expected behavior, not something to smooth over.

    `max_results` is a display safeguard only (so a broad,
    balanced profile can't flood the UI with hundreds of
    results) — it is not a claim that the 16th-best match is
    meaningfully worse than the 15th. `min_results` is the
    symmetric safeguard: if a profile is so narrow that almost
    nothing clears the threshold, the top `min_results` matches
    are still returned rather than showing the student nothing.
    """

    # Load occupations
    occupations = load_career_graph()

    # Extract occupation vectors (min-max normalized per column)
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

    # Search the full index so every similarity is available to
    # threshold against — there's no fixed result count to search for.
    similarities, indices = index.search(
        student_vector,
        len(occupations)
    )

    ranked = list(zip(similarities[0], indices[0]))

    passing = [
        (similarity, index_position)
        for similarity, index_position in ranked
        if similarity >= threshold
    ]

    selected = passing if len(passing) >= min_results else ranked[:min_results]

    results = []

    for similarity, index_position in selected[:max_results]:
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

    matches = match_occupations(combined_vector)

    print(f"\nOccupation matches (threshold={SIMILARITY_THRESHOLD}, max={MAX_RESULTS}):\n")

    for match in matches:
        print(
            match["title"],
            "->",
            round(match["similarity"], 4)
        )