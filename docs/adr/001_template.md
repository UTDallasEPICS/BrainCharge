# ADR [Number]: [Short Title of the Decision]

- **Status:** [ Proposed | Accepted | Rejected | Superseded ]
- **Deciders:** [Name/GitHub Handles of everyone involved in the choice]
- **Date:** YYYY-MM-DD

---

## 1. Context & Problem Statement

Describe the issue or engineering challenge you are facing. Why does a decision need to be made right now? Keep it clear and concise.

> Example: We need to store user preferences and sensor logs locally on the micro-controller, but our available EEPROM space is insufficient.

---

## 2. Decision Drivers (Goals & Constraints)

List the main objectives, limitations, or requirements that influence this decision:

- **Goal 1:** Must handle up to 10,000 write cycles per day.
- **Goal 2:** Cost must remain under $5 per unit.
- **Constraint:** Must fit within our existing physical enclosure dimensions.

---

## 3. Options Considered

### Option 1: [Name of Option 1]

Short description of what this option entails.

- **Pros:**
  - Advantage 1
  - Advantage 2
- **Cons:**
  - Disadvantage 1
  - Disadvantage 2

### Option 2: [Name of Option 2]

Short description of what this option entails.

- **Pros:**
  - Advantage 1
  - Advantage 2
- **Cons:**
  - Disadvantage 1
  - Disadvantage 2

### Option 3: [Name of Option 3]

Short description of what this option entails.

- **Pros:**
  - Advantage 1
  - Advantage 2
- **Cons:**
  - Disadvantage 1
  - Disadvantage 2

---

## 4. Decision & Justification

**Chosen Option:** Option [X] — [Name of Option]

### Rationale

Explain why this option was selected over the others. Connect the decision back to the goals and constraints in Section 2.

> Example: We chose Option 2 because it meets our cost budget of under $5 while providing significantly better read/write speed than Option 1. Although Option 3 offered better long-term reliability, its high unit price makes it unfeasible for our production scale.

---

## 5. Consequences & Next Steps

### Positive Consequences

What becomes easier or better as a result of this decision?

### Negative Consequences / Trade-offs

What risks, tech debt, or overhead are we accepting?

### Action Items

- Task 1 (e.g., Update system design diagram)
- Task 2 (e.g., Order component sample for testing)
