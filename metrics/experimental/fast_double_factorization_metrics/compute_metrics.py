import numpy as np
def compute_hypergraph_metrics(pauli_hamiltonian):
    # Initialize the nodes and weighted hyperedges
    nodes = set()
    weighted_hyperedges = []

    # Populate nodes and weighted hyperedges from the Pauli strings
    for pauli_string, weight in pauli_hamiltonian.items():
        if pauli_string:  # Ignore the empty key corresponding to the identity operator
            qubits_in_string = set(qubit for qubit, _ in pauli_string)
            nodes.update(qubits_in_string)
            weighted_hyperedges.append((qubits_in_string, weight))

    # Convert nodes to a sorted list for consistent ordering
    nodes = sorted(nodes)

    # Compute statistics
    weights = [abs(weight) for _, weight in weighted_hyperedges]
    vertex_degree = {node: 0 for node in nodes}
    edge_orders = [len(edge) for edge, _ in weighted_hyperedges]

    for edge, weight in weighted_hyperedges:
        for node in edge:
            vertex_degree[node] += 1

    weight_stats = {
        "one_norm": sum(weights),
        "max_weight": np.max(weights),
        "min_weight": np.min(weights),
        "mean_weight": np.mean(weights),
        "std_dev_weight": np.std(weights)
    }

    # Calculate statistics for vertex degree
    vertex_degrees = list(vertex_degree.values())
    vertex_degree_stats = {
        "max_vertex_degree": np.max(vertex_degrees),
        "min_vertex_degree": np.min(vertex_degrees),
        "mean_vertex_degree": np.mean(vertex_degrees),
        "std_dev_vertex_degree": np.std(vertex_degrees)
    }

    # Calculate statistics for edge orders
    edge_order_stats = {
        "max_edge_order": np.max(edge_orders),
        "min_edge_order": np.min(edge_orders),
        "mean_edge_order": np.mean(edge_orders),
        "std_dev_edge_order": np.std(edge_orders)
    }

    return vertex_degree_stats, weight_stats, edge_order_stats
