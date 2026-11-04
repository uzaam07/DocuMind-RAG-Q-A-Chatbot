# DocuMind evaluation report

- **Mock run (deterministic offline models)**
- Generated: 2026-11-01T06:41:31Z
- Questions: 37 (k = 5)

| Mode | Hit@k | MRR | Answer accuracy | Citation correctness | Fallback accuracy | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| `vector` | 78.6% | 0.667 | 53.6% | 60.7% | 67.6% | 13 | 15 |
| `hybrid` | 82.1% | 0.717 | 53.6% | 60.7% | 67.6% | 14 | 18 |
| `hybrid_rerank` | 89.3% | 0.795 | 55.4% | 64.3% | 70.3% | 13 | 15 |

Answer cache: cold 14 ms vs warm 7 ms (2.0x faster on repeat questions).

Hit@k and MRR are measured over answerable questions; fallback accuracy covers all questions (answers when it should, declines when it should).
