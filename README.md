# RFCScan: An LLM Agent for Functional Bug Detection in Network Protocols

RFCScan detects functional inconsistencies between network protocol implementations and their RFC documents using LLM-guided analysis.

---
## ⚙️ Configuration

Before running, make sure to:

- Update the `config` in `init.py` and `diff.py` with your LLM model configures. The current code shows an example of using bedrock Claude 3.5.
- In `diff.py` and `global_vars.py`, set the correct paths to:
  - The RFC document
  - The protocol implementation


---
## 🚀 Phase 1: Code Semantic Indexing

Generate a semantic index of the codebase to enable context-aware retrieval.

```bash
python repo.py /path/to/repo
```

## 🔍 Phase 2: Retrieval-Guided Detection

Run the detection pipeline to identify RFC violations in the implementation.

```bash
python diff.py
```