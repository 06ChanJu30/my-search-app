# AI_README: System Architecture & Developer Guidelines

## 🤖 Introduction for AI Agents
You are an autonomous AI agent or LLM assisting with the maintenance, feature expansion, and API interaction of this repository. This document outlines the core architecture, data flow, caching rules, and strict constraints of the "Safety Manual OPS Search Engine" (Streamlit App). **Read this carefully before making any modifications to `app.py`.**

## 1. System Overview
*   **Purpose:** A hybrid search engine (Keyword + Semantic) for Samsung C&T's safety manuals.
*   **Framework:** Streamlit (Python).
*   **Core Libraries:**
    *   `pandas`: Data manipulation and keyword searching.
    *   `PyMuPDF (fitz)`: PDF rendering and text highlighting.
    *   `sentence-transformers`: Semantic text embedding (`snunlp/KR-SBERT-V40K-klueNLI-augSTS`).
    *   `faiss-cpu`: Vector similarity search.

## 2. File Structure & Data Sources
*   `app.py`: Main application script (UI, Search Logic, Admin Dashboard).
*   `ops_database.json`: Primary metadata and text database (Title, Category, Page numbers, Answer).
*   `안전보건 작업지침 OPS.pdf`: The source of truth for rendering visual manuals.
*   `vector_db.index`: FAISS index file for semantic search.
*   `search_logs.csv`: Local log file for tracking search queries (Note: subject to volatility on Streamlit Cloud).

## 3. Core Mechanisms & Caching Rules (CRITICAL)
To maintain performance and prevent server crashes in a multi-user environment, strict caching rules are applied. **Do not modify these patterns unless explicitly instructed.**

### A. Data Caching (`@st.cache_data`)
*   Used for serializable data that can be safely copied.
*   **`load_ops_data()`:** Loads the JSON database into a Pandas DataFrame.
*   **`convert_df_to_csv_for_vba()`:** Caches the output of DataFrame-to-CSV conversion to prevent redundant CPU cycles during re-renders.

### B. Resource Caching (`@st.cache_resource`)
*   Used for global, non-serializable objects (Models, DB connections, Bytes).
*   **`load_ai_models()`:** Loads the SBERT model and FAISS index globally.
*   **`load_pdf_bytes()`:** Loads the PDF file into memory as **raw bytes**, NOT as a `fitz.Document` object.

### C. PDF Rendering & Thread Safety (Anti-Race Condition)
*   **Rule:** Never instantiate `fitz.open(PDF_FILE_PATH)` globally or cache the `fitz.Document` object. Streamlit is multi-threaded, and concurrent annotation (highlighting) on a single global PDF object will cause a core dump/crash.
*   **Pattern:** In `display_manual_content()`, the PDF is opened locally using the cached bytes: `local_pdf = fitz.open("pdf", pdf_bytes)`.
*   **Cleanup:** The local PDF instance MUST be closed in a `finally:` block (`local_pdf.close()`) to prevent memory leaks.

## 4. Search Workflow
1.  **Exact Keyword Match (Step 1):** Uses Pandas boolean masking (`str.contains`) on `title` and `search_normalized`.
2.  **Semantic Search (Step 2 - Fallback/Recommend):** If keyword matches are <= 3, the query is vectorized and searched against `faiss_index`.
3.  **API / Headless Mode (V4.0+):** The app supports URL parameter queries (`?query=...&format=json`). When `format=json` is detected, UI rendering is bypassed, and raw JSON is returned using `st.json()` or `st.write()` and execution is halted via `st.stop()`.

## 5. Strict Constraints for Code Modification
*   **Do not use `st.rerun()` for simple UI toggles.** It causes poor UX (screen flashing).
*   **Preserve `CATEGORY_KEYWORDS` dictionary.** Do not revert to hardcoded `if-elif` blocks for category assignment.
*   **VBA Compatibility:** When modifying the CSV export logic, ensure `Report_Date`, `Target_Cell_Width`, and `Target_Cell_Height` columns remain intact for external Excel VBA macros.
*   **Mobile-First UI:** Maintain `st.columns(..., vertical_alignment="center")` and collapsed sidebars for field workers using tablets/phones.

## 6. Known Environment Limitations
*   **Ephemeral Storage:** This app runs on Streamlit Cloud. Files written locally (like `search_logs.csv` or updated `ops_database.json`) will be wiped upon server reboot. Any future patches handling data persistence must target external APIs (e.g., Google Sheets API, GitHub API).