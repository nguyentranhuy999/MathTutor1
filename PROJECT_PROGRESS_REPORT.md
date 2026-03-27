# Báo Cáo Tiến Độ Dự Án Nghiên Cứu

## 1. Thông Tin Chung

- **Tên hướng nghiên cứu**: Neuro-symbolic tutoring pipeline for math word problems
- **Mục tiêu tổng quát**: xây dựng một hệ thống tutoring có khả năng:
  - hiểu đề toán có lời văn,
  - sinh biểu diễn cấu trúc có thể thực thi,
  - phân tích bài làm của học sinh,
  - đối chiếu process của học sinh với lời giải chuẩn,
  - chẩn đoán lỗi,
  - sinh gợi ý sư phạm an toàn, không lộ đáp án.
- **Định hướng dài hạn**:
  - không chỉ dừng ở rule-based tutoring,
  - mà hướng tới một kiến trúc có khả năng học tốt hơn từ dữ liệu, verifier và phản hồi,
  - thậm chí có thể bổ sung **reinforcement learning (RL)** ở giai đoạn sau nếu đủ thời gian.

---

## 2. Đặt Vấn Đề

### 2.1. Bài toán thực tế

Trong các hệ thống tutoring toán, nếu chỉ để LLM trả lời trực tiếp bằng chuỗi suy luận tự do thì có một số vấn đề:

- khó kiểm chứng xem model có thật sự hiểu đúng đề không,
- khó xác định chính xác học sinh sai ở bước nào,
- khó sinh gợi ý sư phạm an toàn,
- dễ sinh lời giải “có vẻ hợp lý” nhưng không trung thực với process của học sinh,
- khó giải thích và khó mở rộng sang nghiên cứu định lượng.

### 2.2. Bài toán nghiên cứu

Từ đó, dự án đặt ra bài toán nghiên cứu:

> Có thể xây dựng một pipeline tutoring cho toán có lời văn theo hướng **neuro-symbolic**, trong đó:
> - LLM chỉ đảm nhiệm các phần ngữ nghĩa khó,
> - phần symbolic/runtime giữ vai trò nguồn sự thật thực thi,
> - process của học sinh được formalize thành graph,
> - và diagnosis/hint được xây dựng trên evidence có cấu trúc thay vì chỉ dựa vào đáp án cuối?

Đây không phải là bài toán “gọi LLM để trả lời”, mà là bài toán:

- **formal reasoning representation**
- **process alignment**
- **error localization**
- **pedagogical hint generation**

---

## 3. Vì Sao Đây Là Một Dự Án Nghiên Cứu

### 3.1. Không chỉ là một ứng dụng kỹ thuật

Dự án có tính nghiên cứu vì nó không đơn thuần xây một app sử dụng API, mà đang giải quyết một số câu hỏi mở:

- biểu diễn trung gian nào phù hợp nhất cho math tutoring: text, plan, program hay graph?
- nên chia vai trò giữa LLM và symbolic runtime như thế nào?
- làm thế nào để formalize bài làm học sinh mà không “nhìn đáp án chuẩn” quá sớm?
- làm thế nào để so sánh hai process giải khác nhau nhưng tương đương về ngữ nghĩa?
- làm thế nào để tách `evidence`, `diagnosis`, `pedagogy`, `hint` thành các tầng có thể đánh giá độc lập?

### 3.2. Các yếu tố cho thấy đây là bài toán nghiên cứu

Các dấu hiệu quan trọng:

1. **Có bài toán khoa học rõ ràng**
- tutoring trên toán có lời văn không chỉ là generation, mà là structured reasoning + diagnosis + pedagogy.

2. **Có giả thuyết nghiên cứu**
- structured formalization + executable graph + process-aware evidence sẽ tốt hơn pipeline chỉ dựa vào final answer hoặc free-form CoT.

3. **Có kiến trúc mới cần kiểm chứng**
- tách hệ thành nhiều module:
  - formalizer
  - runtime
  - student work
  - evidence
  - diagnosis
  - pedagogy
  - hint

4. **Có thể làm ablation**
- bỏ graph thì sao?
- chỉ dùng final answer thì sao?
- alignment theo index so với global alignment khác nhau thế nào?
- heuristic-only so với LLM-assisted khác nhau thế nào?

5. **Có thể xây benchmark và protocol đánh giá**
- accuracy của formalizer
- graph executability
- target inference accuracy
- first-divergence localization
- diagnosis label accuracy
- hint safety / anti-spoiler / pedagogical utility

6. **Có thể so với baseline**
- direct CoT baseline
- heuristic-only baseline
- no-graph baseline
- no-evidence baseline

7. **Có không gian để mở rộng thành learning system**
- verifier-guided refinement
- ranking candidates
- RL for pedagogy/hint policy

Tức là đây có đầy đủ các thành phần nền tảng của một đề tài nghiên cứu:

- problem formulation
- architectural novelty
- hypotheses
- measurable evaluation
- ablation potential
- benchmark potential
- future learning extensions

---

## 4. Câu Hỏi / Giả Thuyết Nghiên Cứu Cốt Lõi

Một số giả thuyết trung tâm của dự án:

### H1. Formalization có cấu trúc tốt hơn free-form reasoning

Nếu đề bài được formalize thành **typed graph / executable plan**, hệ sẽ:

- kiểm chứng được,
- dễ debug hơn,
- ít phụ thuộc vào lời văn LLM hơn.

### H2. Process-aware evidence tốt hơn final-answer-only evidence

Nếu bài làm học sinh được chuyển thành graph/trace rồi so với canonical reference ở mức process, hệ sẽ:

- xác định tốt hơn lỗi mục tiêu,
- phân biệt tốt hơn sai phép tính và sai quan hệ lượng,
- giảm false positive trong các lời giải đúng nhưng khác thứ tự.

### H3. Tách `evidence -> diagnosis -> pedagogy -> hint` tốt hơn pipeline generation trực tiếp

Nếu diagnosis và hint không sinh trực tiếp từ raw text mà đi qua evidence có cấu trúc, hệ sẽ:

- có tính giải thích cao hơn,
- ít lộ đáp án hơn,
- dễ benchmark hơn.

### H4. Kết hợp LLM + symbolic/runtime tốt hơn chỉ dùng một trong hai

- Chỉ heuristic: cứng nhắc, dễ gãy khi bài đa dạng.
- Chỉ LLM: khó kiểm chứng, dễ hallucinate.
- Kết hợp: vừa linh hoạt vừa kiểm chứng được.

---

## 5. Các Nghiên Cứu / Paper Đã Tham Khảo

### 5.1. Nhóm về biểu diễn trung gian / program / graph cho MWP

1. **MathQA: Towards Interpretable Math Word Problem Solving with Operation-Based Formalisms**
- Ý chính: bài toán nên có biểu diễn trung gian kiểu program / operation-based formalism.
- Áp dụng:
  - dự án dùng `FormalizedProblem`
  - dùng `ProblemGraph`
  - dùng `ExecutablePlan`

2. **Graph-to-Tree Learning for Solving Math Word Problems**
- Ý chính: representation quan hệ giữa quantities rất quan trọng.
- Áp dụng:
  - project dùng graph thay vì chỉ relation flat.

3. **A Goal-Driven Tree-Structured Neural Model for Math Word Problems**
- Ý chính: target/goal nên là trung tâm của decomposition.
- Áp dụng:
  - `target_variable`
  - `problem_graph.target_node_id`
  - `student_graph.target_node_id`

### 5.2. Nhóm về LLM sinh program, runtime thực thi

4. **PAL: Program-Aided Language Models**
- Ý chính: model sinh program, interpreter mới tính toán.
- Áp dụng:
  - formalizer sinh structure,
  - runtime compile + execute.

5. **Program of Thoughts Prompting**
- Ý chính: tách reasoning và computation.
- Áp dụng:
  - LLM không phải nguồn final truth,
  - executor mới là nơi ra reference final answer.

6. **Logic-LM**
- Ý chính:
  - formalize,
  - kiểm bằng solver,
  - feedback quay lại refine.
- Áp dụng:
  - `problem_formalizer` có retry/refine loop,
  - graph validation feedback được đưa vào attempt sau,
  - heuristic là fallback cuối.

### 5.3. Nhóm về verifier / process verification

7. **Training Verifiers to Solve Math Word Problems**
- Ý chính: cần verifier/ranker chứ không chỉ một lời giải.
- Áp dụng:
  - `evidence builder` được thiết kế như một process verifier nhẹ.

8. **Let’s Verify Step by Step**
- Ý chính: đánh giá ở mức step/process tốt hơn chỉ nhìn final answer.
- Áp dụng:
  - student work và evidence không còn chỉ dựa trên final answer.

9. **ProcessBench**
- Ý chính: phải tìm được bước lệch đầu tiên.
- Áp dụng:
  - `first_divergence_step_id`
  - alignment map
  - dependency-aware comparison

10. **AutoPSV**
- Ý chính: tự động hóa process supervision / verification.
- Áp dụng:
  - evidence builder hướng tới graph-aware alignment và divergence detection.

11. **LLMs cannot spot math errors, even when allowed to peek into the solution**
- Ý chính: phát hiện lỗi toán học là bài toán khó, không thể chỉ dựa vào generation.
- Áp dụng:
  - tách parser, evidence, diagnosis thành các tầng riêng,
  - giảm việc để model tự “kết luận hộ”.

### 5.4. Nhóm về tutoring / hint / pedagogy

12. **MathDial**
- Ý chính: tutoring math cần teacher moves rõ ràng.
- Áp dụng:
  - planner map diagnosis -> teacher move -> hint plan.

13. **TMATH**
- Ý chính: hint generation là bài toán riêng, không đồng nhất với giải toán.
- Áp dụng:
  - `hint_generator` và `hint_verifier` tách riêng,
  - anti-spoiler kiểm ở lớp verifier.

14. **Error Classification of LLMs on Math Word Problems**
- Ý chính: taxonomy lỗi nên tách label ổn định với subtype động.
- Áp dụng:
  - `diagnosis_label`
  - `subtype`
  - `localization`

---

## 6. Kiến Trúc Tổng Thể Của Hệ Thống

Pipeline hiện tại:

`Problem Text -> Problem Formalizer -> Canonical Reference -> Student Work Formalizer -> Evidence Builder -> Diagnosis -> Pedagogy Planner -> Hint Generator -> Hint Verifier`

### Các module chính trong repo

- [formalizer](c:/Users/linhn/Desktop/Dự%20án/src/formalizer)
- [runtime](c:/Users/linhn/Desktop/Dự%20án/src/runtime)
- [evidence](c:/Users/linhn/Desktop/Dự%20án/src/evidence)
- [diagnosis](c:/Users/linhn/Desktop/Dự%20án/src/diagnosis)
- [pedagogy](c:/Users/linhn/Desktop/Dự%20án/src/pedagogy)
- [hint](c:/Users/linhn/Desktop/Dự%20án/src/hint)
- [pipeline](c:/Users/linhn/Desktop/Dự%20án/src/pipeline)
- [models](c:/Users/linhn/Desktop/Dự%20án/src/models)

---

## 7. Tiến Độ Chi Tiết Theo Module

## 7.1. Problem Formalizer

### Vai trò

Biến `problem_text` thành một artifact có cấu trúc:

- quantities
- entities
- target
- relation candidates
- `problem_graph`

### Đã làm được

1. **Tách module sạch**
- [problem_formalizer.py](c:/Users/linhn/Desktop/Dự%20án/src/formalizer/problem_formalizer.py)
- [problem_formalizer_extractors.py](c:/Users/linhn/Desktop/Dự%20án/src/formalizer/problem_formalizer_extractors.py)
- [problem_formalizer_builder.py](c:/Users/linhn/Desktop/Dự%20án/src/formalizer/problem_formalizer_builder.py)
- [problem_formalizer_validation.py](c:/Users/linhn/Desktop/Dự%20án/src/formalizer/problem_formalizer_validation.py)
- [problem_formalizer_llm.py](c:/Users/linhn/Desktop/Dự%20án/src/formalizer/problem_formalizer_llm.py)
- [problem_graph.py](c:/Users/linhn/Desktop/Dự%20án/src/formalizer/problem_graph.py)

2. **Đưa formalizer sang LLM-first nhưng có kiểm soát**
- heuristic draft trước,
- LLM không trả full object dài nữa,
- mà trả `compact skeleton`,
- local code build lại full `FormalizedProblem`.

3. **Có `problem_graph` typed**
- graph gồm:
  - entity nodes
  - quantity nodes
  - operation nodes
  - intermediate nodes
  - target node

4. **Có validation + retry/refine loop**
- graph validator
- semantic sanity checks
- feedback issues được đưa lại cho model ở attempt sau
- heuristic fallback nếu loop fail

5. **Có debug riêng**
- [debug_formalizer.py](c:/Users/linhn/Desktop/Dự%20án/debug_formalizer.py)

### Ý nghĩa nghiên cứu

Formalizer hiện đã vượt khỏi mức “regex parser + LLM sửa nhẹ” và trở thành một bước semantic formalization có graph và executable grounding.

---

## 7.2. Canonical Reference / Runtime

### Vai trò

Biến `FormalizedProblem` thành lời giải chuẩn thực thi được.

### Đã làm được

1. **Graph validation**
- [graph_validator.py](c:/Users/linhn/Desktop/Dự%20án/src/runtime/graph_validator.py)

2. **Compile graph thành plan**
- [compiler.py](c:/Users/linhn/Desktop/Dự%20án/src/runtime/compiler.py)

3. **Execute plan**
- [executor.py](c:/Users/linhn/Desktop/Dự%20án/src/runtime/executor.py)

4. **Build canonical reference**
- [solver.py](c:/Users/linhn/Desktop/Dự%20án/src/runtime/solver.py)

### Ý nghĩa nghiên cứu

Đây là chỗ thể hiện rõ tinh thần `PAL` / `Logic-LM`:
- model không chốt final answer,
- executor mới là nguồn truth.

---

## 7.3. Student Work Formalizer

### Vai trò

Biến bài làm học sinh thành artifact có cấu trúc để so sánh ở downstream.

### Đã làm được

1. **Tách module sạch**
- [student_work.py](c:/Users/linhn/Desktop/Dự%20án/src/formalizer/student_work.py)
- [student_work_builder.py](c:/Users/linhn/Desktop/Dự%20án/src/formalizer/student_work_builder.py)
- [student_work_llm.py](c:/Users/linhn/Desktop/Dự%20án/src/formalizer/student_work_llm.py)
- [student_work_validation.py](c:/Users/linhn/Desktop/Dự%20án/src/formalizer/student_work_validation.py)
- [student_work_graph.py](c:/Users/linhn/Desktop/Dự%20án/src/formalizer/student_work_graph.py)

2. **Chuyển sang compact-skeleton-first**
- heuristic draft
- LLM trả compact skeleton
- local build `StudentWorkState`
- sanity validation
- retry/refine
- fallback heuristic

3. **Build `student_graph`**
- graph học sinh giữ:
  - operation nodes
  - intermediate outputs
  - target node
  - dependency edges giữa các bước học sinh

4. **Tách bạch khỏi reference**
- bước formalization của student work hiện tại không còn “so với lời giải chuẩn” sớm,
- chỉ grounded vào:
  - `student_answer`
  - `problem`

5. **Có debug riêng**
- [debug_student_work.py](c:/Users/linhn/Desktop/Dự%20án/debug_student_work.py)

### Ý nghĩa nghiên cứu

Đây là một điểm mới quan trọng:
- student work không chỉ là text parser,
- mà là process formalizer cho lời giải học sinh.

---

## 7.4. Evidence Builder

### Vai trò

Là tầng trung gian giữa:
- `student_work`
- và `diagnosis`

Nó không chẩn đoán trực tiếp, mà:
- align
- compare
- emit evidence có cấu trúc

### Đã làm được

1. **Refactor từ flat comparison sang process-aware comparison**
- [builder.py](c:/Users/linhn/Desktop/Dự%20án/src/evidence/builder.py)
- [alignment.py](c:/Users/linhn/Desktop/Dự%20án/src/evidence/alignment.py)

2. **Global alignment thật sự**
- không còn chỉ greedy local,
- đã có one-to-one global matching giữa:
  - student steps
  - canonical steps

3. **Dependency-aware comparison**
- builder xét:
  - output value
  - operation
  - input ref overlap
  - dependency subgraph

4. **Edge-level divergence**
- phát hiện lệch ở mức dependency edge,
- không chỉ step index/value.

5. **Graph edit summary**
- builder tính:
  - node substitutions
  - node insertions
  - node deletions
  - edge substitutions
  - edge insertions
  - edge deletions
  - total cost

6. **Xử lý case reorder**
- lời giải đúng nhưng khác thứ tự bước không còn bị phạt oan theo index,
- emit `reordered_but_consistent_steps`

7. **Artifact mới**
- `alignment_map`
- `first_divergence_step_id`
- `likely_error_mechanisms`

### Ý nghĩa nghiên cứu

Đây là phần thể hiện mạnh nhất hướng `process verification`.

---

## 7.5. Diagnosis

### Vai trò

Map structured evidence sang:
- label lỗi
- subtype
- localization
- summary

### Trạng thái

Đã có:
- deterministic diagnosis baseline
- optional LLM refinement

File chính:
- [engine.py](c:/Users/linhn/Desktop/Dự%20án/src/diagnosis/engine.py)

### Trạng thái nghiên cứu hiện tại

Module này đang hoạt động, nhưng **chưa được tinh chỉnh sâu theo evidence mới nhất**.

Nó là phần tiếp theo cần nâng để tận dụng:
- `alignment_map`
- `dependency_mismatch`
- `graph_edit_distance`
- `reordered_but_consistent_steps`

---

## 7.6. Pedagogy Planner

### Vai trò

Map diagnosis sang quyết định sư phạm:
- teacher move
- hint level
- focus points
- disclosure budget

File chính:
- [planner.py](c:/Users/linhn/Desktop/Dự%20án/src/pedagogy/planner.py)

### Trạng thái

Đã có taxonomy và planner deterministic.

### Ý nghĩa nghiên cứu

Phân tách diagnosis khỏi pedagogy cho phép đánh giá riêng:
- hệ hiểu lỗi đúng chưa?
- và hệ dạy đúng chưa?

---

## 7.7. Hint Generator + Verifier

### Vai trò

Sinh gợi ý và kiểm gợi ý.

Files chính:
- [generator.py](c:/Users/linhn/Desktop/Dự%20án/src/hint/generator.py)
- [controller.py](c:/Users/linhn/Desktop/Dự%20án/src/hint/controller.py)
- [verifier.py](c:/Users/linhn/Desktop/Dự%20án/src/hint/verifier.py)

### Đã làm được

- tách planner khỏi generator,
- có fallback hint,
- có anti-spoiler verification,
- có alignment checks,
- có safe fallback nếu LLM hint fail.

### Phần chưa tinh chỉnh sâu

- chưa có critic/repair mạnh cho hint,
- verifier vẫn thiên về rules,
- chưa có đánh giá sư phạm đủ sâu.

---

## 8. Đánh Giá Trạng Thái Hiện Tại Của Dự Án

## 8.1. Những gì đã hoàn thành tốt

1. **Kiến trúc tổng thể đã được hình thành rõ**
- pipeline nhiều tầng,
- grounded,
- có symbolic runtime,
- có graph ở cả problem side và student side.

2. **Formalizer và evidence đã tiến khá xa**
- không còn là hệ chỉ dựa vào final answer,
- mà đã có process-aware artifacts.

3. **Codebase đã được tách module tương đối sạch**
- dễ tiếp tục làm nghiên cứu,
- dễ benchmark,
- dễ ablation.

4. **Có test phủ tương đối tốt cho trạng thái hiện tại**
- toàn bộ test hiện pass.

## 8.2. Những gì vẫn còn là hạn chế

1. diagnosis chưa tận dụng hết evidence mới
2. pedagogy/hint chưa được nâng tương xứng
3. benchmark nghiên cứu chưa được đóng gói thành protocol hoàn chỉnh
4. chưa có thực nghiệm hệ thống trên tập dữ liệu lớn / nhiều loại bài
5. chưa có learning-based verifier/ranker thật sự

---

## 9. Benchmark, Baseline, Ablation: Cần Làm Gì Để Bài Toán Nghiên Cứu “Đứng Vững”

Đây là phần rất quan trọng để chứng minh tính nghiên cứu khi báo cáo.

## 9.1. Benchmark cần xây

Cần một benchmark gồm:

- **Problem set**
  - bài toán lời văn thuộc nhiều kiểu:
    - additive
    - subtractive
    - multiplicative
    - rate/unit
    - discount/threshold
    - partition/grouping

- **Student answer set**
  - đáp án đúng
  - sai final answer
  - nhầm target
  - sai arithmetic
  - sai relation
  - đúng nhưng reorder
  - đúng nhưng gộp bước
  - unparseable

- **Gold annotations**
  - target thật
  - correct final answer
  - first divergence step
  - diagnosis label
  - acceptable hint category

## 9.2. Baseline cần có

1. **Direct LLM baseline**
- đưa đề + bài làm học sinh cho LLM rồi bảo chẩn đoán trực tiếp

2. **Heuristic-only baseline**
- bỏ LLM,
- chỉ dùng parser/rules

3. **No-graph baseline**
- vẫn có structured artifacts nhưng không build graph

4. **Final-answer-only baseline**
- chỉ so đáp án cuối, không so process

## 9.3. Ablations cần làm

Một số ablation rất đáng giá:

1. bỏ `problem_graph`
2. bỏ `student_graph`
3. bỏ `alignment_map`
4. greedy alignment vs global alignment
5. no dependency edges vs dependency-aware comparison
6. no graph-edit summary vs có graph-edit summary
7. heuristic-only formalizer vs LLM-assisted formalizer
8. heuristic-only student work vs LLM-assisted student work

## 9.4. Metrics nên dùng

### Cho formalizer
- graph validity rate
- executable rate
- target correctness
- quantity-role accuracy

### Cho student work
- final answer extraction accuracy
- step extraction quality
- target inference accuracy

### Cho evidence
- alignment accuracy
- first divergence localization accuracy
- false positive rate cho reordered-but-correct cases

### Cho diagnosis
- diagnosis label accuracy
- subtype accuracy
- localization accuracy

### Cho hint
- spoiler violation rate
- teacher-move alignment
- human preference / pedagogical usefulness

---

## 10. Những Gì Chứng Minh Dự Án Có Thể Mở Rộng Thành Công Trình Nghiên Cứu Hoàn Chỉnh

1. Có problem formulation rõ
2. Có hypotheses rõ
3. Có architectural novelty tương đối rõ:
- graph-based formalization
- student process graph
- process-aware evidence

4. Có thể benchmark và ablate
5. Có thể tách từng module để nghiên cứu độc lập
6. Có thể mở rộng theo:
- verifier learning
- ranking
- RL

---

## 11. Định Hướng Tiếp Theo

## 11.1. Ưu tiên ngắn hạn

1. **Nâng diagnosis**
- tận dụng evidence mới:
  - alignment map
  - dependency mismatch
  - graph edit distance
  - reordered-but-consistent

2. **Tinh chỉnh pedagogy/hint**
- dựa trên diagnosis tốt hơn
- thêm repair layer cho hint

3. **Làm bộ benchmark nội bộ**
- để đánh giá có hệ thống

## 11.2. Định hướng trung hạn

1. candidate generation + reranking
2. verifier mạnh hơn thay vì chỉ deterministic rules
3. debugging dashboard / report tooling tốt hơn

## 11.3. Định hướng dài hạn: Reinforcement Learning

Nếu còn thời gian, hệ có thể phát triển theo hướng RL ở 2 mức:

### A. RL cho policy chẩn đoán / evidence ranking
- state:
  - problem graph
  - student graph
  - evidence candidates
- action:
  - chọn alignment / diagnosis path tốt nhất
- reward:
  - đúng diagnosis
  - đúng first divergence

### B. RL cho pedagogical policy / hint policy
- state:
  - diagnosis
  - hint plan
  - student progress
- action:
  - chọn teacher move
  - chọn hint level
- reward:
  - học sinh sửa được lỗi
  - hint không lộ đáp án
  - số lượt tutoring giảm

Tuy nhiên, RL nên được xem là hướng mở rộng sau khi:
- benchmark ổn định,
- evidence/diagnosis đủ đáng tin,
- có protocol reward hợp lý.

---

## 12. Kết Luận Tiến Độ Hiện Tại

Tính đến thời điểm hiện tại, dự án đã vượt qua giai đoạn “prototype gọi LLM” và đang trở thành một **hệ tutoring neuro-symbolic có cấu trúc rõ ràng**.

Các điểm mạnh nổi bật:

- đã formalize đề bài thành graph/executable plan,
- đã formalize bài làm học sinh thành graph,
- đã có evidence builder theo hướng process-aware,
- đã tách pipeline thành các module có thể benchmark và nghiên cứu độc lập,
- đã có nền tảng tốt để tiếp tục sang diagnosis, pedagogy và hint một cách bài bản.

Nói cách khác, dự án hiện tại đã có đủ các yếu tố để được xem là một **đề tài nghiên cứu nghiêm túc**, không chỉ là một ứng dụng kỹ thuật:

- có bài toán khoa học rõ ràng,
- có hypotheses rõ,
- có thiết kế kiến trúc có thể kiểm chứng,
- có tiềm năng benchmark/ablation,
- có hướng mở rộng thành learning system / RL trong giai đoạn sau.

---

## 13. Trạng Thái Kỹ Thuật Hiện Tại

- Toàn bộ test hiện pass:

```powershell
.\venv\Scripts\python.exe -m pytest tests -q
```

- Kết quả gần nhất:
  - `56 passed`
  - `1 warning`

Warning hiện tại là `PytestCacheWarning` của Windows, không phải lỗi logic của hệ thống.
