# Lab Assignment: Cải tiến Agent Day08 → Supervisor-Workers Pattern

**Sinh viên:** 2A202600556 - Nguyễn Văn Minh

---

## Mục tiêu

Cải tiến hệ thống RAG Pipeline từ Day08 (pipeline tuần tự monolithic) sang kiến trúc **Supervisor - Workers** với ít nhất 3 workers chuyên biệt.

---

## Kiến trúc Supervisor - Workers

```
┌─────────────────────────────────────────────────────┐
│                   SUPERVISOR                         │
│  Phân tích câu hỏi → lập kế hoạch → giao việc      │
└───────────┬──────────────┬──────────────┬───────────┘
            │              │              │
┌───────────▼──┐ ┌────────▼────────┐ ┌──▼──────────────┐
│  RETRIEVAL   │ │ LEGAL ANALYSIS  │ │ CITATION        │
│  WORKER      │ │ WORKER          │ │ GENERATOR       │
│  (Worker 1)  │ │ (Worker 2)      │ │ (Worker 3)      │
│              │ │                 │ │                 │
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
```

---

## So sánh Day08 vs Day09

| Tiêu chí | Day08 (Monolithic) | Day09 (Supervisor-Workers) |
|---|---|---|
| Kiến trúc | Pipeline tuần tự | Supervisor điều phối + Workers song song |
| Retrieval | retrieve() → generate() | Worker 1 (semantic + lexical riêng biệt) |
| Phân tích | Không có | Worker 2 (Legal Analysis chuyên biệt) |
| Citation | Trong generate() | Worker 3 (Citation Generator riêng) |
| Mở rộng | Khó (thêm code vào pipeline) | Dễ (thêm worker mới) |
| Song song | Không | Retrieval + Legal Analysis chạy song song |

---

## Công nghệ sử dụng

- **LangGraph** StateGraph + Send API (parallel dispatch)
- **LangChain** create_react_agent (ReAct pattern cho mỗi worker)
- **OpenRouter** API cho LLM inference
- Knowledge base mô phỏng từ Day08 (pháp luật ma tuý Việt Nam)

---

## Cách chạy

```bash
# Từ thư mục gốc
uv run python Lab_Assignment/supervisor_workers.py
```

---

## Các Workers chi tiết

### Worker 1: Retrieval Worker
- Sử dụng 2 tools: `semantic_search` + `lexical_search`
- Tìm kiếm theo cả ngữ nghĩa và từ khóa
- Tổng hợp kết quả từ cả hai nguồn (hybrid search)

### Worker 2: Legal Analysis Worker
- Sử dụng tool: `analyze_law_article`
- Phân tích điều luật áp dụng cụ thể
- Xác định khung hình phạt
- Nhận diện tình tiết tăng nặng/giảm nhẹ

### Worker 3: Citation Generator Worker
- Nhận dữ liệu từ Worker 1 + Worker 2
- Tạo câu trả lời có citation [Nguồn, Năm/Điều]
- Đảm bảo mọi thông tin đều có trích dẫn
