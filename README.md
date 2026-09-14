# tutorplan.co.kr SEO generator

`python build.py` reads the immutable `과외.xlsx`, extracts national region and school entities, then emits only the requested Seoul–Gangnam-gu–Daechi-dong sample inventory and static pages.

Generated data is written to `data/generated/`; validation results are in `review/validation.csv`; rendered sample URLs live beneath `output/tutor/`.

The generator keeps `student_stage`, `school_type`, and `exam_type` separate, so pages such as `중등 영어과외` and `중학교 영어과외` cannot be conflated by the model.
