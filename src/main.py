# src/main.py
import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt

# Предполагается, что у вас есть файл knowledge_graph.py
from knowledge_graph import create_graph, find_related_entities

st.title("Knowledge Graph Explorer 🕸")

# 1. Загружаем граф один раз (лучше кэшировать)
@st.cache_resource
def load_graph():
    return create_graph()

G = load_graph()

# 2. Выбор узла
all_nodes = sorted(list(G.nodes()))
selected_node = st.selectbox(
    "Выберите объект для поиска связей:",
    options=["(все)"] + all_nodes,
    index=0
)

# 3. Поиск связей
if st.button("Найти связи") or selected_node != "(все)":
    if selected_node == "(все)":
        st.info("Выбраны все узлы. Показан полный граф ниже.")
        results = []
    else:
        results = find_related_entities(G, selected_node)
        st.success(f"Объект **{selected_node}** связан с:  \n**{', '.join(results) or '— ничего не найдено'}**")

# 4. Визуализация
st.subheader("Визуализация графа")

fig, ax = plt.subplots(figsize=(10, 8))

# Можно поэкспериментировать с раскладками:
# pos = nx.spring_layout(G, k=0.7, iterations=80)
# pos = nx.kamada_kawai_layout(G)
pos = nx.nx_agraph.graphviz_layout(G, prog="twopi")   # красивее, но требует pygraphviz

nx.draw(
    G, pos,
    with_labels=True,
    node_color='lightblue',
    edge_color='gray',
    node_size=2200,
    font_size=9,
    font_weight='bold',
    arrows=True,
    ax=ax
)

st.pyplot(fig)
