# BOOK RECORD — C12-CS

| Class | Subject | Book title (as printed) | Filename | Board/authority | Publisher/printer | Edition / date | Curriculum | Language | File type & text layer | Total PDF pages | Printed page numbering (rule + range) | Total chapters | Watermarks/stamps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 12 | Computer Science | Computer Science and Entrepreneurship (cover: "Computer Science and Entrepreneurship 12"; model paper: "Computer Science and Entrepreneurship Intermediate part-II") | 12 Class Data/12th Class Computer.pdf | Punjab Education, Curriculum, Training and Assessment Authority (PECTAA), Lahore | Published by Tips Academy; printed by Ishaq Al-Fateh Printers, Lahore | 1st edition, 1st impression, July 2026, 3500 copies, Rs 134.00, "Experimental Edition" | Revised National Curriculum of Pakistan 2023 | English | Scanned PDF (HP flatbed scan of printed book), no native text; OCR layer education_knowledge/source_text/C12-CS.ocr.txt (code/formulas garbled) | 147 | PDF 6–25 = printed 1–20 (pdf = printed + 5); PDF 26–145 = printed 22–141 (pdf = printed + 4, because printed p.21 is missing); PDF 146 = duplicate of printed 141; PDF 147 = back cover. Printed range 1–141 | 9 (+ Pairing Scheme + Model Paper) | Security sticker/QR notice (PDF 1–2); printer signature strips ("Sig1 SideA Process Black … Computer 12 … Ishaq") on page margins; no watermark |

Credits (PDF 4): Authors Dr. Abdul Sattar (Asst. Prof. CS, Lahore Garrison University) and Mr. Zulfiqar Ali Kullachi (Headmaster, Govt. High School Kot Haibat, D.G. Khan); Editor Prof. Saqib Ubaid (Institute of CS, KFUEIT Rahim Yar Khan); External Review Committee: Muhammad Faheem, M. Zeeshan Shabbir, Mahvish Ponum, Kashif Shahzad Ch, Muhammad Asif Majeed Khan, Mehmood Ahmad; Supervision Jahanzaib Khan (Director Curriculum & Compliance); Director Aamir Riaz; Deputy Director Syed Saghir-ul-Hassnain Tirmizi; Incharge Art Cell Mst. Aisha Saidq; Layout Minal Tariq; Illustrations Aiyatullah.

## Completeness check
- First pages present: PDF 1 outer cover (PECTAA, academic year 2026-2027, security sticker/QR), PDF 2 Quaid-e-Azam quote + security-sticker instructions, PDF 3 inner title, PDF 4 credits, PDF 5 copyright note + Table of Contents.
- TOC present (PDF 5). Chapter sequence matches TOC; TOC misprints Ch 1 as "Computer Neworks".
- MISSING PAGE: printed page 21 (Chapter 2) is absent. PDF 25 = printed 20 (chapter opener, ends mid-section 2.1), PDF 26 = printed 22 (begins mid-sentence "…correct order. This prevents errors…"). Lost content: end of 2.1, the whole of heading 2.2 (title UNVERIFIED — context and the chapter summary/long Q2 suggest problem-solving steps / decomposition), Figure 2.1 (never appears), and probably one activity/box.
- DUPLICATED PAGE: printed page 141 (model paper, last page) is scanned twice — PDF 145 and PDF 146 are identical.
- PDF 147 = back cover (Qaumi Tarana / national anthem in Urdu + PECTAA logo), not a content page.
- No blank or out-of-order pages otherwise. Every chapter has Summary, Exercise (MCQ, Short, Long) and an Answer Key.
- Scan quality: flatbed scan of a bound book — pages slightly skewed, variable page sizes, dark gutter/edge strips, printer colour bars on some pages; print is legible at ≥110 dpi. OCR is poor on code listings, formulas, tables and some left-margin text (first 2–4 characters of many lines lost on verso pages, e.g. PDF 9, 11, 17, 19, 21, 30). Use page images for code/formulas.

## Table of Contents (as printed) — with actual ranges
| Ch | Title (as printed in TOC) | Printed start (TOC) | Printed actual | PDF start | PDF end |
|---|---|---|---|---|---|
| 1 | Computer Neworks [sic; chapter page reads "Computer Networks"] | 1 | 1 | 6 | 24 |
| 2 | Computational Thinking & Algorithms | 20 | 20 | 25 | 36 |
| 3 | Object Oriented Programming Using Python | 33 | 33 | 37 | 48 |
| 4 | Development of Graphical User Interface (GUI) | 45 | 45 | 49 | 63 |
| 5 | Code Testing and Debugging | 60 | 60 | 64 | 75 |
| 6 | Data and Analysis | 72 | 72 | 76 | 92 |
| 7 | Hypothesis Testing | 89 | 89 | 93 | 106 |
| 8 | Applications of Computer Science | 103 | 103 | 107 | 121 |
| 9 | Cybersecurity and Safe Digital Collaboration | 118 | 118 | 122 | 140 |
| — | Pairing Scheme | 137 | 137 | 141 | 142 |
| — | Model Paper | 139 | 139 | 143 | 145 (146 duplicate) |

TOC/actual mismatches: none in page numbers; only the "Neworks" misprint. Chapter 2 actual printed range is 20–32 but printed p.21 is missing from the scan.

## CHAPTER INDEX

### Chapter 1 — Computer Networks
- Pages: printed 1–19 · PDF 6–24
- SLOs (printed, 3 bullets, no codes): explain network architecture, fundamental concepts, diagnostic tools/commands; set up and configure home networks, troubleshoot, differentiate connection types; understand/measure bandwidth and latency, appreciate load balancing, security, backup and recovery.
- Main concept: How devices are connected and communicate — network types, devices, topologies, the OSI layered model, core protocols (TCP/IP, HTTP/HTTPS, FTP, DNS), IP addressing/subnetting/NAT, home Wi-Fi setup and security, diagnostic commands, and performance/security/backup concerns.
- Navigation tree:
  - Introduction (unnumbered) — PDF 6
  - 1.1 Introduction to Computer Networks — PDF 6 (Uses of Computer Network, PDF 7)
  - 1.2 Network Architecture and Basic Concepts — PDF 7 (packets, Fig 1.2)
  - 1.3 Types of Computer Networks — PDF 8 (LAN, WAN, The Internet (Public WAN))
  - 1.4 Networking Devices — PDF 9 (Network Interface Card (NIC), Switch, Router, Modem, Wireless access point)
  - 1.5 Network Topologies — PDF 10 (Bus, Star — PDF 10; Ring, Mesh, Tree — PDF 11; Advantages and Disadvantages of Network Topologies — PDF 11–12, Table 1.1)
  - 1.6 Network Models and Layers — PDF 12 (Network Layers; OSI Model (Open Systems Interconnection) — PDF 13; Functions of OSI Model Layers — numbered list 1–7 Physical…Application, PDF 13–14)
  - 1.7 Network Protocols and Services — PDF 14 (TCP/IP, HTTP (+HTTPS, SSL/TLS), FTP, DNS — PDF 14–15)
  - 1.8 IP Addressing and Subnetting — PDF 15 (IPv4 and IPv6 with breakdown tables, PDF 15–16; Subnetting; Network Address Translation (NAT) — PDF 16)
  - 1.9 Home Network Setup and Configuration — PDF 16 (Components of a Home Network, Wired Network Connections, Wireless Network Connections — PDF 17)
  - 1.10 Wi-Fi Security and Router Configuration — PDF 17 (Router Web Interface: 1. Router Configuration, 2. Wi-Fi Encryption (WPA2/WPA3/WEP), 3. Default Gateway; Guest Networks)
  - 1.11 Network Diagnostic Tools and Commands — PDF 17 (troubleshooting; Ping Command — PDF 18; Ipconfig and ifconfig Commands; Telnet, PuTTY, and Secure Shell (SSH) — PDF 18)
  - 1.12 Network Performance — PDF 19 (Network Bandwidth (Mbps), Network Latency (ms), Causes of Network Delay)
  - 1.13 Network Load Balancing — PDF 19 (Benefits; Basic Load Balancing Methods: Round Robin, Least Connection, IP Hash)
  - 1.14 Network Security — PDF 19–20 (Firewalls, Encryption, Access Control, Common Network Security Threats — PDF 20)
  - 1.15 Data Backup and Recovery — PDF 20 (Types of Data Backup: full/incremental/differential; Data Recovery Methods — PDF 21)
  - 1.16 Usability and Security Tradeoffs — PDF 21 (Tradeoffs Between Usability and Security)
  - Summary — PDF 22; Exercise — PDF 23–24
- Key terms: computer network, network architecture, packet, LAN, WAN, Internet (public WAN), NIC, MAC address, switch, router, modem, DSL, ISP, wireless access point, topology (physical/logical; bus, star, ring, mesh, tree), terminator, hub, backbone, OSI model, physical/data link/network/transport/session/presentation/application layer, protocol, TCP/IP, HTTP, HTTPS, SSL/TLS, FTP, DNS, IP address, IPv4 (32-bit), IPv6 (128-bit), subnet, subnetting, NAT, home network, Ethernet, Wi-Fi, router web interface, Wi-Fi encryption (WEP, WPA2, WPA3), default gateway, guest network, ping, ICMP echo, ipconfig/ifconfig, Telnet, PuTTY, SSH, bandwidth, latency, load balancing (Round Robin, Least Connection, IP Hash), firewall, encryption, access control, virus/malware, phishing, Denial of Service, backup (full, incremental, differential), recovery, usability.
- Laws/rules/principles: OSI seven-layer model (PDF 13–14); IPv4 = 4 numbers 0–255, 1 byte each, 32 bits total; IPv6 = 8 groups of 4 hex digits, 16 bits each, 128 bits (PDF 15–16); total IPv4 addresses ≈ 4.29 billion; IPv6 ≈ 2^128 ≈ 3.4×10^38 (PDF 16).
- Formulas: none beyond the address-size arithmetic above. Example CIDR: 192.168.1.0/24 split into 192.168.1.0/25 and 192.168.1.128/25 (PDF 16).
- Named processes/comparisons: packet transmission & reassembly (PDF 7–8); LAN vs WAN vs Internet (PDF 8); topology advantages/disadvantages (Table 1.1, PDF 12); DNS name resolution (PDF 14–15); wired vs wireless connections (PDF 17); ping output reading (PDF 18); load-balancing methods (PDF 19); backup types (PDF 21); usability vs security trade-off (PDF 21).
- Worked examples: 1 command demonstration — "ping google.com" with sample output (PDF 18); IPv4/IPv6 breakdown examples 192.168.1.10 and 2001:0db8:85a3:0000:0000:8a2e:0370:7334 (PDF 15–16).
- In-text features: TIDBIT ×4 (PDF 7, 9, 12, 13); DO YOU KNOW? ×6 (PDF 8, 12, 14, 15 ×2, 16); CLASS ACTIVITY ×8 (PDF 7, 9 ×2, 11, 17, 18, 19 ×2).
- VISUALS IN THIS CHAPTER:
  | Visual ID | Type | PDF p | Printed p | Caption/identifier |
  |---|---|---|---|---|
  | C12-CS/Ch1/Fig1.1 | Illustration | 6 | 1 | A computer network connects multiple devices to share data and resources |
  | C12-CS/Ch1/Fig1.2 | Diagram | 7 | 2 | Network architecture shows how devices and components are organized in a network |
  | C12-CS/Ch1/Fig1.3 | Illustration | 8 | 3 | Local Area Network |
  | C12-CS/Ch1/Fig1.4 | Illustration | 8 | 3 | Wide Area Network |
  | C12-CS/Ch1/Fig1.5 | Illustration | 8 | 3 | Internet |
  | C12-CS/Ch1/Fig1.6 | Photo | 9 | 4 | Network Interface Card |
  | C12-CS/Ch1/Fig1.7 | Illustration | 10 | 5 | Wireless Access Point |
  | C12-CS/Ch1/Fig1.8 | Labelled diagram | 10 | 5 | Bus Topology |
  | C12-CS/Ch1/Fig1.9 | Labelled diagram | 10 | 5 | Star Topology |
  | C12-CS/Ch1/Fig1.10 | Labelled diagram | 11 | 6 | Ring Topology |
  | C12-CS/Ch1/Fig1.11 | Labelled diagram | 11 | 6 | Mesh Topology |
  | C12-CS/Ch1/Fig1.12 | Labelled diagram | 11 | 6 | Tree Topology |
  | C12-CS/Ch1/Tab1.1 | Table | 12 | 7 | Advantages & Disadvantages of Network Topologies |
  | C12-CS/Ch1/Fig1.13 | Labelled diagram | 13 | 8 | OSI Model on the Sender Side Showing Data Flow from the Application Layer to the Physical Layer |
  | C12-CS/Ch1/Fig1.14 | Flow diagram | 15 | 10 | DNS Name Resolution Process |
  | C12-CS/Ch1/Vis1-1 | Table (un-numbered) | 15 | 10 | Breakdown of IPv4 (Part / Value / What it means) |
  | C12-CS/Ch1/Vis1-2 | Table (un-numbered) | 16 | 11 | Breakdown of IPv6 (Part / Value / What it means) |
  | C12-CS/Ch1/Fig1.15 | Labelled diagram | 16 | 11 | Subnetting Example |
  | C12-CS/Ch1/Vis1-3 | Code/terminal listing | 18 | 13 | Ping Command: ping google.com + Sample Output |
  | C12-CS/Ch1/Fig1.16 | Labelled diagram | 18 | 13 | Ping Command |
  | C12-CS/Ch1/Fig1.17 | Illustration | 20 | 15 | Firewall Protection |
- ASSESSMENT (Exercise, PDF 23–24): Multiple Choice Questions ×10 (PDF 23); Short Questions ×10 (PDF 24); Long Questions ×8 (PDF 24). No diagram-based questions (Long Q3/Q4 on OSI layers and topologies benefit from Fig 1.13 / Table 1.1).
- Answer availability: MCQ Answer Key printed (PDF 24): 1 B, 2 C, 3 C, 4 C, 5 C, 6 D, 7 C, 8 C, 9 C, 10 D — all verified consistent with the options.
- Cross-chapter links: firewalls/encryption/access control → Ch 9 (9.2 security tools, cryptography); network diagnostics → Ch 5 debugging mindset; cloud/IoT connectivity → Ch 8.
- Issues: Fig 1.9 caption OCR'd as "Figure I Star Topology" but printed "Figure 1.9: Star Topology" (PDF 10). Printed page 9 footer shows "9" at an odd position (PDF 15 top), cosmetic only.

### Chapter 2 — Computational Thinking & Algorithms
- Pages: printed 20–32 (printed 21 MISSING) · PDF 25–36
- SLOs (printed, 2 bullets): apply problem solving by identifying, decomposing and creating solutions using computational thinking, evaluate and refine solutions; understand computational artifacts/algorithms, primitive structures (lists, stacks, queues, trees, graphs), use knowledge representation and reasoning with propositional and predicate logic.
- Main concept: Computational thinking as a structured way to decompose and solve problems, then logic as a knowledge-representation framework — propositions, connectives, truth tables, equivalence, satisfiability, predicate logic with quantifiers, and logical inference/deduction.
- Navigation tree:
  - Introduction (unnumbered) — PDF 25
  - 2.1 Introduction to Computational Thinking — PDF 25 (Computational Thinking)
  - [2.2 — on missing printed p.21; title UNVERIFIED. Text resumes PDF 26 mid-sentence about following steps in the correct order; Figure 2.1 also lost]
  - (unnumbered) Evaluating and Improving Solutions — PDF 26
  - 2.3 Logic as a Knowledge Representation Framework — PDF 26 (Logic in Computer Science; Role of Logic in Reasoning and Decision Making)
  - 2.4 Propositional Logic — PDF 27 (Proposition; Simple and Compound Propositions; Logical connectives: AND, OR, NOT — PDF 28)
  - 2.5 Truth Tables — PDF 28 (Purpose of Truth Tables; Creating Truth Tables for Logical Expressions; Truth Values of Propositions (2^n rows) — PDF 29)
  - 2.6 Propositional Equivalence — PDF 29 (Identifying Equivalent Logical Expressions; Importance of Equivalence in Logic — PDF 30)
  - 2.7 Propositional Satisfiability — PDF 30 (Conditions for a Proposition to be Satisfiable; Examples of Satisfiable and Unsatisfiable Expressions)
  - 2.8 Predicate Logic — PDF 31 (Introduction to Predicate Logic; Difference Between Propositional and Predicate Logic; Predicates and Variables)
  - 2.9 Quantifiers in Predicate Logic — PDF 31 (Universal Quantifier (for all) ∀; Existential Quantifier (there exists) ∃; Using Quantifiers in Logical Statements — PDF 32)
  - 2.10 Applying Predicate Logic to Real-World Problems — PDF 32 (Representing Relationships Using Predicates — library example Borrows(x,y), Teaches(t,s); Writing Logical Statements With Quantifiers — PDF 33; Reasoning and drawing conclusions)
  - 2.11 Logic-Based Reasoning and Inference — PDF 33 (Logical Inference; Deduction Using Logical Rules)
  - Summary — PDF 34; Exercise — PDF 35–36
- Key terms: computational thinking, decomposition, pattern, abstraction (removing unnecessary detail), algorithm, evaluation, logic, knowledge representation, proposition, simple/compound proposition, logical connectives AND/OR/NOT, truth value, truth table, propositional equivalence (≡), satisfiable/unsatisfiable, predicate, variable, domain of discourse, quantifier, universal quantifier ∀, existential quantifier ∃, inference, premise, deduction, if-then rule.
- Laws/rules/principles: a proposition is either true or false, never both (PDF 27); truth table has 2^n rows for n propositions (PDF 29); two expressions are equivalent if their truth values agree in all cases (PDF 29); satisfiable = at least one true assignment, "P AND NOT P" unsatisfiable (PDF 30); deduction: premises true ⇒ conclusion true (PDF 33).
- Formulas/notation: P = "The sky is blue" (PDF 27); (A AND NOT B) OR (B AND NOT A) ≡ (A OR B) AND (NOT A OR NOT B) (XOR equivalence, PDF 29); ∀x, x > 0; ∃x, x is even; ∀x ∃y, y > x (PDF 32); ∀x, Student(x) → Borrows(x, Book); ∃y, Book(y) ∧ Available(y); ∀x, Student(x) → HasLibraryCard(x) (PDF 33).
- Named processes/examples: tea-making step-by-step algorithm (Fig 2.2); pizza/burger/soda satisfiability example (PDF 30); library-system modelling with predicates (PDF 32–33); Socrates syllogism and rain/wet-ground deduction (PDF 33).
- Worked examples: equivalence truth-table (PDF 29), satisfiable/unsatisfiable statements (PDF 30), quantified library rules (PDF 33) — 3 informal examples, un-numbered.
- In-text features: TIDBIT ×4 (PDF 25, 26, 29, 32); DO YOU KNOW? ×3 (PDF 27, 30, 32); CLASS ACTIVITY ×3 (PDF 27, 30, 33). (Any on the missing page unknown.)
- VISUALS IN THIS CHAPTER:
  | Visual ID | Type | PDF p | Printed p | Caption/identifier |
  |---|---|---|---|---|
  | C12-CS/Ch2/Fig2.1 | — | — | 21 (missing) | NOT PRESENT in scan (page lost) |
  | C12-CS/Ch2/Fig2.2 | Flowchart | 26 | 22 | Step by Step Algorithm Example |
  | C12-CS/Ch2/Fig2.3 | Diagram | 27 | 23 | Propositional Logic Statements |
  | C12-CS/Ch2/Fig2.4 | Venn diagrams | 28 | 24 | Logical Connectives |
  | C12-CS/Ch2/Fig2.5 | Truth table | 28 | 24 | Truth Table for Logical Expressions |
  | C12-CS/Ch2/Fig2.6 | Venn + truth table box | 29 | 25 | Equivalence of two propositional expressions (referenced as Figure 2.6 in text; caption line not printed on the box) |
  | C12-CS/Ch2/Fig2.7 | Tree diagram | 31 | 27 | Predicate Logic Structure |
  | C12-CS/Ch2/Vis2-1 | Comparison box | 31 | 27 | Propositional Logic vs Predicate Logic ("Ali is Tall" vs Tall(Ali)) (descriptive — no official caption) |
  | C12-CS/Ch2/Fig2.8 | Diagram | 32 | 28 | Universal and Existential Quantifier |
- ASSESSMENT (Exercise, PDF 35–36): Multiple Choice Questions ×10 (PDF 35; Q6 and Q9 use logic symbols (P), (Q), (P∧Q), ∃, →, ∧, ∀ — symbol-based); Short Questions ×10 (PDF 35–36); Long Questions ×8 (PDF 36). Long Q5 asks to create truth tables (table-based answer).
- Answer availability: MCQ Answer Key (PDF 36): 1 B, 2 C, 3 B, 4 C, 5 C, 6 C, 7 C, 8 C, 9 D, 10 B — verified.
- Cross-chapter links: logic/if-then → conditional logic in Python code (Ch 3–5); decomposition → unit testing of small functions (Ch 5); predicate statements → hypothesis formulation (Ch 7).
- Issues: printed page 21 missing (heading 2.2, Figure 2.1, part of 2.1 lost) — PDF 25/26 boundary. OCR of Fig 2.5 caption reads "Figure 15" (should be 2.5). Short Q1–5 on PDF 35, Q6–10 on PDF 36.

### Chapter 3 — Object Oriented Programming Using Python
- Pages: printed 33–44 · PDF 37–48
- SLOs (printed, 1 bullet): develop Python applications using OOP principles.
- Main concept: Modelling real-world entities with classes and objects in Python, and applying encapsulation (public/protected/private naming), inheritance (single, multiple, multilevel) and polymorphism (overloading via default/*args, overriding at runtime) to write modular, reusable code.
- Navigation tree:
  - Introduction (unnumbered) — PDF 37
  - 3.1 Object-Oriented Programming (OOP) Using Python — PDF 37 (Benefits of OOP: Modularity, Reusability, and Easier Maintenance)
  - 3.2 Core Concepts of OOP — PDF 37
    - (unnumbered) Classes and Objects — Representing Real-World Entities in Code — PDF 38 (Student class example)
    - (unnumbered) Encapsulation — PDF 39 (Why Encapsulation is important; bank-account analogy; 1. Levels of Access Control: Public, Protected (_name), Private (__name, name mangling); BankAccount example — PDF 40)
    - (unnumbered) Inheritance — Reusing and Extending Functionality — PDF 40 (Single Inheritance; Animal/Dog example — PDF 41; Parent Class, Child Class, Method Overriding, super(); Multiple Inheritance — PDF 41, Father/Mother/Child example — PDF 42; Multilevel Inheritance — PDF 42, Vehicle/Car/ElectricCar example — PDF 42–43)
    - (unnumbered) Polymorphism — PDF 43 (payment-system example; Types of Polymorphism; 1. Compile-time Polymorphism — PDF 44, Calculator.multiply example; 2. Runtime Polymorphism (Overriding) — PDF 44, Animal/Dog/Cat sound example — PDF 44–45)
  - Summary — PDF 46; Exercise — PDF 47–48
- Key terms: OOP, class, object, instance, attribute, method, blueprint, modularity, reusability, maintainability, __init__, self, encapsulation, public/protected/private members, name mangling, getter/setter, inheritance, superclass/parent/base class, subclass/child/derived class, method overriding, super(), single/multiple/multilevel inheritance, polymorphism, compile-time polymorphism, method overloading, default arguments, *args/**kwargs, runtime polymorphism.
- Laws/rules/principles: Python has no strict private keyword — naming conventions (_ protected, __ private) (PDF 39); Python does not support true signature-based method overloading (PDF 44); child class syntax class Child(Parent): (PDF 41).
- Formulas: none.
- Named examples/comparisons: procedural vs OOP (activity, PDF 37); Java/C++ vs Python access control (PDF 39); compile-time vs runtime polymorphism (PDF 44).
- Worked examples (code listings): 7 — Student (PDF 38), BankAccount (PDF 40), Animal/Dog (PDF 41), Father/Mother/Child (PDF 42), Vehicle/Car/ElectricCar (PDF 42–43), Calculator multiply with output 1, 4, 6, 24 (PDF 44), Animal/Dog/Cat sound with output Bark/Meow/Some generic sound (PDF 44–45).
- In-text features: TIDBIT ×3 (PDF 37, 39, 41); DO YOU KNOW? ×1 (PDF 38); CLASS ACTIVITY ×2 (PDF 37, 43).
- VISUALS IN THIS CHAPTER:
  | Visual ID | Type | PDF p | Printed p | Caption/identifier |
  |---|---|---|---|---|
  | C12-CS/Ch3/Fig3.1 | Labelled diagram | 38 | 34 | Diagram Showing Class and Object relationship |
  | C12-CS/Ch3/Vis3-1 | Code listing | 38 | 34 | class Student example (descriptive) |
  | C12-CS/Ch3/Fig3.2 | Labelled diagram | 39 | 35 | Encapsulation diagram showing private and public variables |
  | C12-CS/Ch3/Vis3-2 | Code listing | 40 | 36 | class BankAccount (private __balance, deposit, withdraw, get_balance) |
  | C12-CS/Ch3/Fig3.3 | Diagram | 40 | 36 | Single Inheritance |
  | C12-CS/Ch3/Vis3-3 | Code listing | 41 | 37 | class Animal / class Dog(Animal) |
  | C12-CS/Ch3/Fig3.4 | Diagram | 41 | 37 | Multiple Inheritance |
  | C12-CS/Ch3/Vis3-4 | Code listing | 42 | 38 | class Father, Mother, Child(Father, Mother) |
  | C12-CS/Ch3/Fig3.5 | Diagram | 42 | 38 | Multilevel Inheritance |
  | C12-CS/Ch3/Vis3-5 | Code listing | 42–43 | 38–39 | class Vehicle / Car(Vehicle) / ElectricCar(Car) |
  | C12-CS/Ch3/Fig3.6 | Tree diagram | 43 | 39 | Polymorphism example showing the same function behaving differently |
  | C12-CS/Ch3/Vis3-6 | Code listing + output | 44 | 40 | class Calculator multiply(self, a=1, b=1, *args) |
  | C12-CS/Ch3/Vis3-7 | Code listing + output | 44–45 | 40–41 | Animal/Dog/Cat sound() runtime polymorphism |
- ASSESSMENT (Exercise, PDF 47–48): Multiple Choice Questions ×10 (PDF 47–48); Short Questions ×10 (PDF 48); Long Questions ×8 (PDF 48). No diagram-based questions.
- Answer availability: MCQ Answer Key (PDF 48): 1 C, 2 B, 3 A, 4 A, 5 A, 6 B, 7 B, 8 B, 9 A, 10 B — verified.
- Cross-chapter links: Tkinter widgets/objects and sqlite3 connection objects (Ch 4); unit-testing of methods (Ch 5); sklearn model objects (Ch 6). Model paper Q6 asks for a multilevel-inheritance program (Grandfather/Father/Son).
- Issues: OCR garbles all code; use images. Fig 3.3 caption clipped to "Single Inheritanc" in OCR (printed "Single Inheritance").

### Chapter 4 — Development of Graphical User Interface (GUI)
- Pages: printed 45–59 · PDF 49–63
- SLOs (printed, 2 bullets): design interactive GUI-based programs using Tkinter; connect Python applications to databases and perform CRUD operations.
- Main concept: Building desktop interfaces with Tkinter (windows, frames, widgets, pack/grid/place layout, event-driven programming, a login form) and then persisting data by connecting Python to SQLite/MySQL, understanding relational tables/keys and performing CRUD with SQL.
- Navigation tree:
  - Introduction (unnumbered) — PDF 49
  - 4.1 Graphical User Interface (GUI) Development with Tkinter — PDF 49
    - What is a GUI? Why is it important? — PDF 50; Overview of Tkinter as Python's built-in GUI toolkit — PDF 50 (Simple GUI Example code + output)
    - Tkinter Components and Widgets — PDF 51; Creating Windows and Adding Frames — PDF 51 (Tkinter Frames Example code, PDF 51–52)
    - Common Widgets: Labels, Buttons, Entry Fields, Menus, and List boxes — PDF 52
    - Layout Management — PDF 52; Organizing Elements using pack(), grid(), and place() — PDF 52 (examples pack() PDF 53, grid() PDF 53–54, place() PDF 54); Designing Clean and Responsive Interfaces — PDF 54
    - Event Handling and Interactivity — PDF 55; Understanding Event-Driven Programming; Handling User Input and Connecting Widgets to Functions; Example: Simple Login Form (code PDF 55–56, messagebox)
  - 4.2 Working with Databases in Python — PDF 56
    - Introduction to Databases — PDF 56 (Entity, Attribute, Relationship, Identifier — PDF 57); Understanding Databases — PDF 57 (Relational Database, Table, Column, Primary Key, Foreign Key; Fig 4.3)
    - Overview of Relational Databases and SQL Structure — PDF 58; Connecting Python to a Database; Using sqlite3 or MySQL to Establish a Database Connection (school.db code, PDF 58–59)
    - Executing SQL Commands From Python — PDF 59; CRUD Operations — PDF 59 (Fig 4.4, Table 4.1); Create: Adding New Records — PDF 59; Read: Retrieving and Displaying Data — PDF 60; Update: Modifying Existing Records; Delete: Removing Data Safely (DELETE example code, PDF 60)
  - Summary — PDF 61; Exercise — PDF 62–63
- Key terms: GUI, Tkinter, Tk(), window, title(), geometry(), frame, widget, Label, Button, Entry, Menu, Listbox, pack(), grid() (row, column, columnspan), place() (x, y), padx/pady, grid_columnconfigure, mainloop(), event, event-driven programming, command=, messagebox (showinfo, showerror), show="*", database, entity, attribute, relationship, identifier, relational database, table, record/tuple, field, column, primary key, foreign key, SQL, sqlite3, MySQL, connect(), cursor, execute(), fetchall(), commit(), close(), CRUD, INSERT, SELECT, UPDATE, DELETE, CREATE TABLE IF NOT EXISTS.
- Laws/rules/principles: event-driven model — program idles until an event fires its bound function (PDF 55); without commit() changes are not permanent (PDF 60).
- Formulas: SQL templates — INSERT INTO students (ID, Name, Age) VALUES (1, 'John', 20); SELECT * FROM students; UPDATE students SET Age = 21 WHERE ID = 1; DELETE FROM students WHERE ID = 1 (Table 4.1, PDF 59).
- Named processes: GUI build sequence Tk → widgets → pack → mainloop (PDF 50); database workflow connect → cursor → execute → fetch → close (PDF 59); CRUD cycle (PDF 59–60).
- Worked examples (code + screenshot): 8 — Simple GUI Example (PDF 50), Frames Example (PDF 51–52), pack() (PDF 53), grid() (PDF 53–54), place() (PDF 54), Login Form (PDF 55–56), sqlite3 school.db create/insert/select (PDF 58), sqlite3 DELETE (PDF 60).
- In-text features: TIDBIT ×1 (PDF 52); DO YOU KNOW? ×1 (PDF 56); CLASS ACTIVITY ×3 (PDF 51, 56, 60).
- VISUALS IN THIS CHAPTER:
  | Visual ID | Type | PDF p | Printed p | Caption/identifier |
  |---|---|---|---|---|
  | C12-CS/Ch4/Fig4.1 | GUI mock-up | 49 | 45 | Graphical User Interface (GUI) |
  | C12-CS/Ch4/Vis4-1 | Code listing + GUI screenshot | 50 | 46 | Simple GUI Example (Welcome to Tkinter / Click Me) |
  | C12-CS/Ch4/Vis4-2 | Code listing + GUI screenshot | 51–52 | 47–48 | Tkinter Frames Example (Top Frame / Bottom Frame) |
  | C12-CS/Ch4/Fig4.2 | GUI screenshots | 52 | 48 | Diagram showing Tkinter Layout Managers: pack(), grid(), place() |
  | C12-CS/Ch4/Vis4-3 | Code listing + GUI screenshot | 53 | 49 | Example pack() |
  | C12-CS/Ch4/Vis4-4 | Code listing + GUI screenshot | 53–54 | 49–50 | Example grid() |
  | C12-CS/Ch4/Vis4-5 | Code listing + GUI screenshot | 54 | 50 | Example place() |
  | C12-CS/Ch4/Vis4-6 | Code listing + GUI screenshot | 55–56 | 51–52 | Simple Login Form (Login Form window + Success messagebox) |
  | C12-CS/Ch4/Fig4.3 | Labelled table diagram | 57 | 53 | Tables, Columns, Records, Fields, Primary Key, and Foreign Key Relationship |
  | C12-CS/Ch4/Vis4-7 | Code listing | 58 | 54 | sqlite3 school.db: CREATE TABLE students, INSERT, SELECT, fetchall |
  | C12-CS/Ch4/Fig4.4 | Labelled diagram | 59 | 55 | Diagram showing Create, Read, Update, and Delete operations on a table |
  | C12-CS/Ch4/Tab4.1 | Table | 59 | 55 | CRUD operations |
  | C12-CS/Ch4/Vis4-8 | Code listing | 60 | 56 | sqlite3 DELETE FROM students WHERE ID = 1 |
- ASSESSMENT (Exercise, PDF 62–63): Multiple Choice Questions ×10 (PDF 62–63); Short Questions ×10 (PDF 63); Long Questions ×8 (PDF 63). No diagram-based questions.
- Answer availability: MCQ Answer Key (PDF 63): 1 A, 2 B, 3 B, 4 A, 5 D, 6 B, 7 C, 8 C, 9 C, 10 A — verified.
- Cross-chapter links: classes/objects (Ch 3) underlie widgets; sqlite3 reused in Ch 5 exception-handling example (PDF 68–69); model paper Q3 items on Entry.delete, mainloop(), Tk() root, missing table error.
- Issues: Fig 4.3 caption OCR'd as "Figure 43"; Fig 4.1 OCR "GUL" (printed "GUI"). Code listings garbled in OCR (e.g. "tk,Tk()", "mainloo") — read from images.

### Chapter 5 — Code Testing and Debugging
- Pages: printed 60–71 · PDF 64–75
- SLOs (printed, 1 bullet): use advanced techniques such as unit tests, breakpoints, and watches for testing and debugging Python applications.
- Main concept: Ensuring program correctness through testing (error types, unit tests with unittest/pytest), debugging in IDEs (breakpoints, watch expressions, step into/over/continue), handling exceptions with try/except/finally (incl. database rollback), and finding performance bottlenecks with cProfile/timeit.
- Navigation tree:
  - 5.1 Introduction — PDF 64
  - 5.2 Testing and Debugging Techniques — PDF 64
    - 5.2.1 Importance of Testing and Debugging — PDF 64 (Why testing is essential for reliable applications; Common types of programming errors and bugs — syntax, logic, runtime, data errors, resource leaks; Fig 5.1 PDF 65)
    - (unnumbered) Unit Testing — PDF 65 (Introduction to Python's unittest and pytest modules; Writing and executing test cases; add/multiply + pytest example PDF 65–66)
    - (unnumbered) Using Breakpoints and Watches — PDF 66 (Setting breakpoints in IDEs like PyCharm or VS Code; Monitoring variable values with watch expressions; Step-by-step debugging process; calculate_area example PDF 67; 1. Setting Breakpoints in IDEs like PyCharm, 2. Monitoring Variable Values with Watch Expressions, 3. Step-by-Step Debugging Process: Step Into, Step Over, Continue — PDF 67–68; Fig 5.2)
    - (unnumbered) Exception Handling — PDF 68 (sqlite3 try/except/finally example PDF 68–69; Handling multiple exception types effectively — PDF 69)
  - 5.3 Profiling and Optimization — PDF 69 (nested-loop example 10000×10000 = 100,000,000; Measuring performance using profiling tools — cProfile, timeit, Fig 5.3 PDF 70; Identifying and fixing performance bottlenecks — Fig 5.4; slow_sum/fast_sum example PDF 71 with output PDF 72)
  - Summary — PDF 73; Exercise — PDF 74–75
- Key terms: testing, debugging, bug, syntax error, logic error, runtime error, ZeroDivisionError, SyntaxError, data error, resource leak, unit testing, test case, unittest, pytest, assert, breakpoint, watch expression, step into, step over, continue, PyCharm, VS Code, exception handling, try/except/finally, sqlite3.Error, commit, rollback, profiling, optimization, cProfile, timeit, performance bottleneck, ncalls/tottime/percall/cumtime.
- Laws/rules/principles: pytest auto-discovers functions starting with "test_" (PDF 66); nested loops multiply iteration counts (PDF 70); built-in sum() faster than manual loop (PDF 71–72).
- Formulas: area = 3.14 * radius ** 2 (PDF 67); 10000 × 10000 = 100,000,000 iterations (PDF 70).
- Named processes: three-step debugging (breakpoints → watches → stepping, PDF 67–68); performance test cycle (Fig 5.4); profiling report reading (PDF 72).
- Worked examples (code): 6 — add/multiply with test_add/test_multiply (PDF 65–66); calculate_area/main breakpoint demo (PDF 67); sqlite3 insert with try/except/finally and rollback (PDF 68–69); nested loop (PDF 69); cProfile/timeit slow_sum vs fast_sum (PDF 71); sample profiling output (PDF 72: result 499999500000, slow 0.42 s vs fast 0.09 s).
- In-text features: TIDBIT ×1 (PDF 68); DO YOU KNOW? ×1 (PDF 69); CLASS ACTIVITY ×2 (PDF 64, 69).
- VISUALS IN THIS CHAPTER:
  | Visual ID | Type | PDF p | Printed p | Caption/identifier |
  |---|---|---|---|---|
  | C12-CS/Ch5/Fig5.1 | Annotated code panels | 65 | 61 | Example showing logic error, runtime error and syntax error |
  | C12-CS/Ch5/Vis5-1 | Code listing | 65–66 | 61–62 | add()/multiply() with pytest test functions |
  | C12-CS/Ch5/Vis5-2 | Code listing | 67 | 63 | calculate_area(radius) / main() breakpoint example |
  | C12-CS/Ch5/Fig5.2 | IDE screenshot | 68 | 64 | Debugging in PyCharm |
  | C12-CS/Ch5/Vis5-3 | Code listing | 68–69 | 64–65 | sqlite3 insert with try / except sqlite3.Error / finally |
  | C12-CS/Ch5/Vis5-4 | Code listing | 69 | 65 | nested for-loop (10000 × 10000) |
  | C12-CS/Ch5/Fig5.3 | Table diagram | 70 | 66 | Diagram showing profiling output highlighting bottlenecks |
  | C12-CS/Ch5/Fig5.4 | Cycle diagram | 70 | 66 | Performance Test Cycle |
  | C12-CS/Ch5/Vis5-5 | Code listing | 71 | 67 | cProfile / timeit slow_sum vs fast_sum |
  | C12-CS/Ch5/Vis5-6 | Terminal output listing | 72 | 68 | Profiling Report + Time Comparison Report output |
- ASSESSMENT (Exercise, PDF 74–75): Multiple Choice Questions ×10 (PDF 74–75); Short Questions ×10 (PDF 75); Long Questions ×8 (PDF 75).
- Answer availability: MCQ Answer Key (PDF 75): 1 B, 2 D, 3 B, 4 C, 5 B, 6 B, 7 B, 8 B, 9 A, 10 B — verified.
- Cross-chapter links: sqlite3 from Ch 4; functions/classes from Ch 3; model paper Q3 vii–ix (breakpoint, SyntaxError vs Exception, ZeroDivisionError).
- Issues: numbering jumps from 5.2.1 directly to 5.3 — sub-sections Unit Testing, Breakpoints, Exception Handling are unnumbered (as printed). Fig 5.2 screenshot text is tiny/low-res.

### Chapter 6 — Data and Analysis
- Pages: printed 72–88 · PDF 76–92
- SLOs (printed, 1 bullet): grasp interdisciplinary nature of data science, data types, collection and storage; demonstrate proficiency in data science, machine learning and data visualization applied to real-world business challenges.
- Main concept: Data science workflow and data types, then machine learning — supervised/unsupervised/reinforcement mechanisms, applications, building a model (features, train-test split, linear regression example), evaluating it (accuracy, precision, recall, F1), validating/tuning it, prediction vs causation, and tools (Excel, R, Python/Jupyter).
- Navigation tree:
  - Introduction (unnumbered) — PDF 76
  - 6.1 Introduction to Data Science — PDF 76 (Fig 6.1 workflow; interdisciplinary nature — PDF 77)
  - 6.2 Understanding Data — PDF 77 (Types of Data: Structured and Unstructured; Data Sources and Data Collection Methods — PDF 78; Data Storage and Management Concepts)
  - 6.3 Overview of Machine Learning — PDF 78 (Learning From Data; Difference Between Traditional Programming and Machine Learning — Fig 6.3 PDF 79)
  - 6.4 Machine Learning Mechanisms — PDF 79 (Fig 6.4 labeled vs unlabeled; Supervised, Unsupervised, Reinforcement Machine Learning — PDF 80)
  - 6.5 Applications of Machine Learning — PDF 80 (Healthcare; Business, Education, Everyday Applications — PDF 81; Fig 6.5)
  - 6.6 Building a Machine Learning Model — PDF 81 (student-grade example; Fig 6.6 PDF 82; linear-regression code PDF 82–83; Fig 6.7 PDF 84; Selecting Features and Target Values; Feature Engineering Basics; Train-Test Split Of Data (80/20); Building a Simple Predictive Model — PDF 84–85)
  - 6.7 Model Evaluation and Performance Metrics — PDF 85 (Accuracy and Error; Precision and Recall; F1-Score — PDF 86 with worked example)
  - 6.8 Validation and Model Improvement — PDF 86 (Validation Data Set Preparation; Model Robustness and Reliability; Improving Models Using Hyperparameter Tuning; Simple Analogy: Adjusting the Volume of a Speaker — PDF 87)
  - 6.9 Predictive Modeling and Causality — PDF 87 (Predictive Outcomes in Machine Learning; Understanding Causality; Difference Between Prediction and Causation — PDF 88)
  - 6.10 Machine Learning Tools and Platforms — PDF 88 (Using Excel for Data Analysis; Introduction to R for Data Science — PDF 89; Python and Jupyter Notebooks for Machine Learning)
  - Summary — PDF 90; Exercise — PDF 91–92
- Key terms: data science, interdisciplinary, data, structured/unstructured data, data source, data collection (manual/automatic, real-time), data storage, data management, machine learning, model, training, labeled/unlabeled data, supervised/unsupervised/reinforcement learning, clustering, reward/penalty, feature, target value, feature engineering, scaling, train-test split, overfitting, predictive model, linear regression, Mean Squared Error (MSE), model evaluation, accuracy, error rate, TP/TN/FP/FN, precision, recall, F1-score, validation dataset, robustness, reliability, hyperparameter tuning, prediction, causality/causation, Excel, R, Python, Pandas, NumPy, Jupyter notebook, IDE.
- Laws/rules/principles: common split 80% train / 20% test (PDF 84); lower MSE = better fit (PDF 83); accuracy alone can mislead on unbalanced data (PDF 85–86).
- Formulas: Accuracy = (TP+TN)/(TP+TN+FP+FN) (PDF 85); Precision = TP/(TP+FP); Recall = TP/(TP+FN) (PDF 85); F1-Score = 2 × (Precision × Recall)/(Precision + Recall) (PDF 86); model equation Exam Score = 0.6552 × Hours Studied + 0.1466, MSE = 0.1484 (PDF 83).
- Named processes/comparisons: data-science workflow (Fig 6.1); traditional programming vs ML (Fig 6.3); supervised vs unsupervised vs reinforcement (PDF 80); model-building process (Fig 6.6); prediction vs causation (PDF 88); Excel vs R vs Python (PDF 88–89).
- Worked examples: 2 — sklearn LinearRegression on hours-vs-scores dataset X=[1..10], y=[1,2,2,3,3,4,5,5,6,7] (PDF 82–83, Fig 6.7); metrics example TP=40, TN=50, FP=10, FN=5 → Precision 0.8, Recall 0.8889, F1 0.8421 (PDF 86).
- In-text features: TIDBIT ×4 (PDF 76, 77, 82, 87); DO YOU KNOW? ×2 (PDF 78, 85); CLASS ACTIVITY ×2 (PDF 80, 87).
- VISUALS IN THIS CHAPTER:
  | Visual ID | Type | PDF p | Printed p | Caption/identifier |
  |---|---|---|---|---|
  | C12-CS/Ch6/Fig6.1 | Flow diagram | 76 | 72 | Data Science Work Flow |
  | C12-CS/Ch6/Fig6.2 | Diagram | 77 | 73 | Types of Data |
  | C12-CS/Ch6/Fig6.3 | Comparison diagram | 79 | 75 | Traditional Programming vs Machine Learning |
  | C12-CS/Ch6/Fig6.4 | Illustrated table | 79 | 75 | Labeled vs Unlabeled Data |
  | C12-CS/Ch6/Fig6.5 | Mind-map diagram | 81 | 77 | Applications of Machine Learning |
  | C12-CS/Ch6/Fig6.6 | Cycle diagram | 82 | 78 | Machine Learning Model Building Process |
  | C12-CS/Ch6/Vis6-1 | Code listing + output | 82–83 | 78–79 | Linear regression (numpy, matplotlib, sklearn) hours vs exam scores |
  | C12-CS/Ch6/Fig6.7 | Graph (scatter + regression line) | 84 | 80 | Linear Regression: Hours Studied vs Exam Scores |
  | C12-CS/Ch6/Vis6-2 | Worked calculation box | 86 | 82 | Precision / Recall / F1-Score example (TP 40, TN 50, FP 10, FN 5) |
- ASSESSMENT (Exercise, PDF 91–92): Multiple Choice Questions ×10 (PDF 91); Short Questions ×10 (PDF 91–92); Long Questions ×8 (PDF 92). Long Q6 (evaluation metrics) is formula-based.
- Answer availability: MCQ Answer Key (PDF 92): 1 B, 2 B, 3 C, 4 B, 5 C, 6 C, 7 B, 8 C, 9 B, 10 B — verified.
- Cross-chapter links: hypothesis testing and visualization (Ch 7) continue the analysis workflow; AI/ML applications (Ch 8); Python (Ch 3–5). Model paper Q7 = model evaluation metrics.
- Issues: OCR drops leading characters on PDF 78, 80, 82 (verso pages); formulas garbled in OCR — verified from images. Long Q3 mentions "rule-based learning" which the text does not define (only appears as an MCQ distractor).

### Chapter 7 — Hypothesis Testing
- Pages: printed 89–102 · PDF 93–106
- SLOs (printed, 2 bullets): form hypotheses and perform hypothesis testing; communicate findings using advanced data visuals tied back to hypotheses.
- Main concept: Turning research questions into null/alternative hypotheses, using test statistics (t, chi-square, F), significance level, critical region and p-value to accept/reject them, following a step-by-step numerical example, visualizing results, and handling bias/ethics and clear communication of conclusions.
- Navigation tree:
  - Introduction (unnumbered) — PDF 93
  - 7.1 Introduction to Hypothesis Testing — PDF 93 (Meaning of Hypothesis, hθ(x)=y notation; Research Questions and Hypotheses — PDF 94; Role of Hypothesis Testing in Data Analysis)
  - 7.2 Types of Hypotheses — PDF 94 (Null Hypothesis (H0); Alternative Hypothesis (H1 or Ha); Example research question on study time — PDF 95; Formulating correct hypotheses)
  - 7.3 Concepts in Hypothesis Testing — PDF 95 (Test Statistics: T-value Test formula, example t = 2.5 — PDF 96; Chi-Square Test formula, die example χ² = 3.4; Critical Region — PDF 96; Significance Level (α, 0.05) — PDF 97; P-value and its Importance)
  - 7.4 Performing Hypothesis Tests — PDF 97 (Fig 7.1 PDF 98; Steps in Hypothesis Testing; Simple Hypothesis Testing Examples; Advanced Tests: F-Test and Chi-Square Test, F = S1²/S2², F = 16/9 = 1.78 — PDF 98–99; Numerical Example: Hypothesis Testing, Steps 1–7 — PDF 99–100)
  - 7.5 Data Visualization For Hypothesis Testing — PDF 100 (Fig 7.2; Importance of Data Visualization; Graphs and Charts for Presenting Results — PDF 101; Linking Data Visuals With Hypotheses)
  - 7.6 Ethical Issues in Data Science and Analysis — PDF 101 (Bias in Data Collection and Analysis: 1 Survey, 2 Sampling, 3 Gender, 4 Geographical, 5 Confirmation bias — PDF 101–102; Ethical Use of Data and Models; Responsible Communication of Findings — PDF 102)
  - 7.7 Communicating Results and Conclusions — PDF 102 (Interpreting Test Results; Presenting Findings Clearly — PDF 103; Connecting Conclusions to Hypotheses)
  - Summary — PDF 104; Exercise — PDF 105–106
- Key terms: hypothesis, hypothesis testing, research question, null hypothesis H0, alternative hypothesis H1/Ha, test statistic, t-value, chi-square, F-test, variance, observed/expected frequency, degrees of freedom, critical region, significance level α, p-value, sample mean, standard deviation, decision rule, data visualization, bar chart, line graph, pie chart, scatter plot, outlier, bias (survey, sampling, gender, geographical, confirmation), ethical use of data, consent, responsible communication, interpretation.
- Laws/rules/principles: reject H0 when p-value < α, accept when p-value > α (Fig 7.1, PDF 98); common α = 0.05 (PDF 97); conclusions must be linked to original hypotheses (PDF 103).
- Formulas: hθ(x) = y (PDF 93); t = (x̄ − μ0)/(s/√n) (PDF 95); worked t = (80−75)/(10/√25) = 2.5 (PDF 96); χ² = Σ (Oi − Ei)²/Ei, die example = 3.4 (PDF 96); F = S1²/S2², 16/9 = 1.78 (PDF 98–99); x̄ = Σx/n = 770/10 = 77; s = √(Σ(xi−x̄)²/(n−1)) = √(70/9) ≈ 2.79; t = (77−70)/(2.79/√10) ≈ 7.93, df = 9, p ≈ 0.00002 (PDF 99–100).
- Named processes: 7-step numerical hypothesis test on new teaching method (PDF 99–100); hypothesis testing process flow (Fig 7.1); bias taxonomy (PDF 101–102).
- Worked examples: 4 — t-value (PDF 96), chi-square die (PDF 96), F-test (PDF 99), full numerical example teaching-method marks 72,75,78,74,77,80,76,79,81,78 (PDF 99–100).
- In-text features: TIDBIT ×2 (PDF 93, 97); DO YOU KNOW? ×1 (PDF 101); CLASS ACTIVITY ×1 (PDF 94).
- VISUALS IN THIS CHAPTER:
  | Visual ID | Type | PDF p | Printed p | Caption/identifier |
  |---|---|---|---|---|
  | C12-CS/Ch7/Vis7-1 | Formula box | 95 | 91 | T-value Test formula with legend (x̄, μ0, s, n) |
  | C12-CS/Ch7/Vis7-2 | Table (un-numbered) + calculation | 96 | 92 | Chi-square die example: Face of Die / Observed Frequency (Oi) / Expected Frequency (Ei) |
  | C12-CS/Ch7/Fig7.1 | Flowchart | 98 | 94 | Hypothesis Testing Process |
  | C12-CS/Ch7/Vis7-3 | Worked example box | 99–100 | 95–96 | Numerical Example: Hypothesis Testing (Steps 1–7) |
  | C12-CS/Ch7/Fig7.2 | Charts (bar, line, pie, scatter) | 100 | 96 | Data Visualization |
- ASSESSMENT (Exercise, PDF 105–106): Multiple Choice Questions ×10 (PDF 105); Short Questions ×10 (PDF 105–106); Long Questions ×8 (PDF 106). Long Q4 expects a numerical example; Long Q5 graph-based (visualization).
- Answer availability: MCQ Answer Key (PDF 106): 1 C, 2 B, 3 C, 4 B, 5 B, 6 B, 7 B, 8 B, 9 B, 10 C — verified.
- Cross-chapter links: metrics and model evaluation (Ch 6); ethics/bias also in Ch 8 (8.2) and Ch 9 (9.5). Model paper Q4 i–v are from this chapter.
- Issues: PDF 103 (printed 99) is only one-third full (end of chapter, as printed). OCR garbles all formulas; "7.11" in OCR is "7.1". Symbol (μ) printed as "( g > 70)" in OCR only.

### Chapter 8 — Applications of Computer Science
- Pages: printed 103–117 · PDF 107–121
- SLOs (printed, 2 bullets): evaluate how stakeholders' cultures, values and conflicting interests affect AI system design and assess protective policies; design innovative applications for Pakistan using AI, IoT, Cloud Computing and Blockchain.
- Main concept: Survey of emerging technologies (AI, IoT, cloud, blockchain) and their applications/benefits/challenges, the cultural and ethical dimensions of AI (stakeholders, fairness, bias, conflicts, policy), designing technology solutions for Pakistan's national challenges (smart-agriculture case study), and governance/responsible innovation.
- Navigation tree:
  - Introduction (unnumbered) — PDF 107
  - 8.1 Understanding Emerging Technologies — PDF 107 (Artificial Intelligence (AI) — PDF 108: Common AI Applications, Benefits and Challenges of AI in Society — PDF 108–109; Internet of Things (IoT) — PDF 109: smart-home/healthcare/agriculture examples PDF 110, Fig 8.3, Data Collection, Communication, and Automation; Cloud Computing — PDF 111: Advantages: Scalability, Accessibility, and Cost-effectiveness, Examples: AWS, Microsoft Azure, Fig 8.4 PDF 112; Blockchain Technology — PDF 112)
  - 8.2 Cultural and Ethical Implications of AI Systems — PDF 112 (Fig 8.5 PDF 113; Stakeholders in AI Systems: Developers, Users, Governments, Communities; Cultural Awareness and Diversity; Ethical Principles in AI — PDF 114: Fairness, Accountability, Transparency, and Safety; Avoiding Bias and Ensuring Inclusivity in AI Design; Conflict of Interests Among Stakeholders; Policy and Legal Frameworks (GDPR) — PDF 115)
  - 8.3 Designing Applications for Pakistan Using Emerging Technologies — PDF 115 (Fig 8.6; Identifying National Challenges — PDF 115–116; Innovative Application Design — PDF 116; Technology Integration (smart irrigation); Ethical and Cultural Considerations — PDF 116–117; Case Study: Smart Agriculture in Pakistan — PDF 117: Using IoT Sensors for Soil Monitoring, AI for Predictive Weather Analysis, Cloud for Data Storage and Blockchain for Supply Chain Transparency)
  - 8.4 Policies, Regulations, and Responsible Innovation — PDF 117 (Fig 8.7 PDF 118; Understanding AI Governance; Developing Responsible Technology; Collaboration Across Disciplines)
  - Summary — PDF 119–120; Exercise — PDF 120–121
- Key terms: emerging technologies, Artificial Intelligence, machine learning, Neural Networks (NN), Natural Language Processing (NLP), voice assistant, chatbot, image recognition, recommendation system, self-driving car, Internet of Things, sensor, actuator, microcontroller (ESP32/NodeMCU), automation, cloud computing, scalability, accessibility, cost-effectiveness, pay-as-you-go, AWS, Microsoft Azure, SaaS/PaaS/IaaS, public/private/hybrid cloud, blockchain, block, decentralized, cryptocurrency, Bitcoin, supply chain, stakeholders (developers, users, governments, communities), cultural diversity, fairness, accountability, transparency, safety, bias, inclusivity, conflict of interest, consent, GDPR, AI Ethics Guidelines, national AI policy, design thinking, technology integration, smart agriculture, smart irrigation, AI governance, responsible innovation, interdisciplinary collaboration.
- Laws/rules/principles: four ethical principles of AI — fairness, accountability, transparency, safety (PDF 114); GDPR as data-protection framework (PDF 115, 118); IoT three functions — data collection, communication, automation (PDF 110).
- Formulas: none.
- Named processes/case studies: smart home IoT loop (sensors → microcontroller → cloud → app → actuators, Fig 8.3); DeepMind eye-scan and Amazon/Daraz chatbot examples (PDF 108); Case Study: Smart Agriculture in Pakistan (PDF 117); smart-irrigation integration (PDF 116).
- Worked examples: none (conceptual chapter); 1 case study (PDF 117).
- In-text features: TIDBIT ×7 (PDF 108, 109, 110, 112, 114, 117, 118); DO YOU KNOW? ×5 (PDF 109, 111, 114, 116, 117); CLASS ACTIVITY ×5 (PDF 111, 113, 114, 116 ×2).
- VISUALS IN THIS CHAPTER:
  | Visual ID | Type | PDF p | Printed p | Caption/identifier |
  |---|---|---|---|---|
  | C12-CS/Ch8/Fig8.1 | Diagram (icons) | 107 | 103 | AI, IoT, Cloud Computing, and Blockchain Working Together to Shape the Modern World |
  | C12-CS/Ch8/Fig8.2 | Illustration | 109 | 105 | Artificial Intelligence systems mimic human intelligence to perform tasks like vision, speech, and decision-making |
  | C12-CS/Ch8/Fig8.3 | Labelled system diagram | 110 | 106 | Smart Home using IoT: Connected devices such as lights, thermostat, and security systems can be monitored and controlled remotely through the internet |
  | C12-CS/Ch8/Fig8.4 | Labelled architecture diagram | 112 | 108 | Cloud Computing enables users to store, access, and share data from anywhere through the internet |
  | C12-CS/Ch8/Fig8.5 | Illustration | 113 | 109 | Ethical AI Design Balances the Interests of Different Stakeholders While Ensuring Fairness and Inclusivity |
  | C12-CS/Ch8/Fig8.6 | Map illustration | 115 | 111 | Emerging technologies can solve local challenges in Pakistan across key sectors like agriculture, health, and governance |
  | C12-CS/Ch8/Fig8.7 | Illustration (icons) | 118 | 114 | Policies and Ethical Guidelines Ensure Responsible Innovation and Protect User Rights in Technology Development |
- ASSESSMENT (Exercise, PDF 120–121): Multiple Choice Questions ×10 (Q1–9 PDF 120, Q10 PDF 121); Short Questions ×10 (PDF 121); Long Questions ×8 (PDF 121). No diagram-based questions.
- Answer availability: MCQ Answer Key (PDF 121): 1 B, 2 A, 3 A, 4 A, 5 A, 6 B, 7 A, 8 A, 9 B, 10 B — verified.
- Cross-chapter links: ML/AI concepts (Ch 6); cloud/IoT networking (Ch 1); ethics/bias (Ch 7.6); GDPR and PECA (Ch 9.5). Model paper Q8 = benefits/challenges of AI.
- Issues: Figure 8.1 caption OCR'd as "AIi IoT, Cloud Coinputing" — printed "AI, IoT, Cloud Computing, and Blockchain Working Together to Shape the Modern World". Fig 8.5 caption prints "or" where "of" is meant (OCR) — image reads "of".

### Chapter 9 — Cybersecurity and Safe Digital Collaboration
- Pages: printed 118–136 · PDF 122–140
- SLOs (printed, 4 bullets): apply safe practices when collaborating online; understand common cybersecurity problems, 2FA, biometric verification, secure data transmission; collaborate on digital applications and design for equity/equal access; explore digital entrepreneurship and develop simple technology-based business ideas.
- Main concept: Safe, responsible digital behaviour (passwords, updates, privacy settings, etiquette), cyber threats and defences (2FA, biometrics, firewalls/IDS/antivirus, cryptography, intrusion detection), equitable digital collaboration, digital entrepreneurship in Pakistan, and the ethical, legal (GDPR, PECA 2016) and environmental (e-waste) dimensions of computing.
- Navigation tree:
  - Introduction (unnumbered) — PDF 122 (Fig 9.1)
  - 9.1 Safe and Responsible Digital Practices — PDF 123 (Fig 9.2; Importance of Online Safety; Understanding Strong Passwords and Their Role in Data Protection; Risks of Downloading Suspicious Software and Unsafe Browsing Habits — PDF 124; Software Maintenance and Updates; Privacy and Security Settings; Reading and Managing Privacy Policies; Customizing Privacy and Security Settings for Online Platforms — PDF 125; Safe Online Collaboration; Identifying Secure Collaboration Platforms (e.g., Google Workspace, MS Teams); Practicing Digital Etiquette and Responsible Communication)
  - 9.2 Cybersecurity Awareness and Threat Management — PDF 125 (Understanding Cyber Threats — PDF 126; Common Types of Cyberattacks: virus, phishing, ransomware, spyware, DDoS; How Cyberattacks Affect Individuals and Organizations; Security Tools and Techniques; Two-Factor Authentication (2FA) — PDF 127; Biometric Verification; Use of Firewalls, Intrusion Detection Systems (IDS), and Antivirus Tools; Data Protection and Cryptography (encryption/decryption); Secure Methods for Transmitting and Storing Data (HTTPS) — PDF 127–128; Detecting and Preventing Intrusions — PDF 128; Identifying Vulnerabilities and Suspicious Activities; Applying Troubleshooting and Preventive Measures)
  - 9.3 Digital Collaboration and Equity in Computing — PDF 128 (Fig 9.3 PDF 129; Working Together Online; Importance of Teamwork and Communication in Digital Environments; Tools and Platforms for Real-Time Collaboration; Designing for Equity and Accessibility — PDF 129–130; Creating Inclusive Applications for Diverse Users — PDF 130; Strategies for Effective Collaboration: Assigning Roles, Managing Tasks, Setting Team Goals; Reflecting on Collaborative Experiences — PDF 131; Discussion to Improve Teamwork)
  - 9.4 Digital Entrepreneurship and Innovation — PDF 131 (Characteristics of Successful Entrepreneurs; Entrepreneurship in Pakistan and the Digital Economy; Identifying Business Opportunities; Solving Real-World Problems Through Technology — PDF 132, Fig 9.4; Recognizing Market Needs and Customer Demands; Digital Platforms for Entrepreneurship — Fig 9.5; Using Social Media for Business Promotion — PDF 133; E-commerce Platforms and Online Marketplaces; Freelancing and Remote Work Opportunities; Planning a Small Digital Business; Basic Business Planning Concepts; Budgeting and Resource Management — PDF 134; Teamwork and Communication in Startups; Innovation and Future Opportunities; Emerging Technologies and Entrepreneurship; Role of AI, Apps, and Digital Services in Business; Career Pathways in Technology Entrepreneurship — PDF 135)
  - 9.5 Ethical, Legal, and Environmental Impacts of Computing — PDF 135 (Ethical Use of Technology; Respecting Intellectual Property and Data Ownership; Understanding Consequences of Unethical Digital Behavior; Legal Aspects and Data Privacy Laws — PDF 135–136; Overview of International Frameworks (e.g., GDPR) — PDF 136; Cybercrime Laws and Data Protection Policies in Pakistan (PECA 2016); Environmental and Social Impacts; E-waste Management and Sustainable Computing; The Role of Technology in Cultural and Societal Change — PDF 136–137)
  - Summary — PDF 137–138; Exercise — PDF 139–140
- Key terms: online safety, digital footprint, strong password, spyware, unsafe browsing, software update/patch, privacy settings, privacy policy, two-factor authentication (2FA), read receipts, secure collaboration platform (Google Workspace, Microsoft Teams, Google Meet, Zoom), digital etiquette, cybersecurity, cyber threat, virus, phishing, ransomware, spyware, DDoS, data breach, biometric verification, firewall, intrusion detection system (IDS), antivirus, data protection, cryptography, encryption, decryption, key, HTTPS, backup, intrusion, vulnerability, system log, troubleshooting, digital collaboration, equity, accessibility, inclusive application, screen reader, roles/tasks/goals, reflection, digital entrepreneurship, innovation, entrepreneur, digital economy, business opportunity, market need, social media, e-commerce (Daraz, Amazon), freelancing (Fiverr, Upwork), remote work, business plan, budget, startup, career pathways, ethical use, intellectual property, data ownership, cybercrime, data privacy law, GDPR, PECA 2016, e-waste, sustainable computing, digital divide.
- Laws/rules/principles: Prevention of Electronic Crimes Act (PECA) 2016 — Pakistan's main cybercrime law (PDF 136); GDPR — EU data-protection law (PDF 136); 12-character password takes "millions of years" to crack (DYK, PDF 123).
- Formulas: none.
- Named processes/examples: Instagram/WhatsApp privacy-setting examples (PDF 124–125); Google Docs "View only" sharing (PDF 125); 2FA login flow (PDF 127); encryption/decryption flow (PDF 127); intrusion detection & preventive measures (PDF 128); collaboration strategies — roles, tasks, goals (PDF 130); business-planning steps (PDF 133–134).
- Worked examples: none (conceptual); numerous scenario examples.
- In-text features: TIDBIT ×6 (PDF 123, 124, 126, 127, 130, 136); DO YOU KNOW? ×7 (PDF 123, 126, 129, 131, 133, 134, 135); CLASS ACTIVITY ×5 (PDF 124, 127, 128, 130, 136).
- VISUALS IN THIS CHAPTER:
  | Visual ID | Type | PDF p | Printed p | Caption/identifier |
  |---|---|---|---|---|
  | C12-CS/Ch9/Fig9.1 | Diagram (icons) | 122 | 118 | Cybersecurity, Ethics, and Digital Collaboration in Today's Connected World |
  | C12-CS/Ch9/Fig9.2 | Illustration | 123 | 119 | Safe Digital Practices |
  | C12-CS/Ch9/Fig9.3 | Illustration | 129 | 125 | Digital Collaboration |
  | C12-CS/Ch9/Fig9.4 | Tree diagram | 132 | 128 | Technology-Based Solutions |
  | C12-CS/Ch9/Fig9.5 | Tree diagram | 132 | 128 | Digital Platforms |
- ASSESSMENT (Exercise, PDF 139–140): Multiple Choice Questions ×10 (PDF 139); Short Questions ×10 (Q1–4 PDF 139, Q5–10 PDF 140); Long Questions ×8 (PDF 140).
- Answer availability: MCQ Answer Key (PDF 140): 1 B, 2 C, 3 B, 4 A, 5 B, 6 C, 7 B, 8 C, 9 B, 10 C. KEY ERROR: Q10 "The international law that protects user privacy is" — correct option is (b) GDPR, but the key prints C (CPU). Items 1–9 verified correct.
- Cross-chapter links: firewalls/encryption (Ch 1.14); GDPR, ethics (Ch 8.2, 8.4); bias/ethics (Ch 7.6); emerging technologies in business (Ch 8). Model paper Q4 viii–ix and Q9 from this chapter.
- Issues: Q10 answer-key error (PDF 140). Text on PDF 133 says "as shown in Figure 9.4" for digital platforms (should be Figure 9.5 — figure-reference slip). OCR loses left margins on PDF 124, 126, 128, 130.

## BACK MATTER / SUPPLEMENTARY
- Pairing Scheme — "Instructions for Preparation of Exam Paper of Computer Science and Entrepreneurship for Class XII / Essential Instructions for Paper Setters" (printed 137–138, PDF 141–142). Total 75 marks, time 2:30 hours.
  - Part-I Objective, Q-1: 15 MCQs from the entire textbook, 1 × 15 = 15 marks. Chapter distribution: Ch1 2, Ch2 2, Ch3 2, Ch4 2, Ch5 2, Ch6 2, Ch7 1, Ch8 1, Ch9 1.
  - Part-II Subjective: three questions (Q2, Q3, Q4), each with 9 short questions, attempt 6 of 9, 2 × 6 = 12 marks each (36 total). Q-2: Ch1 3, Ch2 4, Ch6 2. Q-3: Ch3 2, Ch4 4, Ch5 3. Q-4: Ch7 5, Ch8 2, Ch9 2.
  - Part-III Subjective: five long questions, attempt any 3 of 5, 8 marks each, 3 × 8 = 24. Q-5 Ch1 (1), Q-6 Ch3 (1), Q-7 Ch6 (1), Q-8 Ch8 (1), Q-9 Ch9 (1). (Chapters 2, 4, 5, 7 have no long question.)
  - Check: 15 + 36 + 24 = 75 marks.
- Model Paper — "Model Paper Computer Science and Entrepreneurship Intermediate part-II" (printed 139–141, PDF 143–145; PDF 146 is a duplicate scan of printed 141).
  - OBJECTIVE (PDF 143): Question 1 MCQ ×15, Total Marks 15, Time Allowed 20 mins; options a–d; instruction to fill circle, two circles = zero. Chapter mapping: Q1–2 Ch1 (HTTP; modem), Q3–4 Ch2 (compound proposition P AND Q; satisfiable), Q5–6 Ch3 (encapsulation; class keyword), Q7–8 Ch4 (Tkinter; Entry), Q9–10 Ch5 (unittest; try-except), Q11–12 Ch6 (accuracy; learn from data), Q13 Ch7 (t-value), Q14 Ch8 (AWS), Q15 Ch9 (malware infection). No answer key printed for the model paper.
  - SUBJECTIVE (PDF 144–145): Total Marks 60, Time Allowed 2:10 hours. SECTION I: Q2 — any six of nine short answers (6×2=12), items i–ix from Ch1 (network architecture, bus-topology cable break, DNS phonebook), Ch2 (propositional vs predicate logic, tautology, quantified statement, decomposition of "cleaning a messy bedroom") and Ch6 (supervised vs unsupervised, train/test split); Q3 — any six of nine (6×2=12), items i–ix from Ch3 (encapsulation, Player.health = 100), Ch4 (Entry delete, mainloop(), root = Tk(), missing database table) and Ch5 (breakpoint, Syntax Error vs Exception, ZeroDivisionError for 10 / 0); Q4 — any six of nine (6×2=12), items i–ix from Ch7 (H0 vs Ha, deleting outliers ethics, 5 % error at α = 0.05, die-fairness hypotheses, p-value), Ch8 (AI in daily life, blockchain security) and Ch9 (e-waste, suspicious software). SECTION II: attempt any three descriptive answers (3×8=24): Q5 OSI model layers (Ch1); Q6 Python program for multilevel inheritance Grandfather/Father/Son (Ch3); Q7 model evaluation — accuracy, precision, recall, F1 (Ch6); Q8 benefits/challenges of AI and ethical principles (Ch8); Q9 privacy/security settings and privacy policies (Ch9). Marks (08) each. Objective + Subjective = 75, matching the pairing scheme exactly.
- Back cover (PDF 147): Qaumi Tarana (national anthem, Urdu) + PECTAA logo. No glossary, bibliography, index, or periodic table in this book. Chapter summaries serve as per-chapter glossaries (term + definition lists).

## ASSESSMENT SUMMARY TABLE
| Ch | MCQ | Fill/TF/Match | Short | Constructed | Long | Numerical/Exercise Qs | Diagram/graph/table-based | Other | Exercise PDF pp | Answers |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 10 | 0 | 10 | 0 | 8 | 0 | 0 | 8 class activities | 23–24 | MCQ key PDF 24 (verified) |
| 2 | 10 | 0 | 10 | 0 | 8 | 0 | Long Q5 truth-table based | 3 class activities | 35–36 | MCQ key PDF 36 (verified) |
| 3 | 10 | 0 | 10 | 0 | 8 | 0 | 0 | 2 class activities | 47–48 | MCQ key PDF 48 (verified) |
| 4 | 10 | 0 | 10 | 0 | 8 | 0 | 0 | 3 class activities | 62–63 | MCQ key PDF 63 (verified) |
| 5 | 10 | 0 | 10 | 0 | 8 | 0 | 0 | 2 class activities | 74–75 | MCQ key PDF 75 (verified) |
| 6 | 10 | 0 | 10 | 0 | 8 | Long Q6 formula-based | 0 | 2 class activities | 91–92 | MCQ key PDF 92 (verified) |
| 7 | 10 | 0 | 10 | 0 | 8 | Long Q4 numerical example | Long Q5 graph-based | 1 class activity | 105–106 | MCQ key PDF 106 (verified) |
| 8 | 10 | 0 | 10 | 0 | 8 | 0 | 0 | 5 class activities | 120–121 | MCQ key PDF 121 (verified) |
| 9 | 10 | 0 | 10 | 0 | 8 | 0 | 0 | 5 class activities | 139–140 | MCQ key PDF 140 (Q10 wrong) |
| Model paper | 15 | 0 | 27 (3 × 9, attempt 6 each) | 0 | 5 (attempt 3) | Q4 iii numeric | 0 | — | 143–145 | none printed |
| TOTAL | 105 | 0 | 117 | 0 | 77 | — | — | 31 class activities | — | 9 MCQ keys |

Chapter totals (excluding model paper): MCQ 90, Short 90, Long 72.

## BOOK ISSUES
1. Missing printed page 21 (Chapter 2): PDF 25 (printed 20) → PDF 26 (printed 22). Lost: end of 2.1, heading 2.2 (title unknown), Figure 2.1, continuation into "…correct order". Page rule shifts from pdf = printed+5 to pdf = printed+4 at PDF 26.
2. Duplicate scan: PDF 145 and PDF 146 are both printed page 141 (model paper Section II). PDF 147 is the back cover.
3. Answer-key error: Chapter 9 MCQ Q10 key says "C" (CPU); correct answer is (b) GDPR (PDF 139–140).
4. TOC misprint "Computer Neworks" (PDF 5).
5. Figure-reference slip: PDF 133 text cites "Figure 9.4" for digital platforms, which is Figure 9.5 (PDF 132).
6. Chapter 2 Figure 2.6 is referenced in text (PDF 29) but the box carries no printed "Figure 2.6:" caption line (as far as legible at 80–120 dpi) — treated as Fig 2.6 by reference.
7. Heading numbering: Ch 5 uses 5.1, 5.2, 5.2.1 then 5.3 (sub-sections unnumbered); all other chapters use only N.n numbering with unnumbered sub-headings. Chapter 2 jumps 2.1 → 2.3 in the scan because 2.2 was on the lost page.
8. Scan quality: skewed pages, dark gutter strips, printer signature text in margins (e.g. PDF 6, 21, 49, 64, 108, 125, 133); OCR drops the first characters of many lines on verso pages (PDF 9, 11, 17, 19, 21, 26, 30, 32, 78, 80, 102, 110, 116, 124, 126, 128, 130, 136). All code listings, formulas and tables must be read from page images.
9. Model paper has no answer key; pairing scheme omits long questions from Ch 2, 4, 5, 7 (by design).
10. Minor content observations: Fig 8.5 caption on page reads "…Interests of Different Stakeholders…"; Chapter 6 Long Q3 and MCQ distractors mention "rule-based learning" which the chapter does not define; Fig 6.7 caption printed as "Linear Regression: Hours Studied vs Exam Scores" (caption-hint TSV truncates it).
