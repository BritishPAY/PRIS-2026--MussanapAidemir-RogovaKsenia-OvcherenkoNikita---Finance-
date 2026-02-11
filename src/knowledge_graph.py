# src/knowledge_graph.py
import networkx as nx


def create_graph():
    # Создаем пустой граф
    G = nx.Graph()

    # --- 1. ДОБАВЛЕНИЕ УЗЛОВ (NODES) ---

    # Магазины / сервисы (источники транзакций)
    stores = ["Uber", "Magnum", "Starbucks"]
    G.add_nodes_from(stores, type="store")

    # Категории расходов
    categories = ["Такси", "Еда", "Кофе"]
    G.add_nodes_from(categories, type="category")

    # Месяцы
    months = ["Январь", "Февраль", "Март"]
    G.add_nodes_from(months, type="month")

    # --- 2. ДОБАВЛЕНИЕ СВЯЗЕЙ (EDGES) ---
    # Магазин -> Категория
    relationships = [
        ("Uber", "Такси"),
        ("Magnum", "Еда"),
        ("Starbucks", "Кофе"),

        # Категория -> Месяц (пример агрегации по времени)
        ("Такси", "Январь"),
        ("Еда", "Февраль"),
        ("Кофе", "Март"),
    ]

    G.add_edges_from(relationships)

    return G


def find_related_entities(graph, start_node):
    """
    Универсальный поиск:
    Найти все объекты, связанные с start_node
    (например: магазин -> категория)
    """
    if start_node not in graph:
        return []

    neighbors = list(graph.neighbors(start_node))
    return neighbors


# Пример использования
if __name__ == "__main__":
    graph = create_graph()

    store = "Starbucks"
    related = find_related_entities(graph, store)

    print(f"Объекты, связанные с '{store}': {related}")
