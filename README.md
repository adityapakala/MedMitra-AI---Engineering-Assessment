# MedMitra-AI---Engineering-Assessment

# Medical Question Answering System

## Overview
This project implements a **Medical Question Answering System** that retrieves relevant medical information using FAISS and generates answers to user queries using a fine-tuned T5 model. The system integrates both **retrieval** and **generation** components to provide accurate responses to medical questions.

## Features
- **Data Preparation**: Text cleaning, tokenization, and chunking to preprocess the dataset.
- **Retrieval System**: Uses FAISS to index and retrieve relevant passages.
- **LLM Fine-Tuning**: Fine-tunes the T5 model for generating medical answers.
- **Evaluation**: BLEU and ROUGE scores to evaluate performance.
- **User Interface**: A simple Flask-based API where users can submit medical queries and get responses.

## Table of Contents
- [Requirements](#requirements)
- [Setup Instructions](#setup-instructions)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Evaluation](#evaluation)

---

## Requirements

- Python 3.7+
- Flask
- FAISS
- PyTorch
- Sentence Transformers
- Transformers
- NLTK
- ROUGE
- BLEU

## Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone <repository_url>
   cd <project_directory>
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Download and preprocess the dataset** (if needed):
   - Upload your medical Q&A dataset in JSONL format.

4. **Run the Flask application**:
   ```bash
   python main.py
   ```

5. **Run the Evaluation script**:
   - Evaluate the model's performance using BLEU and ROUGE metrics.
   ```bash
   python evaluate.py
   ```

---

## Usage

1. **Start the Flask App**:
   - Once the app is running, you can send queries via HTTP POST requests to the `/ask` endpoint.

2. **Example POST Request**:
   ```bash
   curl -X POST http://127.0.0.1:5000/ask \
   -H 'Content-Type: application/json' \
   -d '{"query": "What are the symptoms of diabetes?"}'
   ```

   The response will be in the following format:
   ```json
   {
     "answer": "Symptoms of diabetes include increased thirst, frequent urination, and fatigue."
   }
   ```

---

## Project Structure

```plaintext
├── main.py                   # Main Flask app
├── requirements.txt           # Project dependencies
├── README.md                  # Project documentation
├── evaluate.py                # Script for BLEU/ROUGE evaluation
├── models/                    # Directory for pre-trained and fine-tuned models
├── data/                      # Directory for storing datasets
├── templates/                 # HTML files for UI (optional)
└── static/                    # Static files like CSS, JS (optional)
```

- **`main.py`**: Contains the Flask API and code for embedding, retrieval, and answer generation.
- **`evaluate.py`**: Evaluates the model using BLEU and ROUGE scores.
- **`models/`**: Directory to store pre-trained and fine-tuned models.
- **`data/`**: Store the cleaned and tokenized medical Q&A dataset.

---

## Evaluation

We used BLEU and ROUGE scores to evaluate the performance of the generated responses compared to the expected answers.

1. **BLEU Score**:
   ```bash
   BLEU Score: 0.4258
   ```

2. **ROUGE Scores**:
   - **ROUGE-1**:
     - F1 Score: 0.7584
   - **ROUGE-2**:
     - F1 Score: 0.5919
   - **ROUGE-L**:
     - F1 Score: 0.7584

### Error Analysis
- The model performs well for most medical questions but struggles with more complex questions that require detailed answers or domain-specific knowledge.
- Future improvements could involve more diverse datasets or fine-tuning on a broader range of medical content.

---

## Optional: Running the System on AWS

1. **Step-by-step Instructions**:
   - Set up AWS SageMaker to host the fine-tuned T5 model.
   - Use AWS Lambda and API Gateway for serverless API execution.
   - Store the dataset and models in S3.

2. **Architecture Diagram**:
   - This diagram shows how each AWS component interacts to create a seamless pipeline.
## Architecture Diagram 

```mermaid
graph LR
  A[User Interface] --> B[API Gateway]
  B --> C[AWS Lambda]
  C --> D[AWS SageMaker]
  
  style A fill:#f9f,stroke:#333,stroke-width:4px
  style B fill:#bbf,stroke:#333,stroke-width:4px
  style C fill:#bbf,stroke:#333,stroke-width:4px
  style D fill:#bbf,stroke:#333,stroke-width:4px

