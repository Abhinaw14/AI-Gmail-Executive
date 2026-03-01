"""
agents/retrieval_agent.py — Hybrid RAG + Graph retrieval.
Combines ChromaDB semantic search with NetworkX graph context.
"""
from memory.vector_store import get_vector_store
from memory.graph_memory import get_graph_memory


def retrieve_context(
    query: str,
    sender: str = "",
    n_results: int = 5,
) -> dict:
    """
    Retrieve relevant context for a given query.
    Returns:
        {
          "vector_results": [...],
          "graph_summary": {...},
          "combined_context": "<formatted string for prompt injection>"
        }
    """
    vs = get_vector_store()
    gm = get_graph_memory()

    # --- Vector retrieval ---
    where_filter = {"sender": sender} if sender else None
    email_results = vs.query("emails", query, n_results=n_results, where=where_filter)
    doc_results = vs.query("documents", query, n_results=3)

    # --- Graph retrieval ---
    graph_summary = gm.get_person_summary(sender) if sender else {}
    topic_nodes = gm.search_nodes(query, node_type="Topic")[:5]

    # --- Format context ---
    parts = []

    if email_results:
        parts.append("## Relevant Past Emails")
        for r in email_results:
            meta = r.get("metadata", {})
            parts.append(
                f"- From: {meta.get('sender','')} | Subject: {meta.get('subject','')}\n"
                f"  {r['text'][:300]}..."
            )

    if doc_results:
        parts.append("\n## Relevant Documents")
        for r in doc_results:
            meta = r.get("metadata", {})
            parts.append(f"- {meta.get('filename','doc')}: {r['text'][:200]}...")

    if graph_summary:
        parts.append("\n## Sender Knowledge Graph")
        if graph_summary.get("topics"):
            parts.append(f"- Topics discussed: {', '.join(graph_summary['topics'][:5])}")
        if graph_summary.get("projects"):
            parts.append(f"- Projects: {', '.join(graph_summary['projects'][:3])}")
        if graph_summary.get("decisions"):
            parts.append(f"- Past decisions: {', '.join(graph_summary['decisions'][:3])}")

    if topic_nodes:
        parts.append("\n## Related Topics in Graph")
        parts.append(", ".join(n.get("label", n["node"]) for n in topic_nodes))

    combined_context = "\n".join(parts) if parts else "No prior context available."

    return {
        "vector_results": email_results + doc_results,
        "graph_summary": graph_summary,
        "combined_context": combined_context,
    }
