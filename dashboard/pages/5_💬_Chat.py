"""
Prime Wheels SL — 💬 Chat with the Market Dashboard Tab.
Connects to the CRAG pipeline via the FastAPI backend.
"""

import os

import requests
import streamlit as st

st.set_page_config(page_title="Chat with Market — Prime Wheels SL", page_icon="💬", layout="wide")
st.title("💬 Chat with the Vehicle Market")
st.caption("Ask anything about Sri Lankan vehicles — powered by RAG")

API_URL = os.getenv("API_URL", "http://localhost:8000")

# ── Chat History ──
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("vehicles"):
            with st.expander("🚗 Vehicles mentioned"):
                for v in message["vehicles"]:
                    st.write(f"- **{v.get('make', '')} {v.get('model', '')} {v.get('year', '')}** "
                             f"— Rs. {v.get('price_lkr', 'N/A'):,}" if isinstance(v.get('price_lkr'), (int, float))
                             else f"- **{v.get('make', '')} {v.get('model', '')}**")
        if message.get("metadata"):
            meta = message["metadata"]
            st.caption(
                f"⏱️ {meta.get('response_time_ms', '?')}ms | "
                f"📄 {meta.get('num_docs', '?')} docs | "
                f"🎯 Relevance: {meta.get('avg_relevance', '?')} | "
                f"{'⚡ Cache' if meta.get('cache_hit') else '🔄 Fresh'}"
            )

# ── Chat Input ──
if prompt := st.chat_input("Ask about vehicles in Sri Lanka..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call API
    with st.chat_message("assistant"):
        with st.spinner("🔍 Searching vehicle listings..."):
            try:
                response = requests.post(
                    f"{API_URL}/api/v1/query",
                    json={"query": prompt},
                    timeout=30,
                )
                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("answer", "Sorry, I couldn't generate an answer.")
                    st.markdown(answer)

                    vehicles = data.get("vehicles_mentioned", [])
                    if vehicles:
                        with st.expander("🚗 Vehicles mentioned"):
                            for v in vehicles:
                                price = v.get("price_lkr")
                                price_str = f"Rs. {price:,.0f}" if isinstance(price, (int, float)) else "N/A"
                                url = v.get("url", "#")
                                st.write(
                                    f"- **{v.get('make', '')} {v.get('model', '')} "
                                    f"{v.get('year', '')}** — {price_str} "
                                    f"[🔗 View]({url})"
                                )

                    # Suggestions
                    suggestions = data.get("follow_up_suggestions", [])
                    if suggestions:
                        st.caption("💡 **Suggested follow-ups:**")
                        for s in suggestions:
                            st.caption(f"  • {s}")

                    # Metadata
                    meta = {
                        "response_time_ms": data.get("response_time_ms"),
                        "num_docs": data.get("num_docs_retrieved"),
                        "avg_relevance": data.get("avg_relevance"),
                        "cache_hit": data.get("cache_hit"),
                    }
                    avg_rel = meta["avg_relevance"]
                    avg_rel_str = f"{avg_rel:.2f}" if isinstance(avg_rel, (int, float)) else "N/A"
                    st.caption(
                        f"⏱️ {meta['response_time_ms']}ms | "
                        f"📄 {meta['num_docs']} docs | "
                        f"🎯 {avg_rel_str} relevance | "
                        f"{'⚡ Cached' if meta['cache_hit'] else '🔄 Fresh query'}"
                    )

                    # Save to history
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "vehicles": vehicles,
                        "metadata": meta,
                    })
                else:
                    st.error(f"API error: {response.status_code}")
            except requests.exceptions.ConnectionError:
                st.error(
                    "⚠️ Cannot connect to the API server. "
                    "Make sure the FastAPI backend is running on "
                    f"{API_URL}"
                )
            except Exception as e:
                st.error(f"Error: {e}")

# ── Sidebar: Example Questions ──
with st.sidebar:
    st.header("💡 Example Questions")
    examples = [
        "Best hybrid SUV under Rs. 10 million in Colombo?",
        "Compare Toyota Corolla vs Honda Civic 2020",
        "What's the average price of a Toyota Aqua 2018?",
        "Cheapest automatic car available in Gampaha?",
        "Which vehicles have the lowest depreciation?",
        "Show me diesel vans under Rs. 5 million",
        "What are the most popular cars in Kandy?",
        "Electric vehicles available in Sri Lanka",
    ]
    for example in examples:
        if st.button(example, key=f"ex_{hash(example)}", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": example})
            st.rerun()
