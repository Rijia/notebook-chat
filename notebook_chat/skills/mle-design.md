Design an ML system using the structured 7-step framework from Alex Xu & Ali Aminian's ML System Design Interview. $ARGUMENTS should describe the use case (e.g., "design a feed ranking system", "build a query-ad matching model").

## 7-Step ML System Design Framework

### Step 1: Requirements Clarification
Before any technical decisions, clarify scope:
- **Business objective**: What metric does this move? (revenue, engagement, retention, safety)
- **ML framing**: Is this supervised, self-supervised, or RL? Classification vs ranking vs regression?
- **Scale**: QPS, user base, item corpus size, label volume, latency SLA
- **Constraints**: Online vs offline inference, edge vs cloud, explainability requirements, regulatory limits
- **Non-requirements**: Explicitly state what is out of scope to avoid scope creep

### Step 2: Problem Framing & ML Objective
Translate the business objective into a precise ML objective:
- Define the **label** precisely: What event counts as positive? (e.g., "click" vs "click + dwell > 5s")
- Identify **proxy metric risks**: Optimizing clicks can hurt long-term retention; say so
- Choose **loss function**: BCE for binary, listwise/pairwise loss for ranking (LambdaRank, ApproxNDCG)
- Define **offline evaluation metrics**: AUC, NDCG@k, MRR, Precision@k — and why each was chosen
- Define the mapping from offline metric → online metric (A/B test primary KPI)

### Step 3: Data Pipeline
Design the full data flow before touching model architecture:

**Training Data**
- Sources: user events (clicks, dwell, shares), item metadata, graph signals
- **Label construction**: How are positives/negatives defined? Negative sampling strategy? (random, hard, in-batch)
- **Temporal split**: Always split by time, never randomly — avoids data leakage
- **Class imbalance**: CTR ~0.1–2%; techniques: downsampling negatives (preserve prior by reweighting), focal loss, oversampling

**Data Quality Checklist**
- Exposure bias: items never shown cannot be labeled negative — use caution
- Selection bias: users who convert differ from users who don't engage
- Feedback delay: delayed conversions (purchases) need time-window decisions
- Training-serving skew: log the exact features used at serving time (point-in-time correctness)

**Feature Store**
- Online store (Redis, DynamoDB): low-latency serving, pre-computed user/item embeddings
- Offline store (Parquet on S3, Delta Lake): training pipelines, historical features
- **Point-in-time joins**: use the feature value as it was at prediction time, not the current value

### Step 4: Feature Engineering

**User Features**
- Demographics (age, location, language)
- Behavioral: session-level (last 10 interactions), short-term (7d), long-term (90d) histories
- Embeddings: user ID embedding, behavioral sequence embedding (sum/attention pool)

**Item Features**
- Content: text embeddings (TF-IDF, BERT), image embeddings (ResNet/ViT), categorical
- Engagement statistics: CTR, like rate, share rate — with age/popularity bias correction
- Freshness: time since publication, content decay signals

**Context Features**
- Device, time of day, day of week, surface (home feed vs search vs notification)
- Query (search systems): query embedding, query-item interaction features

**Cross Features**
- User × Item: co-occurrence in history, similarity between user profile embedding and item embedding
- Polynomial/hash trick: for memorization of specific (user, item) patterns in wide models

### Step 5: Model Selection & Architecture

**Retrieval Stage (Candidate Generation)**
Goal: reduce corpus from millions → hundreds at <10ms latency
- **Two-Tower Model**: separate user encoder and item encoder; dot product similarity at serving time
  - Train with in-batch negatives + hard negatives (items near the decision boundary)
  - Index item embeddings with ANN (FAISS HNSW, ScaNN); serve via approximate nearest neighbor
  - Cannot model cross-features between user and item at this stage (encoders are independent)
- **Alternatives**: collaborative filtering (matrix factorization), graph-based (GraphSAGE for PYMK)

**Ranking Stage**
Goal: score ~hundreds of candidates with richer features; latency budget ~50–100ms
- **DeepFM**: factorization machine for low-order interactions + DNN for high-order; good for ads CTR
- **Wide & Deep**: wide = memorization (cross features), deep = generalization
- **DCN v2**: explicit cross network replaces the wide component; strong for feature interactions
- **Multi-task DNN**: shared bottom + task-specific towers; predict CTR + CVR + engagement jointly
  - Avoids training separate models; shared representations transfer between tasks
  - ESMM (Entire Space Multi-task Model): jointly models CTR and CTCVR to address selection bias in CVR

**Reranking Stage** (optional)
Goal: apply business rules, diversity, freshness, policy constraints
- Deterministic rules: suppress already-seen, dedup author, boost new content
- MMR (Maximal Marginal Relevance): diversity via explicit deduplication of similar embeddings
- Contextual bandits or slate optimization for diversity-aware reranking

**Special Architectures by Use Case**
| Use Case | Primary Architecture |
|----------|---------------------|
| Ads CTR | DeepFM, DCN v2, Wide & Deep |
| Feed ranking | Multi-task DNN (CTR + CVR + dwell) |
| Recommendations | Two-tower retrieval + ranking DNN |
| PYMK / friend suggestions | GNN (GraphSAGE, PinSage) |
| Search ranking | Bi-encoder (retrieval) + cross-encoder reranker |
| NLP/content understanding | Fine-tuned BERT / sentence transformers |

### Step 6: Evaluation Framework

**Offline Evaluation**
- Train/val/test split by time — never random
- Metrics: AUC-ROC (ranking ability), Log Loss (calibration), NDCG@k, Precision@k, Recall@k
- **Calibration check**: predicted probability should match empirical click rate by decile (reliability diagram)
- Baseline: always compare to a simple baseline (popularity, recency, logistic regression)

**Online Evaluation (A/B Test)**
- Randomize at user level (not request level) to avoid within-user contamination
- Primary metric: business KPI (revenue, engagement time, D7 retention)
- Guardrail metrics: latency p99, error rate, diversity (intrasession similarity), user-reported quality
- Minimum detectable effect: power analysis before launch, not after
- Novelty effect window: run for ≥2 weeks to distinguish novelty from real lift

**Slice Analysis**
- Break results by user segment (new vs returning, platform, geography)
- Break results by item type/age (new items vs established)
- A significant average effect can hide harm to a subgroup

### Step 7: Serving & Production

**Serving Architecture**
```
Request → [Retrieval: Two-Tower ANN] → [Ranking: DNN score] → [Reranking: Rules + Diversity] → Response
```
- Pre-compute item embeddings offline; serve from ANN index
- User embeddings: pre-compute for active users; fallback for cold-start
- Cache: feature lookup cache (Redis), result cache for repeated queries

**Latency Budget** (example for feed ranking)
| Stage | Budget |
|-------|--------|
| Feature lookup | 5–10ms |
| Retrieval (ANN) | 5–10ms |
| Ranking inference | 20–50ms |
| Reranking + business logic | 5ms |
| Total p99 | <100ms |

**Cold Start**
- New users: use demographic priors, onboarding signals, popular/trending items
- New items: use content-based embeddings (no behavioral signal yet); boost in retrieval
- Transition: blend content-based and behavioral signals as data accumulates

**Training Pipeline**
- Batch retraining: full model retrain nightly/weekly on recent data
- Online/incremental learning: update embeddings or last layers with streaming data (Kafka → Flink → model)
- Feature freshness SLA: engagement stats should lag <1 hour; user behavioral features <15 min

**Monitoring**
- **Data drift**: input feature distribution shift (KL divergence, PSI per feature daily)
- **Label drift**: CTR trend — is a drop real or is the model predicting differently?
- **Prediction drift**: score distribution shift — monitor percentiles daily
- **Model staleness**: track AUC degradation on a held-out recent slice; trigger retrain if AUC drops >X%
- **Business metrics dashboard**: tie model metrics to business KPIs; alert on decoupling

**Failure Modes to Address Explicitly**
- Popularity bias: most retrieved items are popular → add diversity injection, use long-tail sampling
- Filter bubbles: engagement optimization → add content diversity constraint
- Position bias: items shown higher get clicked more → use inverse propensity scoring in training
- Feedback loops: model's predictions influence future labels → monitor label distribution over time

## Code Standards
- Show schema for feature tables (column name, type, freshness SLA)
- For any architectural diagram, describe it as a numbered pipeline with latency at each hop
- Report all offline metrics with confidence intervals; a single number without variance is incomplete
- When comparing architectures, use a table: model, pros, cons, latency, training complexity
