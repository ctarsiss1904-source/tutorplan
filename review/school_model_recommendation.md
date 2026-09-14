# School model recommendation

Keep the current provisional `school_id` unchanged during this audit. Add `normalized_school_name`, `school_level`, `canonical_school_key`, `official_school_code`, `official_address`, and `source_count` in a later migration. `official_school_code` must become the preferred key only after an authoritative match. Preserve every Excel relation with `relation_type: source_reference` by default; use `living_area_reference` only for rows already classified as living areas. Do not infer a school address or convert a reference into `in_region`.
