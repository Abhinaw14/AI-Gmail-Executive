"""

memory/graph_memory.py — NetworkX-based in-memory knowledge graph.
Persisted to disk as a pickle file.

Node types:  Person, Topic, Project, Decision, Task
Edge types:  discussed, assigned_to, related_to, decided, participated_in
"""
import os
import pickle
import networkx as nx
from typing import Optional
from config import get_settings

settings = get_settings()


class GraphMemory:
    def __init__(self, path: str = None):
        self.path = path or settings.graph_memory_path
        self.G = self._load()

    # ------------------------------------------------------------------ load/save
    def _load(self) -> nx.DiGraph:
        if os.path.exists(self.path):
            with open(self.path, "rb") as f:
                return pickle.load(f)
        return nx.DiGraph()

    def save(self):
        with open(self.path, "wb") as f:
            pickle.dump(self.G, f)

    # ------------------------------------------------------------------ nodes
    def add_node(self, node_id: str, node_type: str, **attrs):
        self.G.add_node(node_id, type=node_type, **attrs)

    def add_edge(self, src: str, dst: str, relation: str, **attrs):
        self.G.add_edge(src, dst, relation=relation, **attrs)

    # ------------------------------------------------------------------ email ingestion
    def add_email_to_graph(self, email: dict):
        """
        Given a parsed email dict, extract entities and add to graph.
        email keys: sender, recipients, subject, classification, thread_id,
                    extracted_topics (list), extracted_projects (list),
                    extracted_decisions (list), extracted_tasks (list)
        """
        sender = email.get("sender", "")
        subject = email.get("subject", "")
        thread_id = email.get("thread_id", "")

        # Sender node
        self.add_node(sender, "Person", name=email.get("sender_name", sender))

        # Recipients
        for r in email.get("recipients", []):
            self.add_node(r, "Person")
            self.add_edge(sender, r, "sent_to", thread_id=thread_id)

        # Topics
        for topic in email.get("extracted_topics", []):
            topic_id = f"topic:{topic.lower()}"
            self.add_node(topic_id, "Topic", label=topic)
            self.add_edge(sender, topic_id, "discussed", subject=subject, thread_id=thread_id)

        # Projects
        for proj in email.get("extracted_projects", []):
            proj_id = f"project:{proj.lower()}"
            self.add_node(proj_id, "Project", label=proj)
            self.add_edge(sender, proj_id, "related_to", thread_id=thread_id)

        # Decisions
        for dec in email.get("extracted_decisions", []):
            dec_id = f"decision:{dec[:40].lower().replace(' ', '_')}"
            self.add_node(dec_id, "Decision", label=dec)
            self.add_edge(sender, dec_id, "decided", thread_id=thread_id)

        # Tasks
        for task in email.get("extracted_tasks", []):
            task_id = f"task:{task[:40].lower().replace(' ', '_')}"
            self.add_node(task_id, "Task", label=task)
            self.add_edge(sender, task_id, "assigned_to", thread_id=thread_id)

        self.save()

    # ------------------------------------------------------------------ queries
    def get_neighbors(self, node_id: str, relation: Optional[str] = None) -> list[dict]:
        result = []
        for _, nbr, data in self.G.out_edges(node_id, data=True):
            if relation is None or data.get("relation") == relation:
                nbr_data = self.G.nodes[nbr]
                result.append({"node": nbr, **nbr_data, **data})
        return result

    def search_nodes(self, query: str, node_type: Optional[str] = None) -> list[dict]:
        """Simple substring search over node labels."""
        results = []
        query_lower = query.lower()
        for node, data in self.G.nodes(data=True):
            if node_type and data.get("type") != node_type:
                continue
            label = data.get("label", node).lower()
            if query_lower in label or query_lower in node.lower():
                results.append({"node": node, **data})
        return results[:10]

    def get_person_summary(self, email_addr: str) -> dict:
        """Returns topics, projects, tasks discussed by a person."""
        if email_addr not in self.G:
            return {}
        out = {"topics": [], "projects": [], "decisions": [], "tasks": [], "contacts": []}
        for _, nbr, data in self.G.out_edges(email_addr, data=True):
            nbr_type = self.G.nodes[nbr].get("type", "")
            label = self.G.nodes[nbr].get("label", nbr)
            rel = data.get("relation", "")
            if nbr_type == "Topic":
                out["topics"].append(label)
            elif nbr_type == "Project":
                out["projects"].append(label)
            elif nbr_type == "Decision":
                out["decisions"].append(label)
            elif nbr_type == "Task":
                out["tasks"].append(label)
            elif nbr_type == "Person":
                out["contacts"].append(nbr)
        return out

    def get_top_entities(self, limit: int = 5, node_type: Optional[str] = None) -> list[tuple[str, int]]:
        """Return nodes with highest degree (most connections)."""
        candidates = []
        for node, data in self.G.nodes(data=True):
            if node_type and data.get("type") != node_type:
                continue
            deg = self.G.degree(node)
            label = data.get("label", data.get("name", node))
            candidates.append((label, deg))
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:limit]

    def stats(self) -> dict:
        return {
            "nodes": self.G.number_of_nodes(),
            "edges": self.G.number_of_edges(),
        }


# Singleton
_graph: Optional[GraphMemory] = None


def get_graph_memory() -> GraphMemory:
    global _graph
    if _graph is None:
        _graph = GraphMemory()
    return _graph
