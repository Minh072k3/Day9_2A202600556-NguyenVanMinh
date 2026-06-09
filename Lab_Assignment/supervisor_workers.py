"""
Lab Assignment - Cải tiến Agent Day08 sử dụng Supervisor - Workers Pattern

Kiến trúc Supervisor - Workers (3 Workers):

    ┌─────────────────────────────────────────────────────┐
    │                   SUPERVISOR                         │
    │  Phân tích câu hỏi → lập kế hoạch → giao việc      │
    └───────────┬──────────────┬──────────────┬───────────┘
                │              │              │
    ┌───────────▼──┐ ┌────────▼────────┐ ┌──▼──────────────┐
    │  RETRIEVAL   │ │ LEGAL ANALYSIS  │ │ CITATION        │
    │  WORKER      │ │ WORKER          │ │ GENERATOR       │
    │              │ │                 │ │ WORKER          │
    │ • Semantic   │ │ • Phân tích     │ │ • Reorder       │
    │   Search     │ │   luật áp dụng  │ │   chunks        │
    │ • Lexical    │ │ • Xác định      │ │ • Format        │
    │   Search     │ │   hình phạt     │ │   context       │
    │ • Reranking  │ │ • Trích dẫn     │ │ • Generate      │
    │   (RRF)      │ │   điều luật     │ │   with citation │
    └──────────────┘ └─────────────────┘ └─────────────────┘
                │              │              │
    ┌───────────▼──────────────▼──────────────▼───────────┐
    │                   SYNTHESIZER                        │
    │  Tổng hợp kết quả → Báo cáo pháp lý cuối cùng     │
    └─────────────────────────────────────────────────────┘

Cải tiến so với Day08:
    1. Day08: pipeline tuần tự (retrieve → generate) — monolithic
    2. Day09: Supervisor phân tích câu hỏi, giao việc song song cho 3 workers
       chuyên biệt, rồi tổng hợp — modular, parallel, scalable
    3. Thêm Legal Analysis Worker chuyên phân tích luật áp dụng
    4. Tách riêng Citation Generator để đảm bảo chất lượng citation
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Annotated, TypedDict

# Cho phép chạy từ thư mục Lab_Assignment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.constants import Send
from langgraph.graph import END, StateGraph

from common.llm import get_llm


# ---------------------------------------------------------------------------
# Simulated RAG Knowledge Base (tái sử dụng ý tưởng từ Day08)
# Trong production, đây sẽ kết nối tới ChromaDB + BM25 index thật
# ---------------------------------------------------------------------------

DRUG_LAW_KNOWLEDGE = [
    {
        "id": "dieu_248_blhs",
        "keywords": ["tàng trữ", "ma túy", "ma tuý", "chất cấm", "248", "trái phép"],
        "text": (
            "Điều 248 BLHS 2015 (sửa đổi 2017) - Tội tàng trữ trái phép chất ma tuý: "
            "Phạt tù 1-5 năm (Heroin/Cocaine dưới 1g hoặc chất ma tuý khác dưới tương đương). "
            "Phạt tù 5-10 năm (Heroin/Cocaine 1g-dưới 30g). "
            "Phạt tù 10-15 năm (Heroin/Cocaine 30g-dưới 100g). "
            "Phạt tù 15-20 năm hoặc tù chung thân (Heroin/Cocaine 100g trở lên)."
        ),
        "source": "Bộ luật Hình sự 2015",
        "type": "legal",
    },
    {
        "id": "dieu_249_blhs",
        "keywords": ["vận chuyển", "ma túy", "ma tuý", "249", "buôn bán"],
        "text": (
            "Điều 249 BLHS 2015 - Tội vận chuyển trái phép chất ma tuý: "
            "Khung hình phạt tương tự Điều 248, có thể bị tịch thu phương tiện vận chuyển. "
            "Người tổ chức vận chuyển bị xử lý với vai trò chủ mưu, tình tiết tăng nặng."
        ),
        "source": "Bộ luật Hình sự 2015",
        "type": "legal",
    },
    {
        "id": "dieu_250_blhs",
        "keywords": ["mua bán", "ma túy", "ma tuý", "250", "buôn bán", "phân phối"],
        "text": (
            "Điều 250 BLHS 2015 - Tội mua bán trái phép chất ma tuý: "
            "Phạt tù 2-7 năm (lượng nhỏ). Phạt tù 7-15 năm (có tổ chức, tái phạm). "
            "Phạt tù 15-20 năm (lượng lớn). Tử hình (lượng đặc biệt lớn hoặc có tình tiết "
            "tăng nặng đặc biệt). Ngoài ra có thể bị phạt tiền 5-500 triệu VNĐ."
        ),
        "source": "Bộ luật Hình sự 2015",
        "type": "legal",
    },
    {
        "id": "luat_phong_chong_2021",
        "keywords": ["phòng chống", "cai nghiện", "2021", "quản lý", "kiểm soát"],
        "text": (
            "Luật Phòng, chống ma tuý 2021 (Luật 73/2021/QH15): "
            "Quy định về phòng ngừa, quản lý người sử dụng trái phép chất ma tuý, "
            "cai nghiện bắt buộc tại cơ sở (thời hạn 12-24 tháng), "
            "cai nghiện tự nguyện tại gia đình và cộng đồng. "
            "Trách nhiệm của gia đình, cơ quan, tổ chức trong phòng chống ma tuý."
        ),
        "source": "Luật Phòng chống ma tuý 2021",
        "type": "legal",
    },
    {
        "id": "nghi_dinh_105",
        "keywords": ["nghị định", "105", "hướng dẫn", "danh mục", "tiền chất"],
        "text": (
            "Nghị định 105/2021/NĐ-CP: Quy định chi tiết và hướng dẫn thi hành "
            "Luật Phòng chống ma tuý 2021. Bao gồm: danh mục chất ma tuý và tiền chất, "
            "thủ tục đưa vào cơ sở cai nghiện bắt buộc, "
            "quản lý sau cai nghiện, trách nhiệm của các cơ quan."
        ),
        "source": "Nghị định 105/2021/NĐ-CP",
        "type": "legal",
    },
    {
        "id": "nghe_si_1",
        "keywords": ["nghệ sĩ", "bắt", "sử dụng", "ca sĩ", "diễn viên", "showbiz"],
        "text": (
            "Nhiều nghệ sĩ Việt Nam đã bị bắt vì liên quan tới ma tuý: "
            "sử dụng trái phép chất ma tuý tại các bữa tiệc, quán bar. "
            "Theo Điều 252 BLHS, sử dụng trái phép chất ma tuý bị phạt tù 3 tháng - 2 năm. "
            "Ngoài hình phạt tù, các nghệ sĩ còn bị ảnh hưởng nghiêm trọng về sự nghiệp."
        ),
        "source": "VnExpress, 2024",
        "type": "news",
    },
    {
        "id": "xu_ly_hanh_chinh",
        "keywords": ["hành chính", "phạt", "xử phạt", "vi phạm", "sử dụng"],
        "text": (
            "Xử phạt hành chính về ma tuý (Nghị định 144/2021/NĐ-CP): "
            "Sử dụng trái phép chất ma tuý: phạt tiền 1-2 triệu VNĐ (lần đầu). "
            "Tái phạm: phạt 2-5 triệu VNĐ và đưa vào cơ sở cai nghiện bắt buộc. "
            "Tổ chức sử dụng: phạt 10-20 triệu VNĐ."
        ),
        "source": "Nghị định 144/2021/NĐ-CP",
        "type": "legal",
    },
]


# ---------------------------------------------------------------------------
# Tools cho các Workers
# ---------------------------------------------------------------------------

@tool
def semantic_search(query: str, top_k: int = 5) -> str:
    """Tìm kiếm ngữ nghĩa trong knowledge base pháp luật về ma tuý.

    Args:
        query: Câu truy vấn tìm kiếm.
        top_k: Số kết quả tối đa trả về.
    """
    query_lower = query.lower()
    scored = []
    for entry in DRUG_LAW_KNOWLEDGE:
        overlap = sum(1 for kw in entry["keywords"] if kw in query_lower)
        if overlap > 0:
            scored.append((overlap, entry))
    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, entry in scored[:top_k]:
        results.append(
            f"[{entry['id']}] (Source: {entry['source']}, Score: {score/len(entry['keywords']):.2f})\n"
            f"{entry['text']}"
        )
    return "\n\n---\n\n".join(results) if results else "Không tìm thấy kết quả phù hợp."


@tool
def lexical_search(query: str, top_k: int = 5) -> str:
    """Tìm kiếm từ khóa (BM25-style) trong knowledge base.

    Args:
        query: Câu truy vấn tìm kiếm.
        top_k: Số kết quả tối đa.
    """
    query_words = set(query.lower().split())
    scored = []
    for entry in DRUG_LAW_KNOWLEDGE:
        text_words = set(entry["text"].lower().split())
        overlap = len(query_words & text_words)
        if overlap > 0:
            scored.append((overlap, entry))
    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, entry in scored[:top_k]:
        results.append(
            f"[{entry['id']}] (Source: {entry['source']}, BM25 Score: {score})\n"
            f"{entry['text']}"
        )
    return "\n\n---\n\n".join(results) if results else "Không tìm thấy kết quả phù hợp."


@tool
def analyze_law_article(query: str) -> str:
    """Phân tích điều luật áp dụng cho một tình huống cụ thể.

    Args:
        query: Mô tả tình huống pháp lý cần phân tích.
    """
    query_lower = query.lower()
    applicable = []
    for entry in DRUG_LAW_KNOWLEDGE:
        if entry["type"] == "legal":
            overlap = sum(1 for kw in entry["keywords"] if kw in query_lower)
            if overlap > 0:
                applicable.append((overlap, entry))

    applicable.sort(key=lambda x: x[0], reverse=True)
    if not applicable:
        return "Không tìm thấy điều luật áp dụng."

    result = "CÁC ĐIỀU LUẬT ÁP DỤNG:\n\n"
    for _, entry in applicable[:3]:
        result += f"📜 {entry['source']} ({entry['id']}):\n{entry['text']}\n\n"
    return result


# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------

def _last_wins(a: str, b: str) -> str:
    return b if b else a


class RAGState(TypedDict):
    question: str
    supervisor_plan: str
    workers_needed: list[str]
    retrieval_result: Annotated[str, _last_wins]
    legal_analysis_result: Annotated[str, _last_wins]
    citation_result: Annotated[str, _last_wins]
    final_answer: str


# ---------------------------------------------------------------------------
# SUPERVISOR — Phân tích câu hỏi và điều phối workers
# ---------------------------------------------------------------------------

async def supervisor(state: RAGState) -> dict:
    """Supervisor phân tích câu hỏi và lập kế hoạch giao việc."""
    print("\n🎯 [SUPERVISOR] Đang phân tích câu hỏi...")
    llm = get_llm()

    messages = [
        SystemMessage(content=(
            'Bạn là Supervisor điều phối hệ thống RAG pháp luật về ma tuý.\n'
            'Phân tích câu hỏi và quyết định workers nào cần hoạt động.\n\n'
            'Workers:\n'
            '- retrieval_worker: tìm kiếm thông tin (semantic + lexical search)\n'
            '- legal_analysis_worker: phân tích luật áp dụng và hình phạt\n'
            '- citation_worker: tạo câu trả lời có trích dẫn nguồn\n\n'
            'Trả lời ONLY valid JSON:\n'
            '{"plan": "<kế hoạch ngắn gọn>", "workers": ["worker1", ...]}\n\n'
            'Luôn gọi retrieval_worker để tìm dữ liệu. Gọi legal_analysis_worker '
            'khi câu hỏi liên quan đến hình phạt, điều luật. Luôn gọi citation_worker cuối cùng.'
        )),
        HumanMessage(content=state["question"]),
    ]

    result = await llm.ainvoke(messages)
    raw = result.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {
            "plan": "Tìm kiếm toàn diện và phân tích pháp lý",
            "workers": ["retrieval_worker", "legal_analysis_worker", "citation_worker"],
        }

    plan = parsed.get("plan", "Phân tích toàn diện")
    workers = parsed.get("workers", ["retrieval_worker", "legal_analysis_worker", "citation_worker"])

    print(f"   📋 Kế hoạch: {plan}")
    print(f"   👷 Workers được giao: {', '.join(workers)}")

    return {"supervisor_plan": plan, "workers_needed": workers}


# ---------------------------------------------------------------------------
# Dispatch workers (song song cho retrieval + legal, tuần tự cho citation)
# ---------------------------------------------------------------------------

def dispatch_workers(state: RAGState) -> list[Send]:
    """Gửi công việc đến các workers (song song khi có thể)."""
    sends: list[Send] = []
    workers = state.get("workers_needed", [])

    # Retrieval và Legal Analysis chạy song song
    if "retrieval_worker" in workers:
        sends.append(Send("retrieval_worker", state))
    if "legal_analysis_worker" in workers:
        sends.append(Send("legal_analysis_worker", state))

    if not sends:
        sends.append(Send("citation_worker", state))

    return sends


# ---------------------------------------------------------------------------
# WORKER 1: Retrieval Worker (Semantic + Lexical + Reranking)
# ---------------------------------------------------------------------------

async def retrieval_worker(state: RAGState) -> dict:
    """Worker tìm kiếm thông tin bằng hybrid search (semantic + lexical)."""
    from langgraph.prebuilt import create_react_agent

    print("\n🔍 [RETRIEVAL WORKER] Đang tìm kiếm thông tin...")

    prompt = (
        "Bạn là chuyên gia tìm kiếm thông tin pháp luật. "
        "Sử dụng CẢNH HAI tools: semantic_search VÀ lexical_search để tìm kiếm toàn diện. "
        "Gọi semantic_search trước để tìm theo ngữ nghĩa, sau đó lexical_search để tìm theo từ khóa. "
        "Tổng hợp kết quả từ cả hai nguồn, loại bỏ trùng lặp. "
        "Trả về tất cả thông tin tìm được, không cắt bớt."
    )

    llm = get_llm()
    agent = create_react_agent(model=llm, tools=[semantic_search, lexical_search], prompt=prompt)
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": f"Tìm kiếm thông tin liên quan: {state['question']}"}]}
    )

    final_msg = result["messages"][-1].content
    print(f"   ✅ [RETRIEVAL WORKER] Hoàn thành ({len(final_msg)} ký tự)")
    return {"retrieval_result": final_msg}


# ---------------------------------------------------------------------------
# WORKER 2: Legal Analysis Worker (Phân tích luật áp dụng)
# ---------------------------------------------------------------------------

async def legal_analysis_worker(state: RAGState) -> dict:
    """Worker phân tích luật pháp áp dụng cho câu hỏi."""
    from langgraph.prebuilt import create_react_agent

    print("\n⚖️  [LEGAL ANALYSIS WORKER] Đang phân tích luật áp dụng...")

    prompt = (
        "Bạn là luật sư chuyên về hình sự và luật phòng chống ma tuý Việt Nam. "
        "Sử dụng tool analyze_law_article để tra cứu các điều luật áp dụng. "
        "Phân tích cụ thể:\n"
        "1. Điều luật nào áp dụng (số điều, tên luật)\n"
        "2. Khung hình phạt cụ thể\n"
        "3. Các tình tiết tăng nặng/giảm nhẹ\n"
        "Trả lời bằng tiếng Việt, có cấu trúc rõ ràng."
    )

    llm = get_llm()
    agent = create_react_agent(model=llm, tools=[analyze_law_article], prompt=prompt)
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": state["question"]}]}
    )

    final_msg = result["messages"][-1].content
    print(f"   ✅ [LEGAL ANALYSIS WORKER] Hoàn thành ({len(final_msg)} ký tự)")
    return {"legal_analysis_result": final_msg}


# ---------------------------------------------------------------------------
# WORKER 3: Citation Generator Worker (Sinh câu trả lời có citation)
# ---------------------------------------------------------------------------

async def citation_worker(state: RAGState) -> dict:
    """Worker tạo câu trả lời cuối cùng có citation từ dữ liệu đã thu thập."""
    print("\n📝 [CITATION WORKER] Đang tạo câu trả lời có citation...")
    llm = get_llm()

    # Tổng hợp context từ các workers khác
    context_parts = []
    if state.get("retrieval_result"):
        context_parts.append(f"=== KẾT QUẢ TÌM KIẾM ===\n{state['retrieval_result']}")
    if state.get("legal_analysis_result"):
        context_parts.append(f"=== PHÂN TÍCH PHÁP LÝ ===\n{state['legal_analysis_result']}")

    context = "\n\n".join(context_parts)

    messages = [
        SystemMessage(content=(
            "Bạn tạo câu trả lời pháp lý có CITATION (trích dẫn nguồn). "
            "Quy tắc bắt buộc:\n"
            "1. MỌI thông tin phải có citation dạng [Nguồn, Năm/Điều]\n"
            "   Ví dụ: [BLHS 2015, Điều 248], [Luật PCMT 2021, Điều 3]\n"
            "2. Nếu không có đủ bằng chứng → nói rõ 'Không thể xác minh'\n"
            "3. Trả lời bằng tiếng Việt, cấu trúc rõ ràng\n"
            "4. Kết thúc bằng DANH MỤC NGUỒN THAM KHẢO"
        )),
        HumanMessage(content=(
            f"Câu hỏi: {state['question']}\n\n"
            f"Dữ liệu tham khảo:\n{context}\n\n"
            "Hãy tạo câu trả lời hoàn chỉnh có citation."
        )),
    ]

    result = await llm.ainvoke(messages)
    print(f"   ✅ [CITATION WORKER] Hoàn thành ({len(result.content)} ký tự)")
    return {"citation_result": result.content}


# ---------------------------------------------------------------------------
# SYNTHESIZER — Tổng hợp cuối cùng
# ---------------------------------------------------------------------------

async def synthesizer(state: RAGState) -> dict:
    """Tổng hợp kết quả từ tất cả workers thành báo cáo cuối cùng."""
    print("\n📊 [SYNTHESIZER] Đang tổng hợp báo cáo cuối cùng...")
    llm = get_llm()

    sections = []
    if state.get("retrieval_result"):
        sections.append(f"## 🔍 Kết Quả Tìm Kiếm\n{state['retrieval_result']}")
    if state.get("legal_analysis_result"):
        sections.append(f"## ⚖️ Phân Tích Pháp Lý\n{state['legal_analysis_result']}")
    if state.get("citation_result"):
        sections.append(f"## 📝 Câu Trả Lời Có Citation\n{state['citation_result']}")

    combined = "\n\n---\n\n".join(sections)

    messages = [
        SystemMessage(content=(
            "Bạn là trưởng nhóm tư vấn pháp luật. Tổng hợp các phân tích thành "
            "BÁO CÁO PHÁP LÝ HOÀN CHỈNH bằng tiếng Việt.\n\n"
            "Cấu trúc báo cáo:\n"
            "1. TÓM TẮT: 2-3 câu tóm tắt vấn đề\n"
            "2. PHÂN TÍCH PHÁP LÝ: điều luật áp dụng, hình phạt\n"
            "3. KẾT LUẬN VÀ KHUYẾN NGHỊ: hành động cần thiết\n"
            "4. NGUỒN THAM KHẢO: liệt kê nguồn\n\n"
            "Mọi thông tin phải có citation [Nguồn, Năm/Điều]."
        )),
        HumanMessage(content=(
            f"Câu hỏi: {state['question']}\n"
            f"Kế hoạch: {state.get('supervisor_plan', '')}\n\n"
            f"{combined}"
        )),
    ]

    result = await llm.ainvoke(messages)
    print(f"   ✅ [SYNTHESIZER] Hoàn thành ({len(result.content)} ký tự)")
    return {"final_answer": result.content}


# ---------------------------------------------------------------------------
# Graph Construction
# ---------------------------------------------------------------------------

def create_rag_supervisor_graph():
    """Xây dựng Supervisor-Workers graph cho RAG Pipeline."""
    graph = StateGraph(RAGState)

    # Nodes
    graph.add_node("supervisor", supervisor)
    graph.add_node("retrieval_worker", retrieval_worker)
    graph.add_node("legal_analysis_worker", legal_analysis_worker)
    graph.add_node("citation_worker", citation_worker)
    graph.add_node("synthesizer", synthesizer)

    # Edges
    graph.set_entry_point("supervisor")

    # Supervisor → dispatch retrieval + legal workers (song song)
    graph.add_conditional_edges(
        "supervisor",
        dispatch_workers,
        ["retrieval_worker", "legal_analysis_worker", "citation_worker"],
    )

    # Retrieval + Legal → Citation Worker (sau khi có dữ liệu)
    graph.add_edge("retrieval_worker", "citation_worker")
    graph.add_edge("legal_analysis_worker", "citation_worker")

    # Citation Worker → Synthesizer → END
    graph.add_edge("citation_worker", "synthesizer")
    graph.add_edge("synthesizer", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

QUESTIONS = [
    "Hình phạt cho tội tàng trữ trái phép chất ma tuý theo pháp luật Việt Nam?",
    "Nghệ sĩ sử dụng ma tuý bị xử lý như thế nào theo pháp luật Việt Nam?",
    "Quy trình cai nghiện bắt buộc theo Luật Phòng chống ma tuý 2021?",
]


async def main():
    print("=" * 70)
    print("🏛️  HỆ THỐNG RAG PHÁP LUẬT VỀ MA TÚY")
    print("    Cải tiến Day08 → Supervisor - Workers Pattern")
    print("=" * 70)
    print()
    print("📐 Kiến trúc:")
    print("   SUPERVISOR (điều phối)")
    print("   ├── Worker 1: Retrieval Worker    (semantic + lexical search)")
    print("   ├── Worker 2: Legal Analysis      (phân tích luật áp dụng)")
    print("   └── Worker 3: Citation Generator  (sinh câu trả lời có citation)")
    print("   └── SYNTHESIZER (tổng hợp báo cáo cuối cùng)")
    print()
    print("🔄 So sánh với Day08:")
    print("   Day08: Pipeline tuần tự → retrieve → generate (monolithic)")
    print("   Day09: Supervisor phân tích → Workers song song → Tổng hợp")
    print()

    graph = create_rag_supervisor_graph()

    for i, question in enumerate(QUESTIONS, 1):
        print(f"\n{'─' * 70}")
        print(f"📌 Câu hỏi {i}: {question}")
        print(f"{'─' * 70}")

        result = await graph.ainvoke({
            "question": question,
            "supervisor_plan": "",
            "workers_needed": [],
            "retrieval_result": "",
            "legal_analysis_result": "",
            "citation_result": "",
            "final_answer": "",
        })

        print(f"\n{'═' * 70}")
        print(f"📊 BÁO CÁO PHÁP LÝ - Câu hỏi {i}")
        print(f"{'═' * 70}")
        print(result["final_answer"])
        print(f"{'═' * 70}\n")


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
