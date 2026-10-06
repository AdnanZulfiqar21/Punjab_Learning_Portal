# Source File Map

> **Generated file** — produced by `tools/build_indexes.py` from `books/*.json` on 2026-10-06. Do not edit by hand; fix the per-book JSON and re-run.

Every indexed chapter maps to a page range in an original file. Original files are **read-only**; the OCR text layer for each file lives in `source_text/`.

| Book ID | Class | Subject | Source file | PDF pages | Page rule | OCR text layer |
|---|---|---|---|---|---|---|
| C11-PHY | 11 | Physics | `11 Class Data/11 Physics Book Punjab Board.pdf` | 276 | pdf = printed + 3 (no exceptions found; front matter PDF 1-3) | `source_text/C11-PHY.ocr.txt` |
| C11-CHEM | 11 | Chemistry | `11 Class Data/11 Chemistry Book Punjab Board.pdf` | 360 | pdf = printed + 4 for printed 1-124 (PDF 5-128); printed 125-140 scanned twice in PDF 129-160 (printed p -> PDF first copy and second copy: 125->129/131, 126->130/132, 127->133/135, 128->134/136, 129->137/139, 130->138/140, 131->141/143, 132->142/144, 133->145/147, 134->146/148, 135->149/151, 136->150/152, 137->153/155, 138->154/156, 139->157/159, 140->158/160); pdf = printed + 20 for printed 141-340 (PDF 161-360) | `source_text/C11-CHEM.ocr.txt` |
| C11-BIO | 11 | Biology | `11 Class Data/11 Biology Book Punjab Board.pdf` | 282 | pdf = printed + 3 | `source_text/C11-BIO.ocr.txt` |
| C11-MATH | 11 | Mathematics | `11 Class Data/11 Mathematics Book Punjab Board.pdf` | 262 | pdf = printed + 3 for printed 1-99 (PDF 4-102); printed pages 100-149 are MISSING; pdf = printed - 47 for printed 150-309 (PDF 103-262) | `source_text/C11-MATH.ocr.txt` |
| C11-CS | 11 | Computer Science | `11 Class Data/11 Computer Science Book Punjab Board.pdf` | 144 | pdf = printed + 3 (no exceptions found; printed 1-141 = PDF 4-144) | `source_text/C11-CS.ocr.txt` |
| C12-PHY | 12 | Physics | `12 Class Data/12 Physics Book Punjab Board (Study++).pdf` | 180 | pdf = printed + 3 (no exceptions; chapters numbered 13-21 continuing from Class 11) | `source_text/C12-PHY.ocr.txt` |
| C12-CHEM | 12 | Chemistry | `12 Class Data/12 Chemistry Book Punjab Board (Study++).pdf` | 264 | pdf = printed + 4 (no exceptions; front matter PDF 1-4 unpaginated) | `source_text/C12-CHEM.ocr.txt` |
| C12-BIO | 12 | Biology | `12 Class Data/12 Biology Book Punjab Board (Study++).pdf` | 256 | pdf = printed + 3 (no exceptions found; PDF 1-3 unnumbered front matter: cover, TOC, credits) | `source_text/C12-BIO.ocr.txt` |
| C12-MATH | 12 | Mathematics | `12 Class Data/12 Mathematics Book Punjab Board (Study++).pdf` | 320 | pdf = printed + 2 throughout (PDF 3 = printed 1 ... PDF 320 = printed 318); verified on ≈45 sample pages across all units; PDF 1 cover and PDF 2 contents/credits are unnumbered | `source_text/C12-MATH.ocr.txt` |
| C12-CS | 12 | Computer Science | `12 Class Data/12 Computer Science Book PECTAA (Study++).pdf` | 144 | pdf = printed + 3 for all content pages (PDF 4-144 = printed 1-141); PDF 1-3 unnumbered front matter | `source_text/C12-CS.ocr.txt` |

## `11 Class Data/11 Physics Book Punjab Board.pdf` → C11-PHY

| Section | Printed pp. | PDF pp. | Exercise PDF pp. | Status |
|---|---|---|---|---|
| Ch 1 Measurements | 1–18 | 4–21 | 17–21 | complete |
| Ch 2 Force and Motion | 19–47 | 22–50 | 48–50 | complete |
| Ch 3 Circular and Rotational Motion | 48–68 | 51–71 | 68–71 | complete |
| Ch 4 Work, Energy and Power | 69–86 | 72–89 | 86–89 | complete |
| Ch 5 Solids and Fluid Dynamics | 87–111 | 90–114 | 112–114 | complete |
| Ch 6 Heat and Thermodynamics | 112–131 | 115–134 | 131–134 | complete |
| Ch 7 Waves and Vibrations | 132–166 | 135–169 | 166–169 | complete |
| Ch 8 Physical Optics and Gravitational Waves | 167–184 | 170–187 | 185–187 | complete |
| Ch 9 Electrostatics and Current Electricity | 185–221 | 188–224 | 220–224 | complete |
| Ch 10 Electromagnetism | 222–243 | 225–246 | 242–246 | complete |
| Ch 11 Special Theory of Relativity | 244–253 | 247–256 | 255–256 | complete |
| Ch 12 Nuclear and Particle Physics | 254–272 | 257–275 | 272–275 | complete |
| Bibliography | — | 276–276 | — | back matter |

**File issues:**

- Price Rs 252 and publisher spelling taken from caller's verified facts; price not legible in OCR of PDF 2.
- Faint/garbled section headings recovered from images: 1.7 (PDF 15), 3.2 (PDF 56), 5.7/5.8/5.13/5.14 (PDF 97, 100, 109), 6.8 (PDF 126), 7.1/7.3/7.10/7.11 (PDF 135, 139, 157, 159), 8.2/8.3 (PDF 172), 9.8/9.9/9.12/9.13 (PDF 202, 203, 206), 10.3/10.10 (PDF 230, 241), 11.2-11.5 (PDF 248-252), 12.2/12.4/12.6 (PDF 259, 262, 267).
- Ch 9 MCQ 9.10 is a magnetism question duplicated as MCQ 10.2 (PDF 222, 242).
- Ch 2 Numerical 2.5 printed answer order appears inconsistent (height/range) (PDF 50).
- Ch 5 Numerical 5.6 answer looks inconsistent with given data (PDF 114).
- Ch 6 Example 6.4 answer '825 oC' in OCR (likely 8.25 deg C) (PDF 129).
- Ch 7 Numerical 7.9 answer partly garbled (PDF 169); Ch 8 Numerical 8.1, 8.2 answers illegible in OCR (PDF 187).
- Ch 9 Numerical 9.10 answer not found (PDF 224); Ch 10 Numerical 10.8 answer garbled and 10.12 answer not visible (PDF 246).
- Ch 12 MCQs 12.11-12.13, 12.19 options and Short Q12.4 reactions lost in OCR (PDF 273-274) - use page images.
- Question counts are from numbered items in OCR cross-checked with images for Ch 1 (PDF 19) and Ch 12 (PDF 275); other counts follow OCR numbering (high confidence).
- Equations throughout are heavily garbled in OCR; formulas listed in Section 4 are standard forms reconstructed from context and spot-checked images; verify against PDF before verbatim reuse.

## `11 Class Data/11 Chemistry Book Punjab Board.pdf` → C11-CHEM

| Section | Printed pp. | PDF pp. | Exercise PDF pp. | Status |
|---|---|---|---|---|
| Ch 1 Periodic Table and Periodic Properties | 1–19 | 5–23 | 21–23 | complete |
| Ch 2 Atomic Structure | 20–42 | 24–46 | 44–46 | complete |
| Ch 3 Chemical Bonding | 43–69 | 47–73 | 70–73 | complete |
| Ch 4 Stoichiometry | 70–90 | 74–94 | 92–94 | complete |
| Ch 5 States and Phases of Matter | 91–111 | 95–115 | 113–115 | complete |
| Ch 6 Chemical Energetics | 112–139 | 116–159 | 150–159 | complete |
| Ch 7 Reaction Kinetics | 140–162 | 158–182 | 178–182 | complete |
| Ch 8 Chemical Equilibrium | 163–184 | 183–204 | 201–204 | complete |
| Ch 9 Acid-Base Chemistry | 185–206 | 205–226 | 224–226 | complete |
| Ch 10 Electrochemistry | 207–235 | 227–255 | 252–255 | complete |
| Ch 11 Hydrocarbons | 236–264 | 256–284 | 281–284 | complete |
| Ch 12 Nitrogen and Sulfur | 265–282 | 285–302 | 300–302 | complete |
| Ch 13 Halogens | 283–296 | 303–316 | 314–316 | complete |
| Ch 14 Atmosphere | 297–313 | 317–333 | 331–333 | complete |
| Ch 15 Basic Separation Techniques | 314–325 | 334–345 | 344–345 | complete |
| Ch 16 Lab Safety and Practical Skills | 326–339 | 346–359 | 358–359 | complete |
| Bibliography | — | 360–360 | — | back matter |

**File issues:**

- Duplicated pages: printed pp. 125-140 (PDF 129-160) were scanned twice as consecutive two-page spreads: 125-126 = PDF 129-130 & 131-132; 127-128 = 133-134 & 135-136; 129-130 = 137-138 & 139-140; 131-132 = 141-142 & 143-144; 133-134 = 145-146 & 147-148; 135-136 = 149-150 & 151-152; 137-138 = 153-154 & 155-156; 139-140 = 157-158 & 159-160. Folios render-verified; no printed page missing. Offset changes from +4 to +20.
- SLO code blocks for Ch 2, 3, 4 and 7 are all printed '[C-11-A-01 to C-11-A-25]' (PDF 24, 47, 74, 158; render-verified) - evident printing error; Ch 7 range should logically be A-124 to A-134.
- Ch 10 SLO code '[C-11-A-56 to C-11-B-78]' and Ch 14 '[C-11-C-01 to C-11-B-14]' mix strand letters; Ch 13 '[C-11-B-19 to C-11-B-41]' overlaps Ch 12 '[C-11-B-30 to C-11-B-41]' (render-verified).
- No answer keys for MCQs, short questions or numericals anywhere in the book.
- Heading numbering anomalies: Ch 13 has two sections numbered 13.1 (no 13.2) (PDF 305); Ch 10 sub-heading '10.22.2' under 10.21 (PDF 251); Ch 14 factor list skips iii) (PDF 326-327); Ch 6 Sample Problem 6.6 used twice (PDF 127, 133); Ch 7 numerical questions restart at Q.6 (PDF 181); Ch 4 short-question label g) printed twice (PDF 93-94).
- Ch 7: orphan temperature vs rate-constant table at top of PDF 182 without a question stem (Requires Review).
- Ch 8 exercise has no 'Numerical Problems' heading; Q.7-Q.9 are numerical (PDF 204).
- Ch 16 MCQs/Quick Checks refer to chromyl chloride, brown-ring and lake tests not described in the text (PDF 354-359).
- Data inconsistencies: O second electron affinity +798 vs +844 kJ/mol (Ch 1, PDF 14-15); Sample Problem 4.17 NH3 mass 1.81 g vs 18.1 g and SP 4.20 actual yield 3.15 g vs 2.85 g (PDF 86, 90).
- OCR garbles equations, subscripts, tables, MCQ options and IUPAC names throughout (especially Ch 6, 8, 11); OCR missed SLO code on PDF 317 (Ch 14).

## `11 Class Data/11 Biology Book Punjab Board.pdf` → C11-BIO

| Section | Printed pp. | PDF pp. | Exercise PDF pp. | Status |
|---|---|---|---|---|
| Ch 1 Biodiversity and Classification | 1–32 | 4–35 | 33–35 | complete |
| Ch 2 Bacteria and Viruses | 33–47 | 36–50 | 48–50 | complete |
| Ch 3 Cells and Subcellular Organelles | 48–90 | 51–93 | 89–93 | complete |
| Ch 4 Molecular Biology | 91–126 | 94–129 | 128–129 | complete |
| Ch 5 Enzymes | 127–139 | 130–142 | 141–142 | complete |
| Ch 6 Bioenergetics | 140–166 | 143–169 | 167–169 | complete |
| Ch 7 Structural and Computational Biology | 167–176 | 170–179 | 178–179 | complete |
| Ch 8 Plant Physiology | 177–201 | 180–204 | 203–204 | complete |
| Ch 9 Human Digestive System | 202–214 | 205–217 | 216–217 | complete |
| Ch 10 Human Respiratory System | 215–230 | 218–233 | 232–233 | complete |
| Ch 11 Human Circulatory System | 231–254 | 234–257 | 255–257 | complete |
| Ch 12 Human Skeletal and Muscular Systems | 255–279 | 258–282 | 280–282 | complete |
| Cover (title page: Biology 11, PECTAA) | — | 1–1 | — | back matter |
| Table of Contents | — | 2–2 | — | back matter |
| Credits / imprint page (authors, editors, printing details) | — | 3–3 | — | back matter |

**File issues:**

- No answer key anywhere: MCQ answers are not printed in chapters or at the back of the book (whole book, PDF 1-282).
- No back matter: no glossary, index, bibliography, appendices or answer section; the last page (PDF 282, printed 279) is the end of the Chapter 12 exercise.
- TOC title for Ch 4 'Molecular Biology' vs chapter opener 'Biomolecules' (PDF 2 vs 94).
- Ch 1: phylum numbering jumps 8 -> 10 (PDF 20-21); Eukarya characteristic list skips item 4 (PDF 8); 'seven classes/two groups' vs 'five groups' wording for vertebrates (PDF 22).
- Ch 5: SLO cites five enzyme classes; text has six (PDF 130 vs 139-140). No 'EXERCISE' banner visible at PDF 141.
- Ch 9 has a single numbered heading (9.1) for the entire chapter (PDF 205-215).
- Ch 10-12 exercise headers omit 'SECTION 1/2/3' labels used in Ch 1-9 (PDF 232-233, 255-256, 280-282).
- Some exercise questions test content not in the chapter text: Ch 10 MCQ 6 (lung volumes, PDF 232), Ch 12 Short Q8 (bone repair, PDF 281), Ch 9 Short Q15 (stress and digestion, PDF 217), Ch 1 Short Q7 (genetic drift, PDF 35).
- OCR: tables (kingdom comparison PDF 13, bacterial groups PDF 43-44, Table 4.1/4.2 PDF 95/102-103, optimum pH PDF 135, enzyme classes PDF 140, muscle comparison PDF 273) and all chemical/biochemical equations are garbled - use PDF images.
- OCR figure-caption mislabels: 'Figure 14.9' (PDF 243), 'Figure 11.66' (PDF 248), 'Figure 6.68' (PDF 161), 'Figure 12.3' for vertebral column (PDF 264).
- Ch 3 SLO 'Differentiate between' is truncated (PDF 51); Ch 11 SLO list has a duplicated garbled item (PDF 234).
- Probable printed factual slips (verify against print): 'Berzelius (in 1938)' (PDF 110); myoglobin 'single polynucleotide chain' (PDF 227).
- Ch 8: root-pathway list numbered '4.' instead of '1.' in OCR (PDF 187); 'EXERCISE' banner not captured on PDF 203.
- Watermark 'studyplusplus.com (study++)' crosses text diagonally on every page; it occasionally degrades OCR but text remains legible in renders.

## `11 Class Data/11 Mathematics Book Punjab Board.pdf` → C11-MATH

| Section | Printed pp. | PDF pp. | Exercise PDF pp. | Status |
|---|---|---|---|---|
| Ch 1 Complex Numbers | 1–21 | 4–24 | 8–24 | complete |
| Ch 2 Functions and Graphs | 22–33 | 25–36 | 29–36 | complete |
| Ch 3 Theory of Quadratic Functions | 34–43 | 37–46 | 42–46 | complete |
| Ch 4 Matrices and Determinants | 44–77 | 47–80 | 56–80 | complete |
| Ch 5 Partial Fractions | 78–87 | 81–90 | 88–90 | complete |
| Ch 6 Sequences and Series | 88–122 | 91–102 | 92–102 | partial |
| Ch 7 Permutations and Combinations | 123–139 | — | — | missing |
| Ch 8 Mathematical Inductions and Binomial Theorem | 140–168 | 103–121 | 103–121 | partial |
| Ch 9 Division of Polynomials | 169–176 | 122–129 | 126–129 | complete |
| Ch 10 Trigonometric Identities | 177–199 | 130–152 | 138–152 | complete |
| Ch 11 Trigonometric Functions and their Graphs | 200–217 | 153–170 | 158–170 | complete |
| Ch 12 Limit and Continuity | 218–236 | 171–189 | 182–189 | complete |
| Ch 13 Differentiation | 237–257 | 190–210 | 201–210 | complete |
| Ch 14 Vectors in Space | 258–290 | 211–243 | 218–243 | complete |
| Cover | — | 1–1 | — | back matter |
| Credits / imprint | — | 2–2 | — | back matter |
| Table of Contents | — | 3–3 | — | back matter |
| Answers | — | 244–262 | — | back matter |

**File issues:**

- CRITICAL GAP: printed pages 100-149 missing. PDF 102 = printed 99 (Unit 6, §6.5.1-6.5.2); PDF 103 = printed 150 (Unit 8, Exercise 8.1 tail).
- Unit 6 partial (printed 100-122 missing, incl. Exercises 6.5-6.11 whose answers exist on PDF 254-255).
- Unit 7 Permutations and Combinations entirely missing (printed 123-139); only answers to Exercises 7.1-7.4 survive (PDF 255-256).
- Unit 8 partial (printed 140-149 missing: induction sections and Exercise 8.1 Q1(i)-(vi)).
- No other gaps, duplicates or out-of-order pages detected (printed page numbers checked on sampled pages and all exercise pages; content continuous).
- Section numbering irregular in Unit 1 (1.4 and 1.4.1 repeated; '1.3.3' after 1.4.1) PDF 15-19.
- OCR garbles equations, matrices, determinants and answer keys throughout; exercise counts were verified from page images.
- Exercise 13.1 answers list items 12-13 not matching the printed exercise (PDF 201 vs 261) - Requires Review.
- No SLO codes, MCQs, review exercises, glossary or index printed in this book.

## `11 Class Data/11 Computer Science Book Punjab Board.pdf` → C11-CS

| Section | Printed pp. | PDF pp. | Exercise PDF pp. | Status |
|---|---|---|---|---|
| Ch 1 Introduction to Software Development | 1–19 | 4–22 | 21–22 | complete |
| Ch 2 Python Programming | 20–40 | 23–43 | 42–43 | complete |
| Ch 3 Algorithms and Problem Solving | 41–55 | 44–58 | 57–58 | complete |
| Ch 4 Computational Structures | 56–66 | 59–69 | 68–69 | complete |
| Ch 5 Data Analytics | 67–85 | 70–88 | 87–88 | complete |
| Ch 6 Emerging Technologies | 86–100 | 89–103 | 102–103 | complete |
| Ch 7 Legal and Ethical Aspects of Computing System | 101–114 | 104–117 | 116–117 | complete |
| Ch 8 Online Research and Digital Literacy | 115–124 | 118–127 | 125–127 | complete |
| Ch 9 Entrepreneurship in Digital Age | 125–140 | 128–143 | 142–143 | complete |
| Cover | — | 1–1 | — | back matter |
| Credits / imprint | — | 2–2 | — | back matter |
| Contents | — | 3–3 | — | back matter |
| Answers (MCQ answer keys) | — | 144–144 | — | back matter |

**File issues:**

- PDF 144 (Answers) has very little OCR text (63 chars) because it is a grid of answer-letter tables; content read by rendering.
- Unit openers for Units 3 and 8 (PDF 44, 118) - unit banner/title not captured by OCR; verified by rendering. Unit 1 opener (PDF 4) also lacks banner text in OCR.
- Answer key for Unit 5 lists 7 answers but the exercise has 8 MCQs (PDF 87-88, 144) - MCQ 8 key missing.
- Heading numbering anomalies as printed: 2.4.1.3 used twice (PDF 30); 2.9.1.1 -> 2.9.1.4-2.9.1.6 (PDF 39-40); 5.5.2 printed as 5.2.2 (PDF 86); 9.4.3 missing (PDF 135-136); Pharming unnumbered (PDF 107).
- Figure 3.6 number used twice (PDF 52 Merge Sort, PDF 55 Binary Search).
- Unit 6 Short Questions numbered 1,2,3,4,6,8,9 (7 questions) PDF 103.
- Unit 2 Long Questions numbering anomaly: item 2 is a heading for item 3's sub-parts (PDF 43).
- Content gaps vs SLOs/exercises: Blockchain 2.0 (Unit 6), Community Cloud (U6 MCQ 2), bias/evaluating sources/critical thinking (Unit 7), Boolean operators/research questions (Unit 8), experimental design and Python/Tableau/Matplotlib (Unit 5), list aliasing (U4 Short Q2) not covered in text.
- Unit 3 MCQ 5 stem says 'Search algorithm' but options are sorting algorithms (PDF 57).
- OCR garbles Python code (Unit 2 PDF 24-41, Unit 4 PDF 60-63), statistical formulas and tables (Unit 5 PDF 71-73, 76-81) - verify against PDF.
- OCR omits some printed page numbers (e.g. PDF 47, 67, 127) but page sequence is continuous; pdf = printed + 3 holds throughout.

## `12 Class Data/12 Physics Book Punjab Board (Study++).pdf` → C12-PHY

| Section | Printed pp. | PDF pp. | Exercise PDF pp. | Status |
|---|---|---|---|---|
| Ch 13 Thermal Physics | 1–14 | 4–17 | 15–17 | complete |
| Ch 14 Simple Harmonic Motion | 15–40 | 18–43 | 41–43 | complete |
| Ch 15 Physical Optics | 41–57 | 44–60 | 58–60 | complete |
| Ch 16 Electrostatics | 58–81 | 61–84 | 82–84 | complete |
| Ch 17 Alternating Current | 82–108 | 85–111 | 109–111 | complete |
| Ch 18 Quantum Physics | 109–127 | 112–130 | 127–130 | complete |
| Ch 19 Nuclear and Particle Physics | 128–145 | 131–148 | 146–148 | complete |
| Ch 20 Medical Physics | 146–155 | 149–158 | 157–158 | complete |
| Ch 21 Space and Environment | 156–172 | 159–175 | 173–175 | complete |
| Pairing Scheme / Instructions for Preparation of Examination Paper | — | 176–177 | — | back matter |
| Model Paper | — | 177–180 | — | back matter |

**File issues:**

- OCR heading numbers corrupted; headings verified from page images
- Equations garbled in OCR across chapters
- Several MCQ options garbled/missing in OCR (13.1, 13.3, 13.4, 15.3, 16.4, 16.9, 18.x, 21.1-21.4, 21.7)
- Ch20 has no numerical problems or worked examples though Q9 requires a numerical part
- No MCQ answer keys anywhere; numerical answers missing in OCR for 13.3, 13.5, 15.7, 21.8

## `12 Class Data/12 Chemistry Book Punjab Board (Study++).pdf` → C12-CHEM

| Section | Printed pp. | PDF pp. | Exercise PDF pp. | Status |
|---|---|---|---|---|
| Ch 17 Group 2 Elements | 1–13 | 5–17 | 16–17 | complete |
| Ch 18 Transition Metals | 14–33 | 18–37 | 36–37 | complete |
| Ch 19 Basics of Organic Chemistry | 34–54 | 38–58 | 56–58 | complete |
| Ch 20 Aromatic Hydrocarbons | 55–70 | 59–74 | 71–74 | complete |
| Ch 21 Halogenoalkanes | 71–83 | 75–87 | 85–87 | complete |
| Ch 22 Hydroxy Compounds | 84–96 | 88–100 | 98–100 | complete |
| Ch 23 Carbonyl Compounds and Carboxylic Acids | 97–113 | 101–117 | 115–117 | complete |
| Ch 24 Organic Nitrogen Compounds | 114–128 | 118–132 | 131–132 | complete |
| Ch 25 Organic Synthesis | 129–139 | 133–143 | 142–143 | complete |
| Ch 26 Polymers | 140–154 | 144–158 | 156–158 | complete |
| Ch 27 Biochemistry | 155–172 | 159–176 | 174–176 | complete |
| Ch 28 Chromatography | 173–180 | 177–184 | 182–184 | complete |
| Ch 29 Spectroscopy-1 | 181–196 | 185–200 | 198–200 | complete |
| Ch 30 Spectroscopy-2 NMR | 197–211 | 201–215 | 214–215 | complete |
| Ch 31 Materials and Energy | 212–226 | 216–230 | 229–230 | complete |
| Ch 32 Medicine, Agriculture and Industry | 227–241 | 231–245 | 243–245 | complete |
| Ch 33 Water | 242–256 | 246–260 | 259–260 | complete |
| Cover | — | 1–1 | — | back matter |
| Credits / imprint | — | 2–2 | — | back matter |
| Contents | — | 3–3 | — | back matter |
| Periodic Table | — | 4–4 | — | back matter |
| Pairing Scheme (Instructions for Preparation of Exam Paper) | — | 261–261 | — | back matter |
| Model Paper of Chemistry for Class-12 | — | 262–264 | — | back matter |

**File issues:**

- PDF 4 (Periodic Table) has no OCR text (image-only page) - the only low/no-text page.
- Low-text pages are short exercise tails: PDF 74 (Ch 20 descriptive), PDF 100 (Ch 22 CR/descriptive), PDF 198 (Ch 29 quick check/exercise start), PDF 3 (contents).
- Most top-level section numbers (e.g. 17.1, 22.3) are printed in coloured boxes and are dropped by OCR; numbering confirmed by visual check of rendered pages.
- SLO code numbering gaps/out-of-order: B-15 and D-38 to D-40 unused; Ch 25 (D-109 to D-115) follows Ch 26 (D-98 to D-108); Ch 28 (E-29 to E-33) follows Ch 30 (E-19 to E-28); E-01, E-02 unused; Ch 33 uses strand C (C-01 to C-08).
- Ch 18 PDF 34: MnO4-/C2O4 2- worked example shows E cell +2.01 V in equation but +1.03 V in text.
- Ch 30 PDF 213: 13C example inconsistency (2-methoxypropane vs 2-methylpropan-1-ol).
- Ch 31 PDF 227-228: section titled Fission and Fusion but fusion not described.
- Ch 27 PDF 175-176: one Constructed-Response label lost in OCR (count ≈5).
- No answer keys, glossary, summaries or index printed anywhere in the book.
- Equations, structural formulae, tables and spectra are frequently garbled in OCR; verify against PDF before reuse.

## `12 Class Data/12 Biology Book Punjab Board (Study++).pdf` → C12-BIO

| Section | Printed pp. | PDF pp. | Exercise PDF pp. | Status |
|---|---|---|---|---|
| Ch 13 Thermoregulation and Osmoregulation | 1–12 | 4–15 | 14–15 | complete |
| Ch 14 Human Urinary System | 13–25 | 16–28 | 27–28 | complete |
| Ch 15 Human Nervous System | 26–58 | 29–61 | 59–61 | complete |
| Ch 16 Human Endocrine System | 59–74 | 62–77 | 76–77 | complete |
| Ch 17 Human Reproductive System | 75–84 | 78–87 | 86–87 | complete |
| Ch 18 Inheritance | 85–116 | 88–119 | 116–119 | complete |
| Ch 19 Chromosome and DNA | 117–156 | 120–159 | 155–159 | complete |
| Ch 20 Biotechnology | 157–170 | 160–173 | 171–173 | complete |
| Ch 21 Immunity | 171–187 | 174–190 | 189–190 | complete |
| Ch 22 Biostatistics | 188–209 | 191–212 | 211–212 | complete |
| Ch 23 Pharmacology | 210–216 | 213–219 | 218–219 | complete |
| Ch 24 Evolution | 217–229 | 220–232 | 230–232 | complete |
| Ch 25 Ecology | 230–248 | 233–251 | 249–251 | complete |
| Cover | — | 1–1 | — | back matter |
| Table of Contents | — | 2–2 | — | back matter |
| Credits / imprint | — | 3–3 | — | back matter |
| Pairing Scheme / Instructions for Preparation of Exam Paper of Biology for Class-XII | — | 252–253 | — | back matter |
| Model Paper of Biology for Class-XII | — | 253–256 | — | back matter |

**File issues:**

- No missing, duplicated, blank or out-of-order PDF pages found; offset pdf = printed + 3 holds throughout PDF 4-256 (184 pages confirmed by OCR'd folios; spot-checked images at PDF 56-58, 74-77, 95, 101-102, 105, 116-117, 181, 186-187, 217, 220, 246, 252-256).
- No answer keys anywhere in the book (PDF 1-256).
- No SLO codes printed for any chapter.
- Printed duplicated text: end of monoclonal-antibody paragraph repeated at top of printed p.184 (PDF 186-187).
- Ch 23: numbering skips 23.4.1 (23.4 -> 23.4.2) (PDF 217); inconsistent heading style.
- Ch 23: Phase 3 trial size printed '18000-3,000' (PDF 214) - likely typo.
- OCR misreads of heading numbers: '5.3' for 16.3 (PDF 74), '13.6' for 18.6 (PDF 105), '24.11' for 24.1 (PDF 220), '25.0.1' for 25.6.1 (PDF 246), '% 7. t .2' for 17.1.2 (PDF 82); verified against images.
- OCR garbles tables: cranial nerves & ANS tables (PDF 46, 48), hormone tables (PDF 63-66), codon table (PDF 138), biostatistics tables (PDF 196-208), pairing scheme (PDF 252-253; verified from image).
- Ch 22 error-bar example Group C SD lower limit OCR '16.18' (should compute to 18.18) (PDF 207).
- Ch 25 Short Q11 mentions 'tropical rain forest' not in text (PDF 251); Model paper Q3(xi) 'neutral selection' not in Ch 24 text (PDF 256).
- Ch 21 transplant-match odds number missing in OCR (PDF 188); Ch 19 trisomy tidbit truncated (PDF 155).
- Time-sensitive content in Ch 25 (2025 floods, 2026 CO2 428 ppm).
- PDF 105 has a scan fold line; text still legible.

## `12 Class Data/12 Mathematics Book Punjab Board (Study++).pdf` → C12-MATH

| Section | Printed pp. | PDF pp. | Exercise PDF pp. | Status |
|---|---|---|---|---|
| Ch 1 Graphical Representation of Functions | 1–33 | 3–35 | 6–35 | complete |
| Ch 2 Further Differentiation | 34–70 | 36–72 | 43–72 | complete |
| Ch 3 Integration | 71–123 | 73–125 | 78–125 | complete |
| Ch 4 Differential Equations | 124–143 | 126–145 | 130–145 | complete |
| Ch 5 Analytical Geometry | 144–166 | 146–168 | 160–168 | complete |
| Ch 6 Conics | 167–222 | 169–224 | 179–224 | complete |
| Ch 7 Kinematics | 223–236 | 225–238 | 237–238 | complete |
| Ch 8 Numerical Solutions of Nonlinear Equations | 237–258 | 239–260 | 243–260 | complete |
| Ch 9 Inverse Trigonometric Functions and Their Graphs | 259–278 | 261–280 | 275–280 | complete |
| Ch 10 Solution of Trigonometric Equations | 279–288 | 281–290 | 285–290 | complete |
| Ch 11 Vector Valued Functions and Their Derivatives | 289–298 | 291–300 | 295–300 | complete |
| Cover | — | 1–1 | — | back matter |
| Contents and credits | — | 2–2 | — | back matter |
| Answers | — | 301–314 | — | back matter |
| Pairing Scheme / Paper Pattern | — | 315–316 | — | back matter |
| Model Question Paper (Annual Examination) | — | 317–320 | — | back matter |

**File issues:**

- Whole book is scanned images with study++ watermark; OCR garbles virtually all equations, integrals, matrices/determinants, tables and graph labels — use page images for any formula (PDF 3–320).
- Several sub-headings are printed in very faint grey and were missed or garbled by OCR (e.g. 3.8.1 PDF 117, 4.2.1 PDF 127, 4.4.1 PDF 133, 6.1.4 PDF 173, 8.3.4 PDF 248, 9.1.3 PDF 265, 6.4 'Derivation of the Standard Equation' PDF 195); all confirmed from images except the number of 8.3.4 (partly illegible, inferred).
- Answer key for Exercise 3.7 lists an answer numbered 13 but the exercise has 12 questions (PDF 123–125 vs PDF 307) — Requires Review.
- Exercise 10.1 has 24 questions but answers are printed only for Q1–21 (PDF 285 vs 312).
- Exercise 9.2 answers: only Q20 printed (most items are proofs) (PDF 312).
- Ex 2.5 answer block on PDF 305 is smudged/partly illegible.
- Figure numbering in Unit 10 jumps from Figure 10.3 to Figure 10.6 (PDF 285–288).
- Theorem numbering restarts inside Unit 6 (Theorem 1/2/3 reused) and Example numbering in OCR is noisy in Units 1–3; exact example numbers Requires Review.
- Model paper ends on PDF 320 with Q9(b) cut off at the bottom of the page (last page of PDF).
- No SLO codes and no bulleted SLO list are printed; outcomes are paraphrased from each unit's INTRODUCTION paragraph.
- No end-of-unit Review Exercise, MCQ set or Summary is printed in any unit; assessment is only via numbered Exercises (plus MCQs in the Model Paper).

## `12 Class Data/12 Computer Science Book PECTAA (Study++).pdf` → C12-CS

| Section | Printed pp. | PDF pp. | Exercise PDF pp. | Status |
|---|---|---|---|---|
| Ch 1 Computer Networks | 1–19 | 4–22 | 21–22 | complete |
| Ch 2 Computational Thinking & Algorithms | 20–32 | 23–35 | 34–35 | complete |
| Ch 3 Object Oriented Programming Using Python | 33–44 | 36–47 | 46–47 | complete |
| Ch 4 Development of Graphical User Interface (GUI) | 45–59 | 48–62 | 61–62 | complete |
| Ch 5 Code Testing and Debugging | 60–71 | 63–74 | 73–74 | complete |
| Ch 6 Data and Analysis | 72–88 | 75–91 | 90–91 | complete |
| Ch 7 Hypothesis Testing | 89–102 | 92–105 | 104–105 | complete |
| Ch 8 Applications of Computer Science | 103–117 | 106–120 | 119–120 | complete |
| Ch 9 Cybersecurity and Safe Digital Collaboration | 118–136 | 121–139 | 138–139 | complete |
| Pairing Scheme (Instructions for Preparation of Exam Paper) | — | 140–141 | — | back matter |
| Model Paper (Intermediate Part-II) | — | 142–144 | — | back matter |

**File issues:**

- TOC misprints 'Computer Neworks' and 'Graphical User Interface (GUI)' OCR as '(GUO' (PDF 3)
- Ch9 MCQ10 answer key error: keyed C (CPU) but correct is B (GDPR) (PDF 138-139)
- Ch7 PDF 92 includes ML hypothesis function h_theta(x)=y in statistics context
- Ch7 Summary has raw LaTeX artifacts (PDF 103)
- Ch6 Long Q3 asks about rule-based learning not covered (PDF 91)
- Model paper asks about tautology (Ch2), Entry.delete(), syntax vs exception, ZeroDivisionError, die-fairness hypotheses - beyond explicit textbook content (PDF 143-144)
- Model paper MCQ 9 misspells 'unitest' (PDF 142)
- Ch4 Update example caption without code (PDF 59)
- Ch6 F1 example shows 0.8880 vs 0.8889 (PDF 85)
- All code listings and formulas garbled by OCR; verify against page images

