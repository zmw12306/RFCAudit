# RFCAudit

**RFCAudit** is an AI-powered tool that automatically detects misalignments between source code implementations and their corresponding RFC or specification documentation. Using hierarchical semantic analysis and retrieval-augmented generation, RFCAudit helps ensure code compliance with protocol specifications.

## 🚀 Quick Start

### 1. Installation

```bash
# Clone the repository
git clone xxx
cd RFCAudit

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create new folders for RFC and summary
mkdir RFC
mkdir summary
```

### 2. Configuration

Create and configure `config.yaml` with your LLM API settings and project paths:

```yaml
project:
  protocol: "protocol_name"                                    # Protocol name for reporting
  project_path: "/path/to/your/project/"              # Root path of your project
  prefer_path: "/path/to/your/project/src/"           # Source folder to analyze
  rfc_input: "RFC/docs.txt"                           # Path to RFC documentation
  rfc_cleaned_output: "RFC/cleaned_docs.txt"          # Cleaned RFC output location
  summary_json: "summary/summary.json"                # Code summary output
  log_or_not: false                                   # Enable/disable logging
  log_file: "log.txt"                                 # Log file location

llm_config:
  model_name: "LLM model name"                        # LLM model name
  OPENAI_API_KEY: "Your API Key"                      # OPENAI API Key
  temperature: 0.0
  retry_min: 5                                        # Minimum retry delay (seconds)
  retry_max: 60                                       # Maximum retry delay (seconds)
  max_retries: 30                                     # Maximum retry attempts
```



## 📖 Usage

RFCAudit operates in two phases:

### Phase 1: Code Summarization

Generate a hierarchical semantic summary of your codebase:

```bash
python repo.py
```

This will:
- Parse your C source code using Tree-sitter
- Create hierarchical summaries at function, file, and module levels
- Save results to the specified `summary_json` file

### Phase 2: Inconsistency Detection

Analyze the code against RFC documentation:

```bash
python diff.py
```

This will:
- Process and clean the RFC documentation
- Compare code summaries against RFC specifications
- Generate a detailed inconsistency report in `inconsistencies_{protocol}.json`

## 📊 Output Files

| File | Description |
|------|-------------|
| `summary/{protocol}_summary.json` | Hierarchical code summarization results |
| `inconsistencies_{protocol}.json` | Detected misalignments between code and RFC |
| `RFC/cleaned_{protocol}.txt` | Processed RFC documentation |
| `log.txt` | Execution logs (if enabled) |



## 🏗️ Project Structure

```
RFCAudit/
├── README.md                 # This file
├── config.yaml              # Configuration file
├── requirements.txt          # Python dependencies
├── summarizer.py            # Code summarization tool
├── checker.py               # Inconsistency detection tool
├── RFC/                     # Example RFCs 
├── summary/                 # Sample code analysis outputs
```



