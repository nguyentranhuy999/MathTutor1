# Tài liệu module `src/formalizer`

## 1) Mục tiêu của cụm module này

`src/formalizer` chịu trách nhiệm biến dữ liệu chữ tự do thành cấu trúc chuẩn để hệ thống có thể:

- hiểu đề bài toán dưới dạng dữ liệu có kiểu (`FormalizedProblem`),
- dựng đồ thị đề bài (`problem_graph`, `problem_summary_graph`),
- chuẩn hóa bài làm học sinh (`StudentWorkState`) và dựng `student_graph`,
- xuất đồ thị sang Cypher để xem trong Neo4j,
- hỗ trợ đường đi có LLM (nếu có) và fallback heuristic (nếu không có hoặc lỗi).

Lưu ý: tên thư mục đúng là `src/formalizer` (không phải `src/formalize`).

## 2) Luồng chạy chính

### 2.1 Luồng formalize đề bài

1. `formalize_problem(...)` trong `problem_formalizer.py` nhận `problem_text`.
2. Chạy heuristic qua `_heuristic_formalize_problem(...)` trong `problem_formalizer_builder.py`:
   - trích `quantities`, `entities`, `target`, `relation_candidates`, `semantic_triples`.
   - validate + repair nhẹ.
   - dựng `problem_summary_graph` và `problem_graph`.
3. Nếu có `llm_client`: gọi `_llm_formalize_problem(...)` trong `problem_formalizer_llm.py` để tinh chỉnh theo skeleton JSON.
4. Nếu LLM lỗi: fallback về heuristic và thêm note `llm_formalization_failed_fallback`.

### 2.1.1 I/O theo từng file trong pipeline formalize đề bài

| File | Hàm chính trong pipeline | Input trực tiếp | Output trực tiếp | Ghi chú |
|---|---|---|---|---|
| `problem_formalizer.py` | `formalize_problem(problem_text, llm_client=None)` | `problem_text: str`, `llm_client: LLMClient \\| None` | `FormalizedProblem` | Entry point, quyết định đi nhánh heuristic hay LLM. |
| `problem_formalizer_builder.py` | `_heuristic_formalize_problem(problem_text)` | `problem_text: str` | `FormalizedProblem` đã có `problem_summary_graph`, `problem_graph` | Builder lõi cho nhánh heuristic. |
| `problem_formalizer_extractors.py` | Các hàm `_extract_*`, `_build_*` | `problem_text`, và dữ liệu trung gian (`target`, `entities`, `quantities`) | `quantities`, `entities`, `target`, `relation_candidates`, `semantic_triples` | Tầng trích thông tin từ text. |
| `problem_formalizer_validation.py` | `validate_formalized_problem(problem)` | `FormalizedProblem` thô | `FormalizedProblem` đã chuẩn hóa/repair nhẹ | Chuẩn hóa dữ liệu + thêm `notes`, `confidence`. |
| `problem_graph.py` | `build_problem_summary_graph(problem)`, `build_problem_graph(problem)` | `FormalizedProblem` | `ProblemGraph` (summary), `ProblemGraph` (executable) | Dựng đồ thị từ dữ liệu structured. |
| `problem_formalizer_llm.py` | `_llm_formalize_problem(problem_text, heuristic_problem, llm_client)` | `problem_text`, `heuristic_problem`, `llm_client` | `FormalizedProblem` refined hoặc fallback | Vòng lặp prompt/retry + validate. |
| `neo4j_visualizer.py` | `export_problem_graph_to_neo4j_cypher(graph, ...)` | `ProblemGraph` | `str` Cypher script | Bước export để quan sát đồ thị trong Neo4j. |

### 2.1.2 Dữ liệu đi qua từng bước (chi tiết object)

1. **Input thô**
   - `problem_text: str`

2. **Sau extractor (`problem_formalizer_extractors.py`)**
   - `quantities: list[QuantityAnnotation]`
   - `entities: list[ProblemEntity]`
   - `target: TargetSpec | None`
   - `relation_candidates: list[RelationCandidate]`
   - `semantic_triples: list[SemanticTriple]`

3. **Sau validation (`problem_formalizer_validation.py`)**
   - Vẫn là `FormalizedProblem`, nhưng:
   - id sạch hơn, dữ liệu thiếu được bù tối thiểu (fallback),
   - `confidence` và `notes` được cập nhật theo quality hiện tại.

4. **Sau graph build (`problem_graph.py`)**
   - `problem_summary_graph: ProblemGraph`
   - `problem_graph: ProblemGraph`
   - `target_node_id` được gắn để xác định node đích.

5. **Nếu có LLM (`problem_formalizer_llm.py`)**
   - Input cho LLM là `compact draft` (JSON rút gọn từ heuristic result).
   - LLM trả payload skeleton (`quantity_updates`, `target_update`, `relation_updates`, `graph_steps`, ...).
   - Builder ghép payload vào lại `FormalizedProblem` typed.

6. **Khi export (`neo4j_visualizer.py`)**
   - Input: `ProblemGraph`
   - Output: file `.cypher` có node/edge/property để chạy trực tiếp trên Neo4j.

### 2.2 Luồng formalize bài làm học sinh

1. `formalize_student_work(...)` trong `student_work.py` nhận `raw_answer` (và có thể nhận `problem`, `reference`).
2. Chạy heuristic qua `_heuristic_formalize_student_work(...)` trong `student_work_builder.py`:
   - trích đáp án cuối,
   - tách bước,
   - suy ra mode (`final_answer_only`, `partial_trace`, ...),
   - dựng `student_graph`.
3. Nếu có `llm_client`: gọi `_llm_formalize_student_work(...)` trong `student_work_llm.py` để refine.
4. Nếu LLM lỗi: fallback heuristic và thêm note `llm_student_parse_failed_fallback`.

## 3) Chi tiết từng file

## `src/formalizer/__init__.py`

- Vai trò: cổng export public API của package `formalizer`.
- Input/Output: không xử lý dữ liệu; chỉ re-export hàm.
- Public symbols chính:
  - `formalize_problem`, `formalize_student_work`
  - `build_problem_graph`, `build_problem_summary_graph`, `build_student_work_graph`
  - `build_reference_trace`, `build_student_partial_trace`
  - `export_problem_graph_to_neo4j_cypher`
- Dùng khi: các script/debug/test import từ `src.formalizer` thay vì import file lẻ.

## `src/formalizer/problem_formalizer.py`

- Vai trò: entrypoint formalize đề bài.
- Hàm chính: `formalize_problem(problem_text, llm_client=None) -> FormalizedProblem`.
- Input:
  - `problem_text`: đề bài text.
  - `llm_client`: tùy chọn.
- Output:
  - `FormalizedProblem` đã có dữ liệu structured và graph.
- Logic:
  - luôn chạy heuristic trước,
  - nếu có LLM thì refine,
  - nếu LLM lỗi thì giữ heuristic result.

## `src/formalizer/problem_formalizer_builder.py`

- Vai trò: builder lõi cho đề bài (heuristic draft + rebuild từ skeleton LLM).
- Nhóm hàm chính:
  - `_heuristic_formalize_problem(...)`: pipeline heuristic đầy đủ.
  - `_build_compact_draft(...)`: thu gọn object để làm prompt LLM.
  - `_build_formalized_problem_from_skeleton(...)`: ghép payload LLM vào object typed.
  - `_build_problem_graph_from_skeleton(...)`: dựng `ProblemGraph` từ danh sách `graph_steps`.
  - `_attach_problem_graphs(...)`: gắn `problem_summary_graph` + `problem_graph`.
- Input heuristic:
  - `problem_text`.
- Output heuristic:
  - `FormalizedProblem` gồm `quantities`, `entities`, `target`, `relation_candidates`, `semantic_triples`, `problem_summary_graph`, `problem_graph`.
- Điểm mới trong bản lai 4 tầng:
  - thêm `semantic_triples` vào output heuristic,
  - thêm note theo tầng:
    - `hybrid_layer1_structured_extraction_done`
    - `hybrid_layer2_semantic_triples_done`
    - `hybrid_layer3_llm_refinement_skipped` (khi chưa dùng LLM)
    - `hybrid_layer4_graph_projection_done`

## `src/formalizer/problem_formalizer_extractors.py`

- Vai trò: tất cả hàm trích thông tin low-level từ đề bài text.
- Nhóm chức năng:
  - trích target: `_extract_target_text`, `_build_target_spec`, `_attach_target_quantity`.
  - trích thực thể và số: `_extract_entities`, `_extract_quantities`, `_infer_unit`, `_infer_semantic_role`, `_link_quantities_to_entities`.
  - suy luận quan hệ bài toán: `_infer_relation_and_operation`, `_build_relation_candidates`, `_candidate_expression`.
  - chuẩn hóa/khử trùng lặp: `_dedupe_quantities`.
  - trích bộ ba ngữ nghĩa (semantic triple):
    - `_find_triple_relation_cue`, `_clean_triple_subject`, `_clean_triple_object`, `_extract_period_hint`, `_triple_edge_type`, `_extract_semantic_triples`.
- Input chính:
  - `problem_text`, `target`, `entities`, `quantities`.
- Output chính:
  - danh sách `QuantityAnnotation`, `ProblemEntity`, `RelationCandidate`, `SemanticTriple`.
- Ghi chú:
  - đây là tầng “trích cấu trúc + triple” quan trọng nhất trước khi dựng graph.

## `src/formalizer/problem_formalizer_validation.py`

- Vai trò: validate + repair nhẹ cho `FormalizedProblem`, và tạo feedback cho vòng lặp LLM.
- Hàm chính:
  - `validate_formalized_problem(...)`: chuẩn hóa entity/quantity/relation/target và confidence.
  - `_apply_local_semantic_repairs(...)`: sửa bất nhất semantic cục bộ.
  - `_semantic_sanity_validation_result(...)`: kiểm tra sanity theo ngữ nghĩa.
- Hàm hỗ trợ LLM loop:
  - `_schema_validation_result(...)`, `_missing_graph_validation_result(...)`, `_graph_feedback_payload(...)`.
- Input:
  - `FormalizedProblem` trước/ sau refine.
- Output:
  - `FormalizedProblem` sạch hơn + `GraphValidationResult` khi cần.

## `src/formalizer/problem_formalizer_llm.py`

- Vai trò: vòng lặp prompt/retry để refine `FormalizedProblem` bằng LLM theo skeleton JSON.
- Hàm chính:
  - `_build_llm_graph_prompt(...)`: tạo system/user prompt có constraint enum/id.
  - `_llm_formalize_problem(...)`: chạy tối đa 3 lần, validate mỗi lần, fallback nếu không đạt.
- Input:
  - `problem_text`, `heuristic_problem`, `llm_client`.
- Output:
  - `FormalizedProblem` refined hoặc heuristic fallback.
- Chính sách:
  - strict schema,
  - validate graph bằng `runtime.graph_validator.validate_problem_graph(...)`,
  - feedback issue quay lại prompt ở lần sau.

## `src/formalizer/problem_graph.py`

- Vai trò: dựng graph từ dữ liệu structured đề bài.
- Hai output chính:
  - `build_problem_summary_graph(problem)`: graph tóm tắt ngữ nghĩa, không có operation node.
  - `build_problem_graph(problem)`: graph thực thi (có operation step để solve).
- Nhóm logic trong file:
  - base graph: node/edge entity, quantity, target.
  - rule-based subgraph cho dạng bài:
    - rate/discount,
    - additive/subtractive/multiplicative/partition,
    - progression (tỉ lệ kiểu double/half qua các mốc),
    - fallback theo expression relation.
  - summary semantic extraction fallback từ text.
  - ưu tiên dựng summary graph từ `problem.semantic_triples` nếu có.
- Input:
  - `FormalizedProblem`.
- Output:
  - `ProblemGraph`.
- Ghi chú:
  - file này là nơi biến “dữ liệu trích” thành “đồ thị có ý nghĩa” để debug/so sánh/chấm.

## `src/formalizer/neo4j_visualizer.py`

- Vai trò: convert `ProblemGraph` thành script Cypher deterministic.
- Hàm chính: `export_problem_graph_to_neo4j_cypher(graph, graph_scope, clear_scope)`.
- Input:
  - `ProblemGraph`.
- Output:
  - chuỗi `.cypher` có:
    - tạo constraint,
    - `MERGE` node,
    - `MERGE` edge,
    - gắn metadata target/graph.
- Dùng ở:
  - các script debug export graph ra `debug/artifacts/*.cypher`.

## `src/formalizer/reference_trace.py`

- Vai trò: parse lời giải text thành trace chuẩn (`SymbolicTrace`) cho cả reference và student partial.
- Hàm chính:
  - `strip_reference_markers(...)`
  - `parse_trace_step(...)`
  - `build_reference_trace(...)`
  - `build_student_partial_trace(...)`
- Input:
  - text lời giải.
- Output:
  - `SymbolicTrace` với danh sách `TraceStep`, final value, confidence, notes.
- Ý nghĩa:
  - là cầu nối giữa text phép tính và các module runtime/graph student.

## `src/formalizer/student_work.py`

- Vai trò: entrypoint formalize bài làm học sinh.
- Hàm chính: `formalize_student_work(raw_answer, problem=None, reference=None, llm_client=None)`.
- Input:
  - bài làm raw,
  - tùy chọn context đề bài/reference.
- Output:
  - `StudentWorkState` (có thể kèm `student_graph`).
- Cơ chế:
  - heuristic trước, LLM sau, fallback nếu lỗi.

## `src/formalizer/student_work_builder.py`

- Vai trò: builder lõi cho student work (heuristic parse + rebuild từ skeleton).
- Nhóm hàm chính:
  - `_extract_final_answer`, `_split_student_steps`, `_build_step_attempts`.
  - `_infer_mode`, `_infer_selected_target_ref`.
  - `_heuristic_formalize_student_work`.
  - `_build_compact_student_draft`.
  - `_build_student_work_from_skeleton`.
- Input:
  - `raw_answer`, optional `problem`, optional skeleton từ LLM.
- Output:
  - `StudentWorkState` typed + `student_graph` (nếu parse được).
- Chú ý:
  - chỉ cho phép `referenced_ids` thuộc tập `allowed_refs` từ problem target/quantities.

## `src/formalizer/student_work_llm.py`

- Vai trò: vòng lặp prompt/retry để refine student parse bằng LLM.
- Hàm chính:
  - `_build_llm_student_prompt(...)`
  - `_llm_formalize_student_work(...)`
- Input:
  - `raw_answer`, `heuristic_state`, optional `problem/reference`, `llm_client`.
- Output:
  - `StudentWorkState` refined hoặc heuristic fallback.
- Đặc điểm:
  - strict không được invent bước mới,
  - giữ nguyên văn học sinh, chỉ cập nhật fields structured.

## `src/formalizer/student_work_graph.py`

- Vai trò: dựng graph từ `StudentWorkState` để so sánh với `problem_graph/reference_graph`.
- Hàm chính: `build_student_work_graph(student_work, problem=None)`.
- Input:
  - `StudentWorkState`, optional `FormalizedProblem`.
- Output:
  - `ProblemGraph | None` (None nếu không parse được gì).
- Logic:
  - tạo operation node từ từng step,
  - nối input refs,
  - tạo intermediate output nodes nếu step có `extracted_value`,
  - nối target cuối (`student_final_answer`).

## `src/formalizer/student_work_validation.py`

- Vai trò: kiểm tra sanity cho kết quả student formalization.
- Hàm chính:
  - `_student_sanity_validation_result(...)`
  - `_student_feedback_payload(...)`
- Input:
  - `StudentWorkState`, optional `problem/reference`.
- Output:
  - `GraphValidationResult` và payload issue cho vòng lặp LLM.
- Kiểm tra nổi bật:
  - `selected_target_ref` hợp lệ,
  - `referenced_ids` chỉ dùng id hợp lệ,
  - mode và data nhất quán,
  - `student_graph` có target khi cần.

## 4) Bức tranh phụ thuộc giữa các file

- Entrypoint đề bài:
  - `problem_formalizer.py`
  - gọi `problem_formalizer_builder.py`
  - builder gọi `problem_formalizer_extractors.py`, `problem_formalizer_validation.py`, `problem_graph.py`
  - nếu LLM: đi qua `problem_formalizer_llm.py`

- Entrypoint bài làm học sinh:
  - `student_work.py`
  - gọi `student_work_builder.py`
  - builder gọi `reference_trace.py`, `student_work_graph.py`
  - nếu LLM: đi qua `student_work_llm.py`
  - validation nằm ở `student_work_validation.py`

- Export đồ thị:
  - `neo4j_visualizer.py` nhận `ProblemGraph` bất kỳ và xuất `.cypher`.

## 5) Mapping input/output toàn module

- Input text:
  - đề bài: `problem_text`
  - bài làm: `raw_answer`

- Output structured cấp đề bài:
  - `FormalizedProblem`
  - chứa `quantities`, `entities`, `target`, `relation_candidates`, `semantic_triples`
  - chứa `problem_summary_graph`, `problem_graph`

- Output structured cấp học sinh:
  - `StudentWorkState`
  - chứa `steps`, `normalized_final_answer`, `selected_target_ref`, `student_graph`

- Output visualization:
  - chuỗi Cypher từ `export_problem_graph_to_neo4j_cypher(...)`

## 6) Gợi ý đọc code theo thứ tự

1. `problem_formalizer.py`
2. `problem_formalizer_builder.py`
3. `problem_formalizer_extractors.py`
4. `problem_graph.py`
5. `problem_formalizer_validation.py`
6. `problem_formalizer_llm.py`
7. `student_work.py`
8. `student_work_builder.py`
9. `student_work_graph.py`
10. `student_work_validation.py`
11. `student_work_llm.py`
12. `neo4j_visualizer.py`
