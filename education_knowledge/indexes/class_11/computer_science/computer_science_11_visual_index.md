# VISUAL INDEX — C11-CS

Class 11 · Computer Science · "COMPUTER SCIENCE 11" (PCTB Lahore, Experimental Edition) · file: 11 Class Data/11th Class Computer.pdf · pdf = printed + 3

## Summary: visuals by type per chapter
| Unit | Figure/labelled diagram | Table | Graph/chart | Flowchart/cycle | Photo/illustration | Math figure | Code listing | Other | Total |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 4 (Fig 1.5, 1.9, 1.10, 1.11) | 1 (Tab 1.1) | 0 | 7 (Fig 1.1, 1.2, 1.3, 1.4, 1.6, 1.12, Vis1-1) | 0 | 0 | 0 | 0 | 12 |
| 2 | 0 | 0 | 0 | 0 | 0 | 0 | ≈50 boxed listings (+1 output box) | 0 | ≈51 |
| 3 | 4 (Fig 3.4, 3.6, 3.7, 3.8) | 0 | 1 (Vis3-1 Big-O graph) | 2 (Fig 3.1, 3.2) | 1 (Fig 3.3 Sudoku) | 0 | 0 | 0 | 8 |
| 4 | 10 (Fig 4.4, 4.6, 4.8, 4.9, 4.10, 4.11, 4.12, 4.13, Vis4-1) | 0 | 0 | 0 | 3 (Fig 4.2, 4.3, 4.5, 4.7 — 4.7 is a photo-style tree) | 0 | 13 | 0 | 27 |
| 5 | 0 | 10 (Tab 5.1, Tab 5.2, Vis5-1/2/3/5/6/7/8) | 5 (Fig 5.4–5.8) | 0 | 0 | 1 (Vis5-4 logistic formulas) | 0 | 0 | 16 |
| 6 | 4 (Fig 6.1, 6.2, 6.4, 6.5) | 0 | 0 | 1 (Fig 6.3) | 0 | 0 | 0 | 0 | 5 |
| 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **Total** | 22 | 11 | 6 | 10 | 4 | 1 | ≈63 | 0 | ≈119 |

Captioned figures: 41 (Fig 1.1–1.6, 1.9–1.12; 3.1–3.4, 3.6–3.8; 4.2–4.13; 5.4–5.8; 6.1–6.5). Captioned tables: 3 (1.1, 5.1, 5.2). Missing numbers: Fig 1.7, 1.8, 3.5, 4.1, 5.1–5.3. Decorative: unit-opener banners (PDF 4, 33, 68, 90, 126, 153, 175, 194, 207) and "DID YOU KNOW?" / "Tidbits" / "EXERCISE" icons — not indexed.

---

## Unit 1 — Introduction to Software Development

### C11-CS/Ch1/Fig1.1
- Class 11 / Computer Science / C11-CS / Unit 1 / 1.2.2 Stages involved in SDLC
- Type: Flowchart/cycle (cascading stage diagram)
- PDF page: 6 · Printed page: 3
- Title/caption: Figure 1.1: System development life cycle stages
- Labels: Requirement, Analysis, Design, Coding/Implementation, Testing, Maintenance; feedback arrows between stages
- Represents: Six SDLC stages as a staircase of boxes with forward and backward (iteration) arrows.
- Educational importance: exam diagram — name/order the SDLC stages.
- Related concepts: SDLC, Waterfall (Fig 1.2)
- Quality: clear (small labels)

### C11-CS/Ch1/Tab1.1
- Unit 1 / Functional and Non-Functional Requirements (under 1.1.1.1 Requirement Gathering)
- Type: Table (2 columns × 4 rows)
- PDF page: 8 · Printed page: 5
- Title/caption: Table 1.1: Comparison between Functional and Non-Functional Requirements (heading inside table: "Differentiating Functional and Non Functional Requirements")
- Labels: columns Functional Requirements | Non-Functional Requirements; rows: define behaviours vs define quality attributes/constraints; what the system should do vs how it should perform; Example: user can borrow books vs handle 1000 users simultaneously; user interactions vs performance/usability/reliability
- Represents: Point-by-point comparison of the two requirement types.
- Educational importance: direct source for "differentiate functional and non-functional requirements" (Short Q1).
- Related concepts: requirement gathering; Library Management System example
- Quality: clear

### C11-CS/Ch1/Fig1.2
- Unit 1 / 1.1.1.1 Waterfall Model
- Type: Flowchart/cycle (descending arrow sequence)
- PDF page: 11 · Printed page: 8
- Title/caption: Figure 1.2: Waterfall Model
- Labels: title "Waterfall (Plan Driven)"; Requirements, Analysis, Design, Implementation, Testing, Delivery, Maintenance; sub-notes (define project scope, stakeholder interviews, high-level design, dev phases/review, testing/revisions, deployment); "Project Timeline" axis
- Represents: Sequential, non-returning phases of Waterfall along a timeline.
- Educational importance: contrast with Agile; identify phases.
- Related: SDLC stages, Agile (Fig 1.3)
- Quality: clear; sub-note text very small

### C11-CS/Ch1/Fig1.3
- Unit 1 / 1.1.1.1 Agile Methodology
- Type: Flowchart/cycle (circular arrow cycle)
- PDF page: 12 · Printed page: 9
- Title/caption: Figure 1.3: Agile Methodology
- Labels: centre "AGILE"; 1 Requirements, 2 Design, 3 Development, 4 Testing, 5 Deployment, 6 Review
- Represents: The iterative six-step Agile loop.
- Educational importance: shows iteration vs Waterfall's linearity.
- Related: sprints, continuous integration
- Quality: clear

### C11-CS/Ch1/Fig1.4
- Unit 1 / I. Scrum (1.1.1.1 Other Methodologies)
- Type: Flowchart/cycle (process flow)
- PDF page: 14 · Printed page: 11
- Title/caption: Figure 1.4: Scrum Lifecycle
- Labels: Product Backlog, Sprint Planning, Sprint Backlog, Scrum Team, Daily Scrum, Sprint Retrospective, Increment, Sprint Review
- Represents: Flow of Scrum artifacts and events from backlog to increment.
- Educational importance: name Scrum roles/events/artifacts (Short Q4, MCQ 5).
- Related: Agile, Product Owner/Scrum Master
- Quality: clear

### C11-CS/Ch1/Fig1.5
- Unit 1 / ii. Lean
- Type: Labelled diagram (mind-map with icons)
- PDF page: 15 · Printed page: 12
- Title/caption: Figure 1.5: Lean Software Development Model
- Labels: Lean Development; Eliminate Waste, Amplify Learning, Decide as Late as Possible, Deliver as Fast as Possible, Empower the Team, Build Integrity In, Optimize the whole
- Represents: The seven Lean principles.
- Educational importance: recall of Lean principles ("See the Whole" in text = "Optimize the whole" in figure).
- Related: Agile, DevOps
- Quality: clear

### C11-CS/Ch1/Fig1.6
- Unit 1 / 1.1.1.1 DevOps
- Type: Flowchart/cycle (infinity loop)
- PDF page: 16 · Printed page: 13
- Title/caption: Figure 1.6: DevOps Methodology
- Labels: Dev | Ops; plan, code, build, test, release, deploy, operate, monitor
- Represents: Continuous DevOps loop joining development and operations activities.
- Educational importance: identify CI/CD stages.
- Related: CI/CD, Agile
- Quality: clear

### C11-CS/Ch1/Vis1-1
- Unit 1 / 1.5 Project Planning and Management
- Type: Flowchart/cycle (timeline with icons)
- PDF page: 16 · Printed page: 13
- Title/caption: The 5 Phases of a Project Management Plan (descriptive — printed as a heading, no figure number)
- Labels: 1 Initiation, 2 Planning, 3 Execution, 4 Performance monitoring, 5 Project closure
- Represents: Five project-management phases in order.
- Educational importance: sequence recall; links to 1.4.x planning topics.
- Related: timelines, cost estimation, risk management
- Quality: clear

### C11-CS/Ch1/Fig1.9
- Unit 1 / 1.1.1.1 Use Case Diagrams
- Type: Labelled diagram (UML use case)
- PDF page: 21 · Printed page: 18
- Title/caption: Figure 1.9: Example Use Case Diagram for a Library System
- Labels: title "Simple Use case diagram"; actors Librarian, Student; use cases Borrow book, Return book; system boundary box
- Represents: Two actors linked to two use cases inside a system boundary.
- Educational importance: model for drawing use case diagrams (Long Q4).
- Related: actors, functional requirements
- Quality: clear

### C11-CS/Ch1/Fig1.10
- Unit 1 / 1.1.1.1 What is a Class Diagram?
- Type: Labelled diagram (UML class diagram)
- PDF page: 23 · Printed page: 20
- Title/caption: Figure 1.10: Class Diagram for Organizing Your Room
- Labels: Room (-name: String, -size: String); Box (-label: String, -contents: String); ToyBox (-toys: List), BookBox (-books: List), ClothesBox (-clothes: List); inheritance arrows
- Represents: Class hierarchy Room→Box→specialised boxes with attributes.
- Educational importance: class/attribute/inheritance notation.
- Related: OOP (Unit 2.8), inheritance
- Quality: clear

### C11-CS/Ch1/Fig1.11
- Unit 1 / 1.1.1.1 Sequence Diagrams
- Type: Labelled diagram (UML sequence)
- PDF page: 23 · Printed page: 20
- Title/caption: Figure 1.11: Sequence diagram of the user organizing items into labeled boxes
- Labels: lifelines User, Toys Box, Books Box, Clothes Box; messages open(), put toys inside, put books inside, put clothes inside, close()
- Represents: Time-ordered message flow from user to three boxes.
- Educational importance: model for Long Q5 (food-delivery sequence diagram); compare with activity diagram (Short Q7).
- Related: objects, messages
- Quality: clear

### C11-CS/Ch1/Fig1.12
- Unit 1 / 1.1.1.1 Activity Diagrams
- Type: Flowchart (UML activity)
- PDF page: 24 · Printed page: 21
- Title/caption: Figure 1.12: Activity Diagram with Decision and Connector Symbol
- Labels: Start, Order Placement, Food Preparation, decision "Food Ready?" Yes/No, Re-Prepare Food, Order Delivery, End; connector dot
- Represents: Restaurant order workflow with a decision loop.
- Educational importance: decision/connector symbols; basis for Long Q1 flowchart.
- Related: flowcharts (Unit 3 Fig 3.1)
- Quality: clear

---

## Unit 2 — Python Programming (Code listings)
No captioned figures/tables. The unit teaches through boxed Python listings, each followed by an "Explanation". Entries below are compact (one row per boxed listing). Type = Code listing; Quality = clear unless noted; Class/Subject/Book as above.

| Visual ID | PDF p | Printed p | Topic (heading as printed) | Identifier (descriptive — no official caption) | Represents / labels | Importance |
|---|---|---|---|---|---|---|
| C11-CS/Ch2/Code-1 | 35 | 32 | 2.2.1.1 Variable — Python Comments | Single-line and multi-line comment demo | `#` comment, `'''…'''` block, two print() calls (K2, Edhi Foundation) | comment syntax |
| C11-CS/Ch2/Code-2 | 36 | 33 | 2.2.1.1 Variable | age variable reassigned (Quaid-i-Azam 71, Allama Iqbal 60) — NOT boxed | print with multiple args | variable reassignment |
| C11-CS/Ch2/Code-3 | 37 | 34 | 2.2.1.5 Handling Integer and Float Inputs | int(input()) / float(input()) snippets (unboxed) | user_age, user_height | type conversion of input |
| C11-CS/Ch2/Code-4 | 37–38 | 34–35 | 1.2.1 Arithmetic Operators | a=10, b=3 with + * / // % ** and output comments | outputs 13, 30, 3.333…, 3, 1, 1000 | arithmetic operators |
| C11-CS/Ch2/Code-5 | 38 | 35 | 2.3.2 Comparison Operators | x, y = 10, 5 compared with > < == != >= <= (raster image) | outputs True/False per operator | comparison operators |
| C11-CS/Ch2/Code-6 | 39 | 36 | 1.1.2 Assignment Operators | a=10, b=5 with = += -= *= /= //= %= **= (raster image) | output comments a=15, 10, 50, 10.0, 2.0, 2.0, 32.0 | compound assignment |
| C11-CS/Ch2/Code-7 | 39–40 | 36–37 | 1.1.3 Logical Operators | x=True, y=False with and/or/not | note: OR output comment wrongly says "True and False = True" | logical operators |
| C11-CS/Ch2/Code-8 | 41 | 38 | 2.4.1.1 if Statement | temperature = 35; if temperature > 30: print("It's a hot day") | — | if syntax |
| C11-CS/Ch2/Code-9 | 42 | 39 | 2.4.1.2 if-else Statement | temperature = 15 if/else hot/not hot | — | if-else |
| C11-CS/Ch2/Code-10 | 42 | 39 | 2.4.1.3 Short Hand if-else | one-line conditional print | `print(...) if temperature > 30 else print(...)` | ternary form |
| C11-CS/Ch2/Code-11 | 43 | 40 | 2.4.1.3 if-elif-else | weather = "cloudy" sunny/rainy/else | — | if-elif-else |
| C11-CS/Ch2/Code-12 | 43 | 40 | 2.4.1.4 Nested and Chained Conditionals | weather="rainy", temperature=10 nested if | raincoat/umbrella/enjoy | nested if |
| C11-CS/Ch2/Code-13 | 44 | 41 | 2.4.2.1 while Loop | number=1; while number < 10 | prints 1–9 | while loop |
| C11-CS/Ch2/Code-14 | 44 | 41 | 2.4.2.2 for Loop — Example 1 | friends list greeting loop | ["Ahmad","Ali","Hassan"] (printed "All") | for over list |
| C11-CS/Ch2/Code-15 | 45 | 42 | 2.4.2.2 for Loop — Example 2 | shopping cart (list of dicts) total with f-strings + Output box | Apple $2.00, Banana $2.00, Orange $2.25, total $6.25 | dict/list iteration, f-string formatting |
| C11-CS/Ch2/Code-16 | 45 | 42 | 2.4.2.3 The range() Function | for i in range(5): print(i) | prints 0–4 | range() |
| C11-CS/Ch2/Code-17 | 46 | 43 | 2.5.1.1 Defining and Invoking Functions | def greet(name) … greet('Ali') (printed 'AH') | — | def/call |
| C11-CS/Ch2/Code-18 | 46 | 43 | 1.1.1.1 Function Parameters and Return Values | def add(a, b): return a + b | — | return value |
| C11-CS/Ch2/Code-19 | 47 | 44 | 2.5.1.3 Default Parameters | def greet(name="Student") | outputs for greet() and greet("Umer") | default args |
| C11-CS/Ch2/Code-20 | 47 | 44 | 2.5.1.4 Keyword Arguments | def introduce(name, age); call with age=20, name="Ali" (overprinted by Class Activity text — partly cut) | — | keyword args |
| C11-CS/Ch2/Code-21 | 47 | 44 | 2.5.1.5 Arbitrary Arguments | def add_numbers(*args): return sum(args) | outputs 6, 9 | *args |
| C11-CS/Ch2/Code-22 | 48 | 45 | 2.5.3 Importing and Using Libraries | import random; randint(1, 10) | — | random module |
| C11-CS/Ch2/Code-23 | 48 | 45 | 2.5.3 | import datetime; datetime.datetime.now() | — | datetime module |
| C11-CS/Ch2/Code-24 | 48 | 45 | 2.5.3 | import statistics; mean of [23,45,67,89,12,44,56] | — | statistics module |
| C11-CS/Ch2/Code-25 | 49 | 46 | 2.5.3.1 Module Search Path — Current Directory | helper.py: def greet() | — | user module |
| C11-CS/Ch2/Code-26 | 49 | 46 | 2.5.3.1 | main.py: import helper; helper.greet() | output "As-Salaam-Alaikum from helper.py!" | importing own module |
| C11-CS/Ch2/Code-27 | 49 | 46 | 2.5.3.1 — Standard Library | main.py: import random; f"Random number: {number}" | — | standard library lookup |
| C11-CS/Ch2/Code-28 | 50 | 47 | Package Structure | ecommerce/products.py: def list_products() (printed `1ist_products`) | returns ["Laptop","Mobile","Tablet"] | package module |
| C11-CS/Ch2/Code-29 | 50 | 47 | Package Structure | main script: from ecommerce import products | output ['Laptop','Mobile','Tablet'] | from-import |
| C11-CS/Ch2/Code-30 | 50 | 47 | 2.6.1.1 Creating Lists | fruits = ["Mango","Apple" "Banana"] (missing comma); print(fruits) | — | list creation |
| C11-CS/Ch2/Code-31 | 51 | 48 | 2.6.1.2 Accessing List Items | print(fruits[1]) → Apple | — | indexing |
| C11-CS/Ch2/Code-32 | 51 | 48 | 2.6.1.3 Modifying a List | fruits[0]="Orange"; fruits.append("Pineapple") | output list | item assignment/append |
| C11-CS/Ch2/Code-33 | 51 | 48 | 2.6.1.4 Methods and Operations on Lists | students append("Hina") + sort() | ['Ahmed','Ali','Hina','Sara'] | append/sort |
| C11-CS/Ch2/Code-34 | 52 | 49 | 2.6.1.5 List Operations | numbers[1:4] + [6,7] | [2,3,4,6,7] | slicing/concatenation |
| C11-CS/Ch2/Code-35 | 52 | 49 | 2.6.1.5 | student_names sort() then remove("Sara") | ['Ahmed','Ali','Hina'] | sort/remove |
| C11-CS/Ch2/Code-36 | 53 | 50 | 2.6.2 Tuples | my_tuple = (1, 2, 3, "Hello", 4.5); index; len | outputs 1, Hello, 5 | tuple basics |
| C11-CS/Ch2/Code-37 | 53 | 50 | 2.6.3.3 Negative Indices | fruits[0], fruits[-1], fruits[1:4], fruits[-4:-1] | — | positive/negative indexing & slicing |
| C11-CS/Ch2/Code-38 | 55 | 52 | The main Function | main.py with if __name__ == "__main__": main() | — | main guard |
| C11-CS/Ch2/Code-39 | 55 | 52 | 2.7.1 Working with Modules — Step 1 | greetings.py: def say_As-Salaam-Alaikum() (invalid identifier as printed) | — | module file |
| C11-CS/Ch2/Code-40 | 55 | 52 | 2.7.1 — Step 2 | main.py importing greetings; main() | output "As-Salaam-Alaikum, everyone!" | module use + main |
| C11-CS/Ch2/Code-41 | 57 | 54 | 2.8.1.1 Defining Classes and Creating Objects | class ToyCar with __init__(color, size, wheels), describe(); car1, car2 | printed `carl`; __init__ signature garbled | class/object |
| C11-CS/Ch2/Code-42 | 58 | 55 | 1.1.1.1 Access Modifiers | three short Car snippets: public color, _protected_var, __color + get_color() (unboxed) | — | public/protected/private |
| C11-CS/Ch2/Code-43 | 58 | 55 | 2.8.1.3 Constructor and Destructor | class Car with __init__ and __del__ printing message | — | constructor/destructor |
| C11-CS/Ch2/Code-44 | 59 | 56 | 2.8.1.4 Association — Aggregation | class Book; class Library with add_book() | — | aggregation |
| C11-CS/Ch2/Code-45 | 59 | 56 | 2.8.1.4 Association — Composition | class Room; class House creating Room objects | — | composition |
| C11-CS/Ch2/Code-46 | 60 | 57 | 2.8.1.5 Inheritance | class Animal; Dog(Animal); Cat(Animal) overriding make_sound() | — | inheritance/overriding |
| C11-CS/Ch2/Code-47 | 60 | 57 | 2.8.1.6 Polymorphism | def animal_sound(animal); dog, cat objects | outputs Bark!, Meow! (printed `anima1_sound`) | polymorphism |
| C11-CS/Ch2/Code-48 | 61 | 58 | 2.9.1.1 Try-Except Blocks | result = 10/a inside try; except ZeroDivisionError | — | try/except |
| C11-CS/Ch2/Code-49 | 61 | 58 | 2.9.1.2 Finally and Else | int(input()) division with except ZeroDivisionError/ValueError, else, finally — print scrambled | Quality: partly garbled | else/finally |
| C11-CS/Ch2/Code-50 | 61–62 | 58–59 | 2.9.1.3 Custom Exceptions | class CustomError(Exception); check_value(); raise; except CustomError as e | — | custom exception |
| C11-CS/Ch2/Code-51 | 62 | 59 | 2.9.1.5 Opening, Reading, Closing Files | with open("example.txt","r") as file: read() | — | file read |
| C11-CS/Ch2/Code-52 | 62 | 59 | 2.9.1.6 Writing to Files | open "w" write; open "a" append | — | file write/append |
| C11-CS/Ch2/Code-53 | 63 | 60 | 2.10.1.1 Types of Testing | import unittest; class TestMathOperations(unittest.TestCase); assertEqual | — | unit test |
| C11-CS/Ch2/Code-54 | 64 | 61 | 2.10.1.3 Common Debugging Techniques | def divide(a,b); try divide(10,0) except ZeroDivisionError as e (unboxed) | — | error handling for debugging |

(Entries Code-2, Code-3, Code-42, Code-54 are unboxed snippets listed for completeness; boxed listings ≈50.)

---

## Unit 3 — Algorithms and Problem Solving

### C11-CS/Ch3/Fig3.1
- Unit 3 / 3.1.1.2 Well-defined vs. ill-defined Problems
- Type: Flowchart
- PDF page: 70 · Printed page: 67
- Title/caption: Figure 3.1: Finding an Even Number
- Labels: Start; Write "Enter an integer"; Read x; decision x MOD 2 == 0 (True/False); Write "Even"; Write "Odd"; End
- Represents: Flowchart of the even/odd decision — a well-defined problem.
- Educational importance: flowchart symbols; sample for "draw a flowchart" questions (Unit 1 Long Q1).
- Related: well-defined problem, decision problem
- Quality: clear

### C11-CS/Ch3/Fig3.2
- Unit 3 / 3.2.1 Generate and Test Algorithm
- Type: Flowchart (block loop)
- PDF page: 72 · Printed page: 69
- Title/caption: Figure 3.2: Flowchart of the Generate and Test Algorithm Process.
- Labels: GENERATOR → Possible Solution → TESTER → Correct Solution → STOP; Incorrect Solution loops back
- Represents: Generate-and-test loop until a valid solution is found.
- Educational importance: Short Q2 (steps of generate and test).
- Related: heuristics, exhaustive search
- Quality: clear

### C11-CS/Ch3/Fig3.3
- Unit 3 / 3.3.3.2 Class NP
- Type: Photo/illustration (puzzle grid)
- PDF page: 76 · Printed page: 73
- Title/caption: Figure 3.3: A simple Sudoku Puzzle (text calls it Figure 3.5)
- Labels: 9×9 grid with given digits
- Represents: Example NP problem — easy to verify, hard to solve.
- Educational importance: illustration of NP verification vs solving.
- Related: NP, non-deterministic polynomial time
- Quality: clear

### C11-CS/Ch3/Fig3.4
- Unit 3 / 3.3.3.4 NP-Complete
- Type: Labelled diagram (Venn/nested sets)
- PDF page: 77 · Printed page: 74
- Title/caption: Figure 3.4 Venn diagram of the complexity classes P, NP, NP-hard, and NP-complete.
- Labels: P ⊂ NP; NP-Complete at intersection of NP and NP-Hard; NP-Hard
- Represents: Set relationships among the four complexity classes.
- Educational importance: exam diagram for Long Q1 (complexity classes).
- Related: tractable/intractable, P vs NP
- Quality: clear but faint line art

### C11-CS/Ch3/Vis3-1
- Unit 3 / 3.4.1.1 Big O Notation
- Type: Graph/chart
- PDF page: 79 · Printed page: 76
- Title/caption: Big O Notation growth curves (descriptive) — printed caption is WRONG: "Figure 1.1: System development life cycle stages"
- Labels: title "Big O Notation"; axes Time ↑ vs Input Size →; curves O(n²), O(n), O(log n), O(1)
- Represents: Relative growth of common time complexities as input grows.
- Educational importance: compare complexities (MCQ 9–10, Long Q7); referred to in text ("as seen by the flat line in the graph", PDF 80).
- Related: time complexity, Big O
- Quality: clear (raster, slightly blurred)

### C11-CS/Ch3/Fig3.6
- Unit 3 / 3.6.1 Divide and Conquer
- Type: Labelled diagram (recursion tree)
- PDF page: 81 · Printed page: 78
- Title/caption: Figure 3.6: Merge Sort Process
- Labels: [14, 7, 3, 12] → Divide → [14, 7] [3, 12] → Divide → 7 14 3 12 → merge → [3, 7, 12, 14] (dark boxes)
- Represents: Splitting an unsorted list into halves and merging sorted halves.
- Educational importance: divide-and-conquer illustration; Long Q6 comparison sort.
- Related: O(n log n), Bubble Sort
- Quality: clear, dark background

### C11-CS/Ch3/Fig3.7
- Unit 3 / 3.7.2.2 Binary Search
- Type: Labelled diagram (chalkboard-style step table)
- PDF page: 85 · Printed page: 82
- Title/caption: Figure 3.7: Binary Search Process
- Labels: "BINARY SEARCH"; sorted array 21 34 43 57 66 78; Search 78; steps "divide from middle / check mid / 43<78 look for 78 in right half / mid=66 / 66<78 look in right half / mid=78 element found"
- Represents: Halving the search interval until the target 78 is found.
- Educational importance: trace of binary search (Long Q3).
- Related: O(log n), sorted list prerequisite
- Quality: low-res raster, small handwriting-style text partly hard to read

### C11-CS/Ch3/Fig3.8
- Unit 3 / 3.7.3 Graph Algorithms
- Type: Labelled diagram (two trees)
- PDF page: 86 · Printed page: 83
- Title/caption: Figure 3.8: Comparison of BFS and DFS (text refers to it as Figure 3.9)
- Labels: BFS: Source Node 0, Layer 0/1/2, nodes 0–7, Output: 0,1,2,3,4,5,6,7; DFS: nodes 0–7, Output: 0,1,4,5,2,6,3,7
- Represents: Level-order (BFS) vs depth-first (DFS) visiting orders on the same tree.
- Educational importance: Short Q6 / Unit 4 Long Q7 traversal orders.
- Related: queue vs stack, Unit 4 Fig 4.13
- Quality: clear

---

## Unit 4 — Computational Structures

### C11-CS/Ch4/Fig4.2
- Unit 4 / 4.1.2.1 Stack Operations
- Type: Photo/illustration
- PDF page: 96 · Printed page: 93
- Title/caption: Figure 4.2: Stack of Books
- Labels: none (pile of books)
- Represents: Real-world LIFO analogy.
- Educational importance: analogy only.
- Related: push/pop
- Quality: clear

### C11-CS/Ch4/Fig4.3
- Unit 4 / 4.1.4 Queues
- Type: Photo/illustration (silhouettes)
- PDF page: 100 · Printed page: 97
- Title/caption: Figure 4.3: Queue of persons in front of the bank
- Labels: "remove" arrow at front, add arrow at back
- Represents: FIFO analogy — enter at back, leave from front.
- Educational importance: enqueue/dequeue ends.
- Related: FIFO
- Quality: clear

### C11-CS/Ch4/Fig4.4
- Unit 4 / 4.1.5.2 How We Traverse a Tree Using BFS?
- Type: Labelled diagram (binary tree)
- PDF page: 103 · Printed page: 100
- Title/caption: Figure 4.4: Balanced Binary Tree
- Labels: nodes 1 (root); 2, 3; 4, 5, 6, 7
- Represents: 7-node complete binary tree used for the 17-step BFS queue trace.
- Educational importance: BFS trace — exam-style (MCQ 6, Long Q6/7).
- Related: queue, level order
- Quality: clear (small)

### C11-CS/Ch4/Fig4.5
- Unit 4 / 4.1.6 Trees
- Type: Photo/illustration (cartoon family tree)
- PDF page: 106 · Printed page: 103
- Title/caption: Figure 4.5: Family Tree
- Labels: three generations (grandparents, parents, children) connected by lines; name labels not legible — UNCLEAR IN SOURCE
- Represents: Hierarchical parent–child structure as a tree.
- Educational importance: root/leaf/level analogy.
- Related: root node, hierarchy
- Quality: clear graphic, labels tiny

### C11-CS/Ch4/Fig4.6
- Unit 4 / 4.1.6.1 Properties of Trees (code example)
- Type: Labelled diagram (tree)
- PDF page: 107 · Printed page: 104
- Title/caption: Figure 4.6: A Family Tree Structure
- Labels: Grandparent → Parent2, Parent1 → Child2, Child1 (under Parent1)
- Represents: Tree produced by the FamilyTree class code on the same page.
- Educational importance: maps code (add_child) to structure.
- Related: Code-9 (FamilyMember/FamilyTree)
- Quality: clear; node order drawn right-to-left

### C11-CS/Ch4/Fig4.7
- Unit 4 / 4.1.7 Balanced Tree
- Type: Photo/illustration (book-shop tree graphic)
- PDF page: 108 · Printed page: 105
- Title/caption: Figure 4.7: Balanced Tree structure for organizing books in a Store
- Labels: "BOOK SHOP" trunk; branches Science, Story, Novels, Business, Baby, Cooking, Fantasy, Psychology…
- Represents: Decorative analogy of categories branching from a root (text example uses Science→Physics/Biology…).
- Educational importance: analogy only; figure categories differ from text.
- Related: balanced tree, O(log n) search
- Quality: clear

### C11-CS/Ch4/Fig4.8
- Unit 4 / 4.1.7.1 Operations on Tree — Traversal
- Type: Labelled diagram (binary tree)
- PDF page: 109 · Printed page: 106
- Title/caption: Figure 4.8: Tree Structure with Numeric Data
- Labels: root 1; children 3 (left), 2 (right) as drawn; leaves 7, 6 under 3 and 5, 4 under 2 — NOTE the drawing places 3 on the left and 2 on the right, whereas the traversal text treats 2 as the left child (in-order 4,2,5,1,6,3,7)
- Represents: 7-node tree for in-order, pre-order, post-order examples.
- Educational importance: traversal practice (MCQ 7, Long Q6).
- Related: traversal orders
- Quality: clear; left/right drawn mirrored relative to the text

### C11-CS/Ch4/Fig4.9
- Unit 4 / 4.1.7.2 Types of Trees — Binary Tree
- Type: Labelled diagram (binary tree)
- PDF page: 111 · Printed page: 108
- Title/caption: Figure 4.9: Binary Tree Representation of a Family Tree
- Labels: Grandparent; Parent2, Parent1; Child4, Child3 (under Parent2); Child2, Child1 (under Parent1)
- Represents: Binary tree where each node has at most two children.
- Educational importance: binary tree definition.
- Related: Fig 4.6
- Quality: clear

### C11-CS/Ch4/Fig4.10
- Unit 4 / 4.1.7.2 Types of Trees — AVL Trees
- Type: Labelled diagram (binary tree)
- PDF page: 112 · Printed page: 109
- Title/caption: Figure 4.10: AVL Tree.
- Labels: root 20; children 30 (left), 15 (right); 18, 10 under 15
- Represents: Self-balancing tree keeping height difference small (text: left side 15, 10, 18 vs right 30 — drawing mirrored).
- Educational importance: balance concept (MCQ 8 height).
- Related: balanced tree, height
- Quality: clear; drawn mirrored relative to text

### C11-CS/Ch4/Fig4.11
- Unit 4 / 4.1.8.4 Types of Graphs — Directed / Weighted
- Type: Labelled diagram (graph)
- PDF page: 115 · Printed page: 112
- Title/caption: Figure 4.11: Directed Weighted Graph
- Labels: vertices A, B, C, D, E; directed edges with weights 10, 12, 20, 32, 60, 7
- Represents: Directed graph whose edges carry weights (used for both directed and weighted examples).
- Educational importance: degree/weight/direction properties.
- Related: graph properties
- Quality: clear

### C11-CS/Ch4/Fig4.12
- Unit 4 / 4.1.8.4 Types of Graphs — Undirected
- Type: Labelled diagram (graph)
- PDF page: 115 · Printed page: 112
- Title/caption: Figure 4.12: Undirected Graph
- Labels: vertices A, B, C, D, E; undirected edges A–B, A–E, B–C, B–D, B–E, C–D, D–E (approx.)
- Represents: Two-way friendship-style connections.
- Educational importance: directed vs undirected contrast.
- Related: social network example
- Quality: clear

### C11-CS/Ch4/Fig4.13
- Unit 4 / 4.3.2 Combining Stack and Graph to perform DFS (also 4.3.3 BFS)
- Type: Labelled diagram (tree/graph)
- PDF page: 119 · Printed page: 116
- Title/caption: Figure 4.13: Graph Representation of a Tree with Numeric Nodes
- Labels: root 1; children 2, 3, 4; 5, 6 under 2; 7 under 3; 8, 9 under 4
- Represents: 9-node tree used for the step-by-step DFS (1,2,5,6,3,7,4,8,9) and BFS (1…9) traces.
- Educational importance: core traversal worked example; Long Q7 analogue.
- Related: stack (DFS), queue (BFS)
- Quality: clear

### C11-CS/Ch4/Vis4-1
- Unit 4 / Exercise — Long Question 7 (printed unnumbered)
- Type: Labelled diagram (directed graph) — exercise figure
- PDF page: 125 · Printed page: 122
- Title/caption: Graph for DFS/BFS traversal question (descriptive — no official caption)
- Labels: A → B, C, D; B → E, F; C → G, H (approx.); D → H, I; arrows directed downward
- Represents: Graph on which students must list DFS and BFS visiting orders from A.
- Educational importance: diagram-based exam question (required to answer).
- Related: 4.3.2, 4.3.3
- Quality: clear

### Unit 4 code listings
| Visual ID | PDF p | Printed p | Topic | Identifier (descriptive) | Represents | Importance |
|---|---|---|---|---|---|---|
| C11-CS/Ch4/Code-1 | 91 | 88 | 4.1.1.1 List Creation | items list of party supplies + print | list literal | list creation |
| C11-CS/Ch4/Code-2 | 92 | 89 | 4.1.1.2 List Properties | items list demonstrating mutability, heterogeneity, len, indexing, duplicates | append/remove, len(), items[2] | list properties demo |
| C11-CS/Ch4/Code-3 | 93 | 90 | 4.1.1.3 Insertion a | party_list.insert(0, "Invite friends") | output (omits inserted item — error) | insert() |
| C11-CS/Ch4/Code-4 | 93 | 90 | 4.1.1.3 Insertion b | party_list.append("Order cake") | — | append() |
| C11-CS/Ch4/Code-5 | 93 | 90 | 4.1.1.3 Insertion c | party_list.extend(["Party hats","Streamers"]) | — | extend() |
| C11-CS/Ch4/Code-6 | 94 | 91 | 4.1.1.3 Deletion a | party_list.remove("Buy snacks") | — | remove() |
| C11-CS/Ch4/Code-7 | 94 | 91 | 4.1.1.3 Deletion b | party_list.pop(0) | — | pop() |
| C11-CS/Ch4/Code-8 | 94 | 91 | 4.1.1.3 Deletion c | party_list.clear() | output [] | clear() |
| C11-CS/Ch4/Code-9 | 94 | 91 | 4.1.1.3 Searching a | if "Buy cold drinks" in party_list | — | in keyword (MCQ 2) |
| C11-CS/Ch4/Code-10 | 95 | 92 | 4.1.1.3 Searching b | party_list.index("Buy decorations") → 1 | — | index() |
| C11-CS/Ch4/Code-11 | 96 | 93 | 4.1.2.1 Stack Operations | stack_of_books: append 'Book A/B/C', pop() | prints stack after each op | push/pop with list |
| C11-CS/Ch4/Code-12 | 101 | 98 | 4.1.4.2 Queue Operations | from queue import Queue; q.put(Ahmed, Fatima, Ali); q.queue[0]; q.get(); q.put(Sara); list(q.queue) | printed `q.getO` | enqueue/dequeue/peek (Long Q5 model) |
| C11-CS/Ch4/Code-13 | 107 | 104 | 4.1.6.1 Properties of Trees | class FamilyMember / class FamilyTree (add_child, _find_member recursive) + example usage | typos Fami1yMember, Parenti, Childl | tree implementation with classes |
| C11-CS/Ch4/Code-14 | 116 | 113 | Graph Implementation Using Python | import networkx as nx; add_node A,B,C; add_edge; nx.draw; plt.show() (printed `pit`) | — | graph with NetworkX |

---

## Unit 5 — Data Analytics

### C11-CS/Ch5/Vis5-1
- Unit 5 / 5.2.3 Measures of Dispersion — Variance (Class A)
- Type: Table (calculation)
- PDF page: 129 · Printed page: 126
- Title/caption: Step 1.2 squared-deviation table for Class A (descriptive — no official caption)
- Labels: columns xi | xi−μ | (xi−μ)²; rows 50/−4.8/23.04, 52/−2.8/7.84, 55/0.2/.04, 57/2.2/4.84, 60/5.2/27.04
- Represents: Intermediate values for variance = 62.8/5 = 12.56.
- Educational importance: worked numerical method for variance (Class Activity PDF 131).
- Related: mean μ = 54.8, standard deviation 3.55
- Quality: clear

### C11-CS/Ch5/Vis5-2
- Unit 5 / 5.2.3 — Variance (Class B)
- Type: Table (calculation)
- PDF page: 130 · Printed page: 127
- Title/caption: squared-deviation table for Class B (descriptive)
- Labels: xi 30, 45, 55, 75, 90; xi−μ −29, −14, −4, 16, 31; (xi−μ)² 841, 196, 16, 256, 961
- Represents: Values for variance = 2270/5 = 454.
- Educational importance: same as above; compares spread of two classes.
- Related: σ ≈ 21.26
- Quality: clear

### C11-CS/Ch5/Tab5.2
- Unit 5 / 5.3.3.2 Data Transformation (illustrating 5.3.3.1 Data Cleaning)
- Type: Table (two small tables)
- PDF page: 134 · Printed page: 131
- Title/caption: Table 5.2: Graphical Representation of Data Cleaning for Student Grade Records (text refers to it as "Figure 5.2")
- Labels: "Original Data (with Errors)" and "Cleaned Data (After Data Cleaning)"; columns Name, Grade, Class, Section; rows Ali 85, Alie→Ali 90, Sara (blank→75), Class 10, Section A
- Represents: Before/after example of correcting a misspelt name and filling a missing grade.
- Educational importance: data-cleaning and missing-data concepts.
- Related: imputation, flagging, removal
- Quality: clear

### C11-CS/Ch5/Vis5-3
- Unit 5 / 5.4.1.2 Linear Regression — Step 1 Collecting Data
- Type: Table (data)
- PDF page: 136 (repeated PDF 137 ×2) · Printed page: 133–134
- Title/caption: Number of Customers vs Daily Earnings (in Rupees) (descriptive)
- Labels: Customers 10, 15, 20, 25, 30; Earnings 500, 700, 900, 1,100, 1,300
- Represents: Five-day dataset for the regression example (slope 40, intercept 100).
- Educational importance: data for the worked regression (Long Q2).
- Related: Y = β0 + β1x + ε
- Quality: clear (printed three times)

### C11-CS/Ch5/Tab5.1
- Unit 5 / 5.4.2.2 Logistic Regression
- Type: Table (data)
- PDF page: 139 · Printed page: 136
- Title/caption: Table 5.1: Study Hours vs. Exam Outcomes
- Labels: Hours Studied 1–6; Passed (1)/Failed (0): 0, 0, 0, 1, 1, 1
- Represents: Binary-outcome dataset for the logistic model.
- Educational importance: data for logistic regression example.
- Related: P(pass) formula, β0 = 1, β1 = 0.6
- Quality: clear

### C11-CS/Ch5/Vis5-4
- Unit 5 / 5.4.2.2 Logistic Regression — Creating the Logistic Function
- Type: Math figure (rendered equations)
- PDF page: 140 · Printed page: 137
- Title/caption: Logistic function equations (descriptive) — three displayed formulas
- Labels: P(pass) = 1 / (1 + e^−(β0 + β1 × Hours Studied)); P(pass) = 1 / (1 + e^−(1 + 0.6 × Hours Studied)); P(pass) = 1 / (1 + e^−(1 + 0.6×4)) ≈ 0.73 — printed with "|" where the fraction bar should be
- Represents: General and fitted logistic regression equations and a prediction.
- Educational importance: formula recall; computing a pass probability.
- Related: Table 5.1
- Quality: clear but fraction bars rendered as "|"

### C11-CS/Ch5/Vis5-5
- Unit 5 / 5.4.2.3 Introduction To Clustering Techniques
- Type: Table (data)
- PDF page: 141 · Printed page: 138
- Title/caption: Student Math/English scores for K-means (descriptive)
- Labels: Student | Math Score | English Score: Basim 85/70, Umer 90/65, Anie 50/80, Tallat 40/85, Maliha 60/60
- Represents: Five-student dataset clustered with K = 2.
- Educational importance: data for the K-means worked example (Long Q5–6).
- Related: Euclidean distance, centroids (87.5, 67.5) and (50, 75)
- Quality: clear

### C11-CS/Ch5/Vis5-6
- Unit 5 / Class Activity — Linear Regression
- Type: Table (activity data)
- PDF page: 144 · Printed page: 141
- Title/caption: Hours Studied vs Marks Obtained (descriptive)
- Labels: Hours 1–6; Marks 20, 25, 35, 40, 45, 50
- Represents: Practice dataset — plot, fit line, predict marks for 7 hours.
- Educational importance: graph/table-based numerical activity.
- Related: linear regression
- Quality: clear (header text slightly overlapped)

### C11-CS/Ch5/Vis5-7
- Unit 5 / Class Activity — Logistic Regression
- Type: Table (activity data)
- PDF page: 145 · Printed page: 142
- Title/caption: Midterm Marks vs Pass (1)/Fail (0) (descriptive)
- Labels: Midterm 30, 40, 50, 60, 70, 80, 90; Pass/Fail 0, 0, 0, 1, 1, 1, 1
- Represents: Practice dataset — predict probability of passing for a midterm score of 55.
- Educational importance: table-based activity.
- Related: logistic regression
- Quality: clear

### C11-CS/Ch5/Vis5-8
- Unit 5 / Class Activity — K-Means Clustering
- Type: Table (activity data)
- PDF page: 145 · Printed page: 142
- Title/caption: Customer monthly spending (descriptive)
- Labels: Customer 1–6; Groceries Spending ($) 150, 200, 100, 80, 160, 40; Clothing Spending ($) 100, 150, 50, 20, 90, 10
- Represents: Practice dataset for K = 2 clustering.
- Educational importance: table-based activity.
- Related: K-means steps
- Quality: clear

### C11-CS/Ch5/Fig5.4
- Unit 5 / 5.5.1.1 Bar Charts
- Type: Graph/chart (grouped bar chart)
- PDF page: 146 · Printed page: 143
- Title/caption: Figure 5.4: A bar chart showing sales figures of different products (chart title "Sales on Day 1 and Day 2 for various items")
- Labels: y-axis "Number of products sold" 0–1000; legend Day 1 (blue), Day 2 (yellow); four product groups (x labels not printed)
- Represents: Comparison of two days' sales per product category.
- Educational importance: when to use a bar chart (Short Q3, Long Q3).
- Related: Excel/Sheets charts
- Quality: clear; category labels missing

### C11-CS/Ch5/Fig5.5
- Unit 5 / 5.5.1.2 Line Graphs
- Type: Graph/chart (line)
- PDF page: 146 · Printed page: 143
- Title/caption: Figure 5.5: A line graph showing variation of temperature over time
- Labels: title "Temperature, °C"; x-axis times 10 am, 12 pm, 2 pm, 4 pm, 6 pm, 8 pm; y-axis −10 to 4 (approx.)
- Represents: Temperature trend over a day.
- Educational importance: trend-over-time chart type.
- Related: line graph use
- Quality: low-res raster, small

### C11-CS/Ch5/Fig5.6
- Unit 5 / 5.5.1.3 Histograms
- Type: Graph/chart (histogram)
- PDF page: 147 · Printed page: 144
- Title/caption: Figure 5.6: Example of a Histogram showing the distribution of exam scores (chart title "Maltis Test Results" — sic)
- Labels: x-axis "Test Scores" bins 50-55 … 96-100; y-axis "Frequency" 0–5
- Represents: Distribution of scores across bins.
- Educational importance: histogram vs bar chart distinction.
- Related: bins/intervals
- Quality: clear

### C11-CS/Ch5/Fig5.7
- Unit 5 / 5.5.1.4 Scatterplots
- Type: Graph/chart (scatter)
- PDF page: 147 · Printed page: 144
- Title/caption: Figure 5.7: Scatterplot showing the relationship between hours studied and exam scores
- Labels: x-axis "Hours" 0–10; y-axis 0–100; ≈9 points rising
- Represents: Positive relationship between study hours and scores.
- Educational importance: relationship between two variables; link to regression.
- Related: linear regression, correlation
- Quality: clear

### C11-CS/Ch5/Fig5.8
- Unit 5 / 5.5.1.5 Boxplots
- Type: Graph/chart (box-and-whisker)
- PDF page: 148 · Printed page: 145
- Title/caption: Figure 5.8: A Boxplot, showing class scores performance of three classes (chart title "Box Plot of Exam Scores for Three Classes")
- Labels: y-axis "Classes" Class 1, Class 2, Class 3; x-axis "Exam Scores" 50–100; median lines, whiskers, outlier points
- Represents: Median, quartiles and outliers of three classes' scores.
- Educational importance: reading a boxplot.
- Related: median, quartiles
- Quality: clear

---

## Unit 6 — Emerging Technologies

### C11-CS/Ch6/Fig6.1
- Unit 6 / 6.2.2 Types of Cloud Services
- Type: Labelled diagram (service wheel)
- PDF page: 157 · Printed page: 154
- Title/caption: Figure 6.1: Types of Cloud Services
- Labels: centre "Google Cloud Platform Services"; Compute Services, Management Tools, Networking, Cloud AI, Storage Services, IoT (Internet of Things), Big Data, Security and Identity Management
- Represents: Categories of services offered by one cloud platform (not the IaaS/PaaS/SaaS layers described in the text).
- Educational importance: examples of cloud service categories; weak match to section content.
- Related: IaaS/PaaS/SaaS
- Quality: clear (vendor graphic)

### C11-CS/Ch6/Fig6.2
- Unit 6 / 6.4.1 Fundamentals of Blockchain
- Type: Labelled diagram (network + chain)
- PDF page: 162 · Printed page: 159
- Title/caption: Figure 6.2: Example of Blockchain
- Labels: "Blockchain network" of interconnected Blockchain nodes; "Blockchain database": Block 0 → Block n-1 → Block n, each with Timestamp and Transaction
- Represents: P2P node network above a linked chain of blocks.
- Educational importance: exam diagram — nodes, blocks, linking (Long Q1 distributed ledger).
- Related: node, ledger, block, hash
- Quality: clear

### C11-CS/Ch6/Fig6.3
- Unit 6 / 6.5.1 Tracking the Origin of Products
- Type: Flowchart/cycle
- PDF page: 165 · Printed page: 162
- Title/caption: Figure 6.3: Tracking the origin of chocolate using blockchain
- Labels: Supplier → Manufacturer → Fabricator → Intermediary → Retailer → Customer (End User-Consumer), circular arrows
- Represents: Supply-chain stages whose transactions are recorded on the blockchain.
- Educational importance: supply-chain traceability use case (Short Q6).
- Related: immutability, transparency
- Quality: clear

### C11-CS/Ch6/Fig6.4
- Unit 6 / 6.5.2 Blockchain in Financial Services
- Type: Labelled diagram (identity-attestation flow)
- PDF page: 166 · Printed page: 163
- Title/caption: Figure 6.4: Blockchain in banking for faster and safer transactions
- Labels: Identity Issuer(s), User (ID APP), Identity Verifier(s), Identity Hub; "Request and receive attestations", "Present and verify attestations", "Register identity", "Lookup identity", "Store encrypted attestations"
- Represents: Decentralised digital-identity flow between issuer, user and verifier.
- Educational importance: illustrates secure verification (links to BISE certificate Class Activity).
- Related: digital signature, decentralization
- Quality: clear; small text

### C11-CS/Ch6/Fig6.5
- Unit 6 / 6.5.3 Data Security in Blockchain
- Type: Labelled diagram (encryption flow)
- PDF page: 167 · Printed page: 164
- Title/caption: Figure 6.5: Cryptography keeps data secure in blockchain
- Labels: Plain Text → Encryption → Cipher Text → Decryption → Plain Text; Secret key arrows
- Represents: Symmetric encryption/decryption with a secret key.
- Educational importance: encryption concept in the secure-letter analogy.
- Related: digital signatures, data security
- Quality: clear

---

## Units 7, 8, 9
No figures, tables, graphs or code listings (text and boxed activities only). Decorative elements (unit banners, Did-You-Know, Tidbits, Class Activity boxes) not indexed.

## Back matter
### C11-CS/Back/Vis-Answers
- Answers page
- Type: Table (answer key, image)
- PDF page: 226 · Printed page: 223
- Title/caption: "ANSWER" (page heading)
- Labels: nine small tables "Unit 1" … "Unit 9", columns question number | letter; Unit 3 has 5 rows, Unit 9 has 14 rows, others 10
- Represents: MCQ answer key for all units.
- Educational importance: self-check for MCQs (counts mismatch Units 3, 5, 6, 9 — see book index).
- Quality: clear; not in text layer
