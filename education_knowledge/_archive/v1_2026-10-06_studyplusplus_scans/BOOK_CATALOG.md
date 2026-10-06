# Book Catalog

Hand-curated. One row per physical source file. **10 files = 10 distinct books.** There are no duplicate books, alternative editions, split volumes, teacher/student versions, notes, guides, question banks or separate answer keys in the dataset. All metadata was read from each book's credits page (page image).

## Common facts (all 10 books)
- **Authority:** Punjab Education, Curriculum, Training and Assessment Authority (**PECTAA**), Lahore.
- **Curriculum basis:** Updated/Revised **National Curriculum of Pakistan 2023** (NCP-2023).
- **Edition:** **Experimental Edition**, 1st edition, 1st impression.
- **Language:** English (Bismillah line in Arabic on covers).
- **Material type:** Textbook. Exercises are embedded at chapter ends; some books add answers, pairing schemes and model papers (see below).
- **File form:** scanned image PDFs (Ghostscript/PDF24), **no native text layer**; "studyplusplus.com (study++)" watermark on every page. "(Study++)" in the Class 12 filenames refers to this scan source, not a different publisher.
- **Text layer:** produced for this project by OCR, in `source_text/<BOOK_ID>.ocr.txt`.

## Class 11 (folder `11 Class Data/`)

| Book ID | Subject | Title / label | Printed | Copies · Price | Publisher / printer | Authors (lead) | PDF pages | Chapters | File status |
|---|---|---|---|---|---|---|---|---|---|
| C11-PHY | Physics | Physics 11 | June 2025 | 15,000 · Rs 252 | Idara Farogh-e-Adab-o-Science / Ishaq Al Fateh Press | Prof. (Rtd.) Muhammad Ali Shahid et al. (6) | 276 | 12 | ✅ complete |
| C11-CHEM | Chemistry | Chemistry 11 | June 2025 | 12,000 · Rs 310 | Ilmi Book House / Muhammadi Printers | Prof. (R) Dr. Jamil Anwar et al. (12) | 360 | 16 | ⚠ complete, **16 duplicated scan pages** (printed 125–140) |
| C11-BIO | Biology | Biology 11 | June 2025 | 20,000 · Rs 257 | Jamia Asharfia / Ishaq Al Fateh Press | Muhammad Nadeem Asghar et al. (6) | 282 | 12 | ✅ complete |
| C11-MATH | Mathematics | Mathematics 11 | June 2025 | 10,000 · Rs 283 | Sfwan Group, Lahore / Qudrat Ullah Printers | Prof. Shamshad M. Lodhi (late) et al.; NCP-2023 alignment by Dr. Malik Anjum Javed et al. | 262 | 14 units | ❌ **printed pp.100–149 missing** (U6 partial, U7 missing, U8 partial) |
| C11-CS | Computer Science | Computer Science 11 (cover styling: "Computer Science and Entrepreneurship") | June 2025 | 15,000 · Rs 142 | Muhammadi Traders & Printers | Prof. Dr. Muhammad Atif Chattha; Prof. Dr. Syed Waqar ul Qounain Jaffry | 144 | 9 units | ✅ complete |

## Class 12 (folder `12 Class Data/`)

| Book ID | Subject | Title / label | Printed | Copies · Price | Publisher / printer | Authors (lead) | PDF pages | Chapters | File status |
|---|---|---|---|---|---|---|---|---|---|
| C12-PHY | Physics | PHYSICS 12 | July 2026 | 3,500 · Rs 160 | Attiya Publishing House / Etihad Publishers & Printer | Prof. Muhammad Ali Shahid et al. (8) | 180 | 9 (Ch 13–21) | ✅ complete |
| C12-CHEM | Chemistry | CHEMISTRY 12 | Aug 2026 | 4,000 · Rs 223 | Progressive Books / Top Mountain Printers & Publishers | Dr. Ch. Jamil Anwar et al. (7) | 264 | 17 (U 17–33) | ✅ complete |
| C12-BIO | Biology | BIOLOGY 12 | Aug 2026 | 3,500 · Rs 215 | Nishan Publisher / Mithu Printers LHR | Muhammad Nadeem Asghar; Prof. Dr. Tahir Abbas; Zunnorain Ahmed | 256 | 13 (Ch 13–25) | ✅ complete |
| C12-MATH | Mathematics | MATHEMATICS 12 | Aug 2026 | 3,500 · Rs 264 | Kashmir Book Depot, Rawalpindi / Etihad Publishers & Printers | Mr. Mazhar Hussain et al. (6) | 320 | 11 units | ⚠ complete content; **model paper cut off** at last page (PDF 320) |
| C12-CS | Computer Science | Computer Science and Entrepreneurship 12 | July 2026 | 5,000 · Rs 134 | Al-Faisal Nashran / Ishaq Al-Fateh Printers | Dr. Abdul Sattar; Mr. Zulfiqar Ali Kullachi | 144 | 9 | ✅ complete |

## What each book contains (material classification)

| Book ID | Textbook chapters | End-of-chapter exercises | Answer key | Practical / lab | Pairing scheme | Model paper | Other back matter |
|---|---|---|---|---|---|---|---|
| C11-PHY | ✅ | MCQ, Short, Constructed Response, Comprehensive, Numerical | Numerical answers inline (in brackets); **no MCQ key** | — | — | — | Bibliography (PDF 276) |
| C11-CHEM | ✅ | MCQ, Short, Descriptive, Numerical | **None** | ✅ Ch 16: lab safety, first aid, acid-base titration, salt analysis (anions/cations) | — | — | Bibliography (PDF 360) |
| C11-BIO | ✅ | MCQ, Short, Long, Inquisitive Questions | **None** | — | — | — | — |
| C11-MATH | ✅ (U6 partial, U7 missing, U8 partial) | Exercises N.n (problem sets) | ✅ Answers section, printed 291–309 (PDF 244–262), includes answers for missing Ex. 6.5–6.11 and 7.1–7.4 | — | — | — | — |
| C11-CS | ✅ | MCQ, Short, Long | ✅ MCQ keys only (PDF 144; 77 of 78; Unit 5 Q8 key missing) | Python coding content | — | — | — |
| C12-PHY | ✅ | MCQ, Short, Constructed Response, Comprehensive, Numerical | Numerical answers inline; **no MCQ key** | — | ✅ PDF 176+ | ✅ to PDF 180 | — |
| C12-CHEM | ✅ | MCQ, Short-Answer, Constructed-Response, Descriptive | **None** | — | ✅ PDF 261 | ✅ PDF 262–264 | Periodic Table (PDF 4) |
| C12-BIO | ✅ | MCQ, Short, Long, Inquisitive Questions | **None** | — | ✅ PDF 252–253 | ✅ PDF 253–256 | — |
| C12-MATH | ✅ | Exercises N.n (problem sets) | ✅ Answers PDF 301–314 (some gaps) | — | ✅ PDF 315–316 (+ paper pattern) | ✅ PDF 317–320 (**truncated**) | — |
| C12-CS | ✅ | MCQ, Short, Long + chapter Summary | ✅ MCQ key after each chapter (90; Ch 9 Q10 key printed wrongly) | Python OOP / GUI / testing code | ✅ PDF 140–141 | ✅ PDF 142–144 | — |

Categories **not present** anywhere in the dataset: standalone notes, past (board) papers, separate question banks or MCQ banks, solution manuals, teacher guides, practical notebooks, and the Class 11 pairing scheme or model papers.

## Size

| | Class 11 | Class 12 | Total |
|---|---|---|---|
| Files / books | 5 / 5 | 5 / 5 | 10 / 10 |
| PDF pages | 1,324 | 1,164 | 2,488 |
| Chapters / units indexed | 63 | 59 | 122 |
| Numbered topics + subtopics | 1,073 | 723 | 1,796 |
