DART synthetic training dataset (10,000 rows)
=============================================

Files
- dart_synthetic_training_10000.csv: all four profiles, 10,000 rows
- grandparent_2500.csv
- elder_adult_2500.csv
- youth_2500.csv
- children_2500.csv

Important
This is synthetic prototype data, not measured human usability data. Models trained on it learn the assumptions and formula patterns used to generate it. They cannot be described as empirically accurate until calibrated against real user testing.

Figma API mapping
The Figma REST API returns a nested document/node JSON tree. It does NOT directly return several engineered features in this dataset. DART's parser must derive them from node properties:
- font_size_px: node.style.fontSize for TEXT nodes (aggregate/representative statistic per component or screen)
- text_char_count: node.characters length
- node_width_px / node_height_px: node.absoluteBoundingBox.width / height
- contrast_ratio: compute from text fill and background fill colors; not a direct Figma field
- nearest_element_spacing_px: derive from node bounds and neighboring node bounds
- visible_element_count: count visible nodes in the selected frame
- navigation_depth: app/task flow metadata supplied by developer or inferred from linked prototype flows; not reliably available from a single static frame
- label_complexity_score: engineered NLP/text heuristic from node.characters
- layout_complexity_score: engineered score from node types, nesting, auto-layout and constraints
- interactive_element_count: count likely interactive nodes/components, based on naming/component conventions or annotations
- text_node_count / image_count: count node types and image fills
- minimum_target_dimension_px: min(width,height) of interactive targets
- whitespace_ratio: estimate from frame area vs occupied node area
- task_step_count: supplied by task definition or prototype flow

Agent profile features are added by DART, not fetched from Figma:
reading_speed_wpm, attention_span_sec, visual_sensitivity, motor_precision, comprehension_factor.

Targets
- task_time_seconds
- error_probability
- completion_probability
- difficulty_score

Recommended first model
Train one separate multi-output RandomForestRegressor per agent, using the UI feature columns plus that agent's profile columns. Do not use agent_type as a feature if training separate models. Exclude all target columns from X.
For actual predictions, aggregate extracted features at the same granularity as training (e.g., one task/screen/component row), then append the fixed profile values.

Data semantics
Each row is one synthetic UI-task scenario, not one complete Figma file. The data distributions are generated for a prototype and should be replaced or augmented with observations from usability tests.
