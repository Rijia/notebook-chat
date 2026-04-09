Perform a rigorous customer/entity segmentation analysis. $ARGUMENTS should describe what entity to segment (customers, merchants, users) and which columns to use. Use the dataframe already loaded.

## Requirements

### 1. Aggregation & Feature Construction
- Aggregate to entity level (one row per entity)
- Create behavioral features across multiple time windows (7d, 30d, 90d, 180d)
- Create recency, frequency, monetary (RFM) features if transaction data is available
- Log-transform skewed features before clustering

### 2. Preprocessing
- Standard-scale all features before clustering
- Drop features with >20% missingness; impute the rest with median
- Remove features with near-zero variance

### 3. Optimal K Selection
- Run K-means for k=2 through k=10
- Plot elbow curve (inertia) and Silhouette scores side by side
- State the chosen k and justify (elbow point + silhouette peak)

### 4. Clustering
- Fit K-means with chosen k (random_state=42, n_init=10)
- Assign cluster labels back to entity dataframe

### 5. Cluster Characterization
For each cluster, report:
- Size (n and % of total)
- Mean and median of each feature
- Key metrics: revenue, frequency, recency

Produce:
- A heatmap of normalized feature means per cluster (z-scores)
- 2D scatter plots of top principal components colored by cluster
- KDE plots per feature, one line per cluster, all on same axes

### 6. Business Naming & Strategy
- Give each cluster a descriptive business name (e.g., "High-Value Active", "At-Risk Dormant")
- For each cluster, write 2-3 sentences: who they are, what they need, recommended action
- Show revenue/volume concentration: what % of GMV/revenue does each cluster represent?

### 7. Stability Check
- Re-run with a different random seed and check if cluster assignments are stable (>90% agreement via ARI)
- If unstable, note it and consider hierarchical clustering as alternative

## Code Standards
- Functions for each stage: aggregate, preprocess, find_k, fit_clusters, characterize
- All plots labeled and saved with descriptive filenames
- Cluster labels stored in dataframe as `segment` column

## Plotting Standards
Apply these principles to every chart generated in this analysis:

**Chart type**
- Prefer bar charts over pie charts for segment size comparisons
- Avoid 3D effects and dual y-axes
- Use overlaid KDE plots (one line per segment, shared axes) for distribution comparisons — not stacked bars
- For segment rank changes over time, use slope charts

**Axes**
- Bar charts: value axis MUST start at zero
- Use round tick values; label axes with units

**Labels and titles**
- Titles state the finding ("Segment A has 3× higher LTV" not "LTV by Segment")
- Direct labels on chart elements preferred over legends; when using a legend, match its order to the chart's visual order
- Color the segment lines/bars consistently with the cluster labels used throughout the analysis

**Color**
- Use one distinct color per segment, consistently across all charts
- Default to seaborn's `colorblind` palette or matplotlib's `tab10`
- Never use different colors within a single segment's bars
