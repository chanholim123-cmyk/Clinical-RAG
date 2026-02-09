#!/usr/bin/env python3
"""
NG12 Vector Store - Usage Examples

This script demonstrates various ways to use the NG12VectorStore
for querying cancer risk assessment guidelines.
"""

import logging
from app.rag.vector_store import NG12VectorStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def example_basic_query():
    """Example 1: Basic semantic search."""
    logger.info("=" * 60)
    logger.info("Example 1: Basic Semantic Search")
    logger.info("=" * 60)

    vs = NG12VectorStore()

    # Simple symptom-based query
    query_text = "persistent cough and weight loss"
    logger.info(f"Query: '{query_text}'")

    results = vs.query(query_text, top_k=3)

    for i, result in enumerate(results, 1):
        logger.info(f"\nResult {i}:")
        logger.info(f"  Page: {result['page']}")
        logger.info(f"  Section: {result['section']} - {result['subsection']}")
        logger.info(f"  Recommendation: {result['recommendation_id']}")
        logger.info(f"  Urgency: {result['urgency_level']}")
        logger.info(f"  Relevance Score: {result['relevance_score']:.2%}")
        logger.info(f"  Text (first 150 chars): {result['text'][:150]}...")


def example_symptom_based_query():
    """Example 2: Query with patient context."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 2: Symptom-Based Query with Patient Context")
    logger.info("=" * 60)

    vs = NG12VectorStore()

    # Query with multiple symptoms and patient demographics
    symptoms = ["persistent cough", "hoarseness", "chest pain"]
    age = 72
    gender = "M"

    logger.info(f"Patient Profile:")
    logger.info(f"  Age: {age} years")
    logger.info(f"  Gender: {gender}")
    logger.info(f"  Symptoms: {', '.join(symptoms)}")

    results = vs.query_by_symptoms(
        symptoms=symptoms,
        age=age,
        gender=gender,
        top_k=5
    )

    logger.info(f"\nFound {len(results)} recommendations:\n")

    for i, result in enumerate(results, 1):
        urgency_str = f"[{result['urgency_level'].upper()}] " if result['urgency_level'] else ""
        logger.info(f"{i}. {urgency_str}{result['recommendation_id']}")
        logger.info(f"   Section: {result['section']}")
        logger.info(f"   Relevance: {result['relevance_score']:.2%}")
        logger.info(f"   {result['text'][:100]}...\n")


def example_section_context():
    """Example 3: Get all recommendations in a section."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 3: Section Context Retrieval")
    logger.info("=" * 60)

    vs = NG12VectorStore()

    # Retrieve all content from a specific section
    section = "1.1"
    logger.info(f"Retrieving all content from section {section}...\n")

    section_chunks = vs.get_section_context(section)

    if section_chunks:
        logger.info(f"Found {len(section_chunks)} chunks in section {section}:\n")

        for chunk in section_chunks[:5]:  # Show first 5
            logger.info(f"  {chunk['recommendation_id']}")
            logger.info(f"    Page: {chunk['page']}")
            logger.info(f"    {chunk['text'][:80]}...\n")

        if len(section_chunks) > 5:
            logger.info(f"  ... and {len(section_chunks) - 5} more chunks")
    else:
        logger.info(f"Section {section} not found")


def example_urgent_recommendations():
    """Example 4: Get all urgent recommendations."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 4: Urgent Recommendations")
    logger.info("=" * 60)

    vs = NG12VectorStore()

    logger.info("Retrieving urgent and very urgent recommendations...\n")

    urgent_items = vs.get_urgent_recommendations(top_k=20)

    if urgent_items:
        logger.info(f"Found {len(urgent_items)} urgent recommendations:\n")

        # Group by urgency level
        by_urgency = {}
        for item in urgent_items:
            urgency = item['urgency_level']
            if urgency not in by_urgency:
                by_urgency[urgency] = []
            by_urgency[urgency].append(item)

        for urgency_level in sorted(by_urgency.keys(), reverse=True):
            items = by_urgency[urgency_level]
            logger.info(f"\n{urgency_level.upper()} ({len(items)} items):")

            for item in items[:3]:  # Show first 3 per level
                logger.info(f"  {item['recommendation_id']} - Page {item['page']}")
                logger.info(f"    {item['text'][:70]}...\n")

            if len(items) > 3:
                logger.info(f"  ... and {len(items) - 3} more {urgency_level} items\n")
    else:
        logger.info("No urgent recommendations found")


def example_statistics():
    """Example 5: Get vector store statistics."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 5: Vector Store Statistics")
    logger.info("=" * 60)

    vs = NG12VectorStore()

    stats = vs.get_statistics()

    logger.info(f"\nVector Store Statistics:")
    logger.info(f"  Total Chunks: {stats['total_chunks']}")
    logger.info(f"  Sections: {len(stats['sections'])}")
    logger.info(f"  Subsections: {len(stats['subsections'])}")
    logger.info(f"  Has Urgency Metadata: {stats['has_urgency_metadata']}")

    logger.info(f"\n  Sections: {', '.join(stats['sections'][:10])}")
    if len(stats['sections']) > 10:
        logger.info(f"           ... and {len(stats['sections']) - 10} more")

    logger.info(f"\n  Subsections (first 10): {', '.join(stats['subsections'][:10])}")
    if len(stats['subsections']) > 10:
        logger.info(f"           ... and {len(stats['subsections']) - 10} more")


def example_multiple_queries():
    """Example 6: Series of related queries."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 6: Multiple Related Queries (Refinement)")
    logger.info("=" * 60)

    vs = NG12VectorStore()

    # Scenario: Narrow down recommendations based on additional information
    logger.info("Scenario: Patient with respiratory symptoms")
    logger.info("Starting broad, then narrowing based on findings...\n")

    # Query 1: General respiratory symptoms
    logger.info("Query 1: General respiratory symptoms")
    results1 = vs.query("persistent cough shortness of breath", top_k=3)
    logger.info(f"  Found {len(results1)} results")
    for r in results1:
        logger.info(f"    - {r['recommendation_id']}: {r['text'][:50]}...")

    # Query 2: Refine with additional context
    logger.info("\nQuery 2: Cough with hemoptysis (refined)")
    results2 = vs.query("cough with blood sputum hemoptysis malignancy", top_k=3)
    logger.info(f"  Found {len(results2)} results")
    for r in results2:
        logger.info(f"    - {r['recommendation_id']}: {r['text'][:50]}...")

    # Query 3: Check for urgent pathways
    logger.info("\nQuery 3: Check urgent referral pathways")
    results3 = vs.query("urgent referral pathway cancer suspected", top_k=3)
    logger.info(f"  Found {len(results3)} results")
    for r in results3:
        urgency = f"[{r['urgency_level']}]" if r['urgency_level'] else ""
        logger.info(f"    - {r['recommendation_id']} {urgency}: {r['text'][:50]}...")


def example_error_handling():
    """Example 7: Error handling."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 7: Error Handling")
    logger.info("=" * 60)

    vs = NG12VectorStore()

    # Example 1: Empty query
    logger.info("Test 1: Empty query")
    try:
        vs.query("")
    except ValueError as e:
        logger.info(f"  ✓ Caught expected error: {e}")

    # Example 2: Invalid symptom query
    logger.info("\nTest 2: Invalid symptom query (no symptoms)")
    try:
        vs.query_by_symptoms([], age=50, gender="M")
    except ValueError as e:
        logger.info(f"  ✓ Caught expected error: {e}")

    # Example 3: Invalid age
    logger.info("\nTest 3: Invalid age")
    try:
        vs.query_by_symptoms(["cough"], age=999, gender="M")
    except ValueError as e:
        logger.info(f"  ✓ Caught expected error: {e}")

    # Example 4: Invalid gender
    logger.info("\nTest 4: Invalid gender")
    try:
        vs.query_by_symptoms(["cough"], age=50, gender="X")
    except ValueError as e:
        logger.info(f"  ✓ Caught expected error: {e}")

    # Example 5: Invalid section
    logger.info("\nTest 5: Invalid section context")
    try:
        vs.get_section_context("")
    except ValueError as e:
        logger.info(f"  ✓ Caught expected error: {e}")


def example_real_world_scenario():
    """Example 8: Real-world clinical scenario."""
    logger.info("\n" + "=" * 60)
    logger.info("Example 8: Real-World Clinical Scenario")
    logger.info("=" * 60)

    vs = NG12VectorStore()

    logger.info("""
    Scenario: 68-year-old male with:
    - Persistent cough (6 weeks)
    - Hoarseness
    - Weight loss (10 lbs)
    - History of heavy smoking (quit 5 years ago)
    """)

    symptoms = [
        "persistent cough",
        "hoarseness",
        "weight loss"
    ]

    logger.info("Querying guidelines for this patient profile...")
    results = vs.query_by_symptoms(
        symptoms=symptoms,
        age=68,
        gender="M",
        top_k=10
    )

    logger.info(f"\nTop recommendations ({len(results)} found):\n")

    # Categorize by urgency
    urgent = [r for r in results if r['urgency_level'] in ['urgent', 'very_urgent']]
    consider = [r for r in results if r['urgency_level'] in ['consider']]
    other = [r for r in results if r['urgency_level'] is None]

    if urgent:
        logger.info("URGENT - Immediate Action:")
        for r in urgent:
            logger.info(f"  → {r['recommendation_id']} (Page {r['page']})")
            logger.info(f"    Score: {r['relevance_score']:.2%}")
            logger.info(f"    {r['text'][:100]}...\n")

    if consider:
        logger.info("\nCONSIDER - Further Assessment:")
        for r in consider:
            logger.info(f"  → {r['recommendation_id']} (Page {r['page']})")
            logger.info(f"    Score: {r['relevance_score']:.2%}\n")

    if other:
        logger.info(f"\nOTHER - {len(other)} general recommendations")

    # Get full context for top recommendation
    if results:
        top_section = results[0]['section']
        logger.info(f"\nFull context for section {top_section}:")
        section_context = vs.get_section_context(top_section)
        if section_context:
            logger.info(f"  Total recommendations in section: {len(section_context)}")


def main():
    """Run all examples."""
    logger.info("NG12 Vector Store - Usage Examples\n")

    try:
        # Run examples
        example_basic_query()
        example_symptom_based_query()
        example_section_context()
        example_urgent_recommendations()
        example_statistics()
        example_multiple_queries()
        example_error_handling()
        example_real_world_scenario()

        logger.info("\n" + "=" * 60)
        logger.info("All examples completed successfully!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error running examples: {e}")
        logger.info("\nMake sure to run the ingestion script first:")
        logger.info("  python scripts/ingest_pdf.py --pdf-path /path/to/NG12.pdf")
        raise


if __name__ == "__main__":
    main()
