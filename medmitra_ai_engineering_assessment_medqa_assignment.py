# -*- coding: utf-8 -*-
"""MedMitra_AI_Engineering_Assessment_MEDQA_Assignment.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/108E31x6uPQDdw15PFIbnnl2Kyi5ZRcd_
"""

!pip install sentence-transformers

import json
import pandas as pd
import re
import numpy as np
import nltk
from nltk.tokenize import word_tokenize, sent_tokenize
from sentence_transformers import SentenceTransformer
import faiss

# Download necessary NLTK data
nltk.download('punkt')

# Load dataset (limit to the first 1000 entries for memory efficiency)
def load_dataset(file_path, limit=1000):
    data = []
    with open(file_path, 'r') as f:
        for idx, line in enumerate(f):
            if idx >= limit:
                break
            data.append(json.loads(line))
    return pd.DataFrame(data)

df = load_dataset("/content/MED_QA.jsonl", limit=1000)

"""1. **Data Preparation**"""

# Text cleaning function
def clean_text(text):
    text = re.sub(r'\[.*?\]', '', text)  # Remove content inside square brackets
    text = re.sub(r'\(.*?\)', '', text)  # Remove content inside parentheses
    text = re.sub(r'[^a-zA-Z\s]', '', text)  # Remove special characters and numbers
    text = text.lower()  # Convert to lowercase
    text = re.sub(r'[^\w\s]', ' ', text)  # Remove any remaining non-word characters
    return text

# Apply cleaning to questions and answers
df['cleaned_question'] = df['question'].apply(clean_text)
df['cleaned_answer'] = df['answer'].apply(clean_text)

# Tokenization of questions and answers
df['tokenized_question'] = df['cleaned_question'].apply(word_tokenize)
df['tokenized_answer'] = df['cleaned_answer'].apply(word_tokenize)

# Chunking text into smaller passages (with a max limit of 512 tokens)
def chunk_text(text, max_chunk_size=512):
    words = word_tokenize(text)
    chunks = [' '.join(words[i:i+max_chunk_size]) for i in range(0, len(words), max_chunk_size)]
    return chunks

# Chunk both questions and answers
df['chunked_question'] = df['cleaned_question'].apply(lambda x: chunk_text(x, max_chunk_size=512))
df['chunked_answer'] = df['cleaned_answer'].apply(lambda x: chunk_text(x, max_chunk_size=512))

# Fix the map_option_to_answer function
def map_option_to_answer(row):
    # The correct answer (typically 'a', 'b', 'c', etc.)
    correct_option = str(row['answer'].strip())

    # Ensure the row['options'] contains a mapping from the correct option (e.g., 'a') to the full answer
    full_answer = row['options'].get(correct_option, "")  # Default to empty string if option not found
    return full_answer

# Apply the updated function to get the full answer text
df['full_answer_text'] = df.apply(map_option_to_answer, axis=1)

# Load pre-trained Sentence-BERT model for embeddings
model = SentenceTransformer('all-MiniLM-L6-v2')

# Generate embeddings for cleaned questions (concatenating chunked results)
df['question_embeddings'] = df['cleaned_question'].apply(lambda x: model.encode(x))
df['answer_embeddings'] = df['cleaned_answer'].apply(lambda x: model.encode(x))

"""2. **Retrieval System Implementation**


"""

import numpy as np
import faiss

# Assume `df` contains preprocessed questions and answers, and we already generated embeddings for each

# Create FAISS index using L2 (Euclidean distance) or you could switch to cosine similarity if needed
def create_faiss_index(embeddings):
    # Initialize FAISS index (L2 distance, alternative: faiss.IndexFlatIP for inner product)
    index = faiss.IndexFlatL2(embeddings.shape[1])  # embeddings.shape[1] is the dimensionality of embeddings
    index.add(embeddings)  # Add all the precomputed question embeddings
    return index

# Convert the question embeddings to numpy array
question_embeddings = np.array(df['question_embeddings'].tolist()).astype('float32')

# Create FAISS index and store embeddings
index = create_faiss_index(question_embeddings)

# Preprocessing function for user queries (reuse the previous text cleaning)
def preprocess_query(query):
    cleaned_query = clean_text(query)
    return cleaned_query

# Generate embedding for the query using the pre-trained model
def encode_query(query):
    cleaned_query = preprocess_query(query)
    query_embedding = model.encode(cleaned_query).astype('float32')  # Convert to float32 for FAISS
    return query_embedding

# Retrieval function: Find top-N most relevant passages based on query
def retrieve_top_n(query_embedding, k=5):
    distances, indices = index.search(np.array([query_embedding]), k=k)  # Search FAISS index
    results = df.iloc[indices[0]]  # Get corresponding rows from the dataframe
    return results, distances[0]  # Return results and their distances/scores

# Rank the retrieved results based on relevance scores (lower distance = more relevant)
def rank_results(results, distances):
    # Create a DataFrame to store results and their corresponding distances (i.e., relevance score)
    ranked_results = results.copy()
    ranked_results['relevance_score'] = distances  # Lower scores are better for L2 distance
    ranked_results = ranked_results.sort_values(by='relevance_score', ascending=True)  # Sort by relevance
    return ranked_results[['cleaned_question', 'cleaned_answer', 'full_answer_text', 'relevance_score']]

# Example query process and ranking
user_query = "What is the treatment for diabetes?"
query_embedding = encode_query(user_query)
retrieved_results, distances = retrieve_top_n(query_embedding, k=5)
ranked_results = rank_results(retrieved_results, distances)

# Display ranked results
print(ranked_results)

"""**3**. **LLM Fine Tuning**

"""

from transformers import T5ForConditionalGeneration, T5Tokenizer

# Load pre-trained T5 model and tokenizer
model_name = "t5-small"  # You can use larger versions like 't5-base' or 't5-large'
model = T5ForConditionalGeneration.from_pretrained(model_name)
tokenizer = T5Tokenizer.from_pretrained(model_name)

# Prepare the dataset for T5 fine-tuning in the format "question: <question>" -> "<answer>"
def prepare_t5_format(df):
    inputs = []
    targets = []

    for i, row in df.iterrows():
        question = row['cleaned_question']  # cleaned and tokenized question
        answer = row['full_answer_text']  # corresponding answer

        if answer:  # Only consider valid entries
            inputs.append(f"question: {question}")
            targets.append(answer)

    return inputs, targets

# Prepare the inputs and targets
inputs, targets = prepare_t5_format(df)

# Tokenize the inputs and targets
def tokenize_data(inputs, targets):
    input_encodings = tokenizer(inputs, padding=True, truncation=True, return_tensors="pt")
    target_encodings = tokenizer(targets, padding=True, truncation=True, return_tensors="pt")

    return input_encodings, target_encodings

# Tokenizing the dataset
input_encodings, target_encodings = tokenize_data(inputs, targets)

# Create the dataset using the custom class
train_dataset = QADataset(input_encodings, target_encodings)

# Tokenize the inputs and targets
def tokenize_data(inputs, targets):
    input_encodings = tokenizer(inputs, padding=True, truncation=True, return_tensors="pt")
    target_encodings = tokenizer(targets, padding=True, truncation=True, return_tensors="pt")

    return input_encodings, target_encodings

# Tokenizing the dataset
input_encodings, target_encodings = tokenize_data(inputs, targets)

import torch

# Create a custom dataset class
class QADataset(torch.utils.data.Dataset):
    def __init__(self, input_encodings, target_encodings):
        self.input_encodings = input_encodings
        self.target_encodings = target_encodings

    def __getitem__(self, idx):
        return {
            'input_ids': self.input_encodings['input_ids'][idx],
            'attention_mask': self.input_encodings['attention_mask'][idx],
            'labels': self.target_encodings['input_ids'][idx]
        }

    def __len__(self):
        return len(self.input_encodings['input_ids'])

# Create the dataset
train_dataset = QADataset(input_encodings, target_encodings)

from sklearn.model_selection import train_test_split

# Split the dataframe into training and evaluation sets
train_df, eval_df = train_test_split(df, test_size=0.1, random_state=42)  # 10% for evaluation

# Prepare the inputs and targets for evaluation
inputs_eval, targets_eval = prepare_t5_format(eval_df)

# Tokenizing the evaluation dataset
input_encodings_eval, target_encodings_eval = tokenize_data(inputs_eval, targets_eval)

# Create the eval dataset using the custom class
eval_dataset = QADataset(input_encodings_eval, target_encodings_eval)

from transformers import Trainer, TrainingArguments

# Define the training arguments
training_args = TrainingArguments(
    output_dir="./t5_finetuned_medical_qa",
    evaluation_strategy="epoch",
    per_device_train_batch_size=4,  # Adjust based on your GPU memory
    per_device_eval_batch_size=4,
    learning_rate=5e-5,
    num_train_epochs=3,  # More epochs for better training
    weight_decay=0.01,
)


# Initialize the Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,  # Make sure this is included
)


# Start training
trainer.train()

print(f"Training dataset size: {len(train_dataset)}")
print(f"Evaluation dataset size: {len(eval_dataset)}")

# After preparing the datasets, check if they are empty
if len(inputs) == 0 or len(targets) == 0:
    print("Training dataset is empty. Please check the data preparation process.")
if len(inputs_eval) == 0 or len(targets_eval) == 0:
    print("Evaluation dataset is empty. Please check the data preparation process.")

def generate_answer(question):
    input_text = (
        f"Provide a structured answer for the following question: '{question}'. "
        "Include a brief introduction, key management strategies, and a conclusion."
    )
    input_ids = tokenizer(input_text, return_tensors="pt").input_ids
    outputs = model.generate(input_ids, max_new_tokens=150, num_beams=5, early_stopping=True)
    answer = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return answer

outputs = model.generate(input_ids, max_new_tokens=150, num_beams=5, early_stopping=True, temperature=0.7, top_k=50)

test_question = "How can diabetes be managed effectively?"
generated_answer = generate_answer(test_question)

print(f"Question: {test_question}")
print(f"Generated Answer: {generated_answer}")

import pandas as pd

# Display the entire DataFrame (or a portion of it)
print(df[['cleaned_question', 'full_answer_text']])



import json
import pandas as pd
import re
import torch
from nltk.tokenize import word_tokenize
from transformers import T5ForConditionalGeneration, T5Tokenizer

# Load the dataset (limit to the first 300 entries for efficiency)
def load_dataset(file_path, limit=1000):
    data = []
    with open(file_path, 'r') as f:
        for idx, line in enumerate(f):
            if idx >= limit:
                break
            data.append(json.loads(line))
    return pd.DataFrame(data)

# Define the file path to your MED_QA.jsonl file
file_path = "/content/MED_QA.jsonl"
df = load_dataset(file_path, limit=1000)

# Clean text function
def clean_text(text):
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    text = text.lower()
    return text

# Apply cleaning to questions and answers
df['cleaned_question'] = df['question'].apply(clean_text)
df['cleaned_answer'] = df['answer'].apply(clean_text)

# Mapping answer options to full text
def map_option_to_answer(row):
    correct_option = row['answer'].strip()
    full_answer = row['options'].get(correct_option, "")
    return full_answer

df['full_answer_text'] = df.apply(map_option_to_answer, axis=1)

# Now define the function to prepare the dataset for T5 fine-tuning
def prepare_t5_format(df):
    inputs = []
    targets = []

    for i, row in df.iterrows():
        question = row['cleaned_question']  # cleaned and tokenized question
        answer = row['full_answer_text']  # corresponding answer

        if answer:  # Only consider valid entries
            inputs.append(f"question: {question}")
            targets.append(answer)

    return inputs, targets

# Prepare the inputs and targets
inputs, targets = prepare_t5_format(df)

# Load pre-trained T5 model and tokenizer
model_name = "t5-small"  # You can use 't5-base' or 't5-large' for larger models
model = T5ForConditionalGeneration.from_pretrained(model_name)
tokenizer = T5Tokenizer.from_pretrained(model_name)

# Tokenize the inputs and targets
def tokenize_data(inputs, targets):
    input_encodings = tokenizer(inputs, padding=True, truncation=True, return_tensors="pt")
    target_encodings = tokenizer(targets, padding=True, truncation=True, return_tensors="pt")
    return input_encodings, target_encodings

input_encodings, target_encodings = tokenize_data(inputs, targets)

# Custom Dataset class for fine-tuning
class QADataset(torch.utils.data.Dataset):
    def __init__(self, input_encodings, target_encodings):
        self.input_encodings = input_encodings
        self.target_encodings = target_encodings

    def __getitem__(self, idx):
        return {
            'input_ids': self.input_encodings['input_ids'][idx],
            'attention_mask': self.input_encodings['attention_mask'][idx],
            'labels': self.target_encodings['input_ids'][idx]
        }

    def __len__(self):
        return len(self.input_encodings['input_ids'])

# Create the dataset for training
train_dataset = QADataset(input_encodings, target_encodings)

# Verify everything is correct by checking the dataset
print(f"Training dataset size: {len(train_dataset)}")

# You can now proceed with training the model as defined previously.

import json
import pandas as pd
import re
import torch
from sklearn.model_selection import train_test_split
from transformers import T5ForConditionalGeneration, T5Tokenizer

# Load the dataset (limit to the first 300 entries for efficiency)
def load_dataset(file_path, limit=1000):
    data = []
    with open(file_path, 'r') as f:
        for idx, line in enumerate(f):
            if idx >= limit:
                break
            data.append(json.loads(line))
    return pd.DataFrame(data)

# Define the file path to your MED_QA.jsonl file
file_path = "/content/MED_QA.jsonl"
df = load_dataset(file_path, limit=1000)

# Clean text function
def clean_text(text):
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    text = text.lower()
    return text

# Apply cleaning to questions and answers
df['cleaned_question'] = df['question'].apply(clean_text)
df['cleaned_answer'] = df['answer'].apply(clean_text)

# Mapping answer options to full text
def map_option_to_answer(row):
    correct_option = row['answer'].strip()
    full_answer = row['options'].get(correct_option, "")
    return full_answer

df['full_answer_text'] = df.apply(map_option_to_answer, axis=1)

# Prepare the dataset for T5 fine-tuning
def prepare_t5_format(df):
    inputs = []
    targets = []

    for i, row in df.iterrows():
        question = row['cleaned_question']  # cleaned and tokenized question
        answer = row['full_answer_text']  # corresponding answer

        if answer:  # Only consider valid entries
            inputs.append(f"question: {question}")
            targets.append(answer)

    return inputs, targets

# Split the dataset into training and evaluation sets (90% train, 10% eval)
train_df, eval_df = train_test_split(df, test_size=0.1, random_state=42)

# Prepare the inputs and targets for both train and eval sets
train_inputs, train_targets = prepare_t5_format(train_df)
eval_inputs, eval_targets = prepare_t5_format(eval_df)

# Load pre-trained T5 model and tokenizer
model_name = "t5-small"  # You can use 't5-base' or 't5-large' for larger models
model = T5ForConditionalGeneration.from_pretrained(model_name)
tokenizer = T5Tokenizer.from_pretrained(model_name)

# Tokenize the inputs and targets
def tokenize_data(inputs, targets):
    input_encodings = tokenizer(inputs, padding=True, truncation=True, return_tensors="pt")
    target_encodings = tokenizer(targets, padding=True, truncation=True, return_tensors="pt")
    return input_encodings, target_encodings

# Tokenize training and evaluation data
train_input_encodings, train_target_encodings = tokenize_data(train_inputs, train_targets)
eval_input_encodings, eval_target_encodings = tokenize_data(eval_inputs, eval_targets)

# Custom Dataset class for fine-tuning
class QADataset(torch.utils.data.Dataset):
    def __init__(self, input_encodings, target_encodings):
        self.input_encodings = input_encodings
        self.target_encodings = target_encodings

    def __getitem__(self, idx):
        return {
            'input_ids': self.input_encodings['input_ids'][idx],
            'attention_mask': self.input_encodings['attention_mask'][idx],
            'labels': self.target_encodings['input_ids'][idx]
        }

    def __len__(self):
        return len(self.input_encodings['input_ids'])

# Create the dataset for training and evaluation
train_dataset = QADataset(train_input_encodings, train_target_encodings)
eval_dataset = QADataset(eval_input_encodings, eval_target_encodings)

# Define the training arguments and the trainer object
from transformers import Trainer, TrainingArguments

training_args = TrainingArguments(
    output_dir='./t5_finetuned_medqa',
    evaluation_strategy="epoch",  # Perform evaluation at the end of each epoch
    per_device_train_batch_size=4,
    per_device_eval_batch_size=4,
    learning_rate=3e-5,
    num_train_epochs=5,  # You can adjust the number of epochs if necessary
    weight_decay=0.02,
    logging_dir='./logs',  # Directory to save logs
    logging_steps=10,  # Log every 10 steps
    save_steps=100,  # Save the model every 100 steps
    save_total_limit=2,  # Keep only the last 2 models
    report_to="none",  # Disable reporting to external services like Weights & Biases
)


trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset
)

# Start training
trainer.train()

"""4. **Agent Development RAG Pipeline**

"""

from transformers import T5ForConditionalGeneration, T5Tokenizer

# Load the fine-tuned model and tokenizer
model_name = "t5-small"  # Change this if you're using 't5-base' or 't5-large'
model = T5ForConditionalGeneration.from_pretrained('/content/t5_finetuned_medqa/checkpoint-1100')  # Use your fine-tuned model path
tokenizer = T5Tokenizer.from_pretrained(model_name)

# Function to generate an answer for a given question
# Function to generate an answer for a given question
def generate_answer(question):
    input_text = f"question: {question}"  # Format the input as a question
    input_ids = tokenizer(input_text, return_tensors="pt").input_ids  # Tokenize input
    outputs = model.generate(input_ids, max_new_tokens=150, num_beams=5, early_stopping=True)  # Generate answer
    answer = tokenizer.decode(outputs[0], skip_special_tokens=True)  # Decode generated tokens to text
    return answer

# Example usage:
test_question = "What is the treatment for diabetes?"
generated_answer = generate_answer(test_question)

print(f"Question: {test_question}")
print(f"Generated Answer: {generated_answer}")



!pip install sentence-transformers
!pip install faiss-gpu

!pip install faiss-cpu

from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

# Load a pre-trained sentence transformer model
model = SentenceTransformer('all-MiniLM-L6-v2')  # You can use any other model

# Example corpus (text passages)
corpus = [
    "What is the capital of France?",
    "How to bake a chocolate cake?",
    "What is the boiling point of water?",
    "Tell me about the Great Wall of China."
]

# Generate embeddings for the corpus
corpus_embeddings = model.encode(corpus, convert_to_tensor=False)

# Convert embeddings to a numpy array
corpus_embeddings = np.array(corpus_embeddings)

# Create a FAISS index
d = corpus_embeddings.shape[1]  # Dimension of embeddings
index = faiss.IndexFlatL2(d)  # L2 distance (Euclidean)
index.add(corpus_embeddings)  # Add embeddings to the index

# Save the FAISS index
faiss.write_index(index, "faiss_index.index")



from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

# Load a pre-trained sentence transformer model
model = SentenceTransformer('all-MiniLM-L6-v2')  # You can use any other model

# Updated corpus with relevant medical information
corpus = [
    "Diabetes is a chronic condition that affects how your body turns food into energy.",
    "Symptoms of diabetes include increased thirst, frequent urination, and fatigue.",
    "The Great Wall of China is an ancient series of walls and fortifications.",
    "Chocolate cake is made by combining sugar, butter, flour, and cocoa powder.",
    "The boiling point of water is 100 degrees Celsius at sea level."
]

# Generate embeddings for the updated corpus
corpus_embeddings = model.encode(corpus, convert_to_tensor=False)

# Convert embeddings to a numpy array
corpus_embeddings = np.array(corpus_embeddings)

# Create a FAISS index
d = corpus_embeddings.shape[1]  # Dimension of embeddings
index = faiss.IndexFlatL2(d)  # L2 distance (Euclidean)
index.add(corpus_embeddings)  # Add embeddings to the index

# Save the FAISS index (optional)
faiss.write_index(index, "faiss_index.index")

# Define the function to embed the user query
def embed_query(query):
    query_embedding = model.encode([query], convert_to_tensor=False)[0]  # Embed query and return first result
    return query_embedding

# Define a function to retrieve passages
def retrieve_passages(query, n=5):
    # Convert the query into an embedding
    query_embedding = embed_query(query)

    # Search the FAISS index for the top n passages
    distances, indices = index.search(np.array([query_embedding]), n)

    # Retrieve passages based on indices
    retrieved_passages = [corpus[i] for i in indices[0]]  # Map index to the original corpus
    return retrieved_passages

# Function to generate an answer from the query and retrieved passages (assuming you have an LLM for this)
def generate_answer(query, retrieved_passages):
    # For simplicity, we'll return the retrieved passages as the "answer"
    return f"Query: {query}\nRetrieved Passages: {retrieved_passages}"

# Example query
user_query = "What are the symptoms of diabetes?"
retrieved_passages = retrieve_passages(user_query)
generated_answer = generate_answer(user_query, retrieved_passages)

print(generated_answer)

from transformers import T5ForConditionalGeneration, T5Tokenizer
import faiss
import numpy as np

# Initialize your fine-tuned model and tokenizer
model = T5ForConditionalGeneration.from_pretrained('./t5_finetuned_medqa/checkpoint-1125')
tokenizer = T5Tokenizer.from_pretrained('t5-small')

#
# Function to retrieve top N passages from FAISS
def retrieve_passages(query, n=5):
    # Convert the query into an embedding (here you may use any embedding model you have)
    query_embedding = embed_query(query)
    distances, indices = index.search(np.array([query_embedding]), n)
    retrieved_passages = [get_passage_from_index(i) for i in indices[0]]  # Custom function to map index to passages
    return retrieved_passages

# Function to combine the query and retrieved passages
def prepare_input(query, passages):
    input_text = f"User Query: {query}\n"
    for idx, passage in enumerate(passages):
        input_text += f"Passage {idx + 1}: {passage}\n"
    return input_text

# Function to generate the response using the LLM
def generate_answer(query, retrieved_passages):
    input_text = prepare_input(query, retrieved_passages)
    inputs = tokenizer(input_text, return_tensors='pt', max_length=512, truncation=True)
    outputs = model.generate(**inputs)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)

# Example query
user_query = "What are the symptoms of diabetes?"
retrieved_passages = retrieve_passages(user_query)
generated_answer = generate_answer(user_query, retrieved_passages)

print(generated_answer)



from flask import Flask, request, jsonify

app = Flask(__name__)

from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

# Load a pre-trained sentence transformer model
model = SentenceTransformer('all-MiniLM-L6-v2')  # You can use any other model

# Updated corpus with relevant medical information
corpus = [
    "Diabetes is a chronic condition that affects how your body turns food into energy.",
    "Symptoms of diabetes include increased thirst, frequent urination, and fatigue.",
    "The Great Wall of China is an ancient series of walls and fortifications.",
    "Chocolate cake is made by combining sugar, butter, flour, and cocoa powder.",
    "The boiling point of water is 100 degrees Celsius at sea level."
]

# Generate embeddings for the updated corpus
corpus_embeddings = model.encode(corpus, convert_to_tensor=False)

# Convert embeddings to a numpy array
corpus_embeddings = np.array(corpus_embeddings)

# Create a FAISS index
d = corpus_embeddings.shape[1]  # Dimension of embeddings
index = faiss.IndexFlatL2(d)  # L2 distance (Euclidean)
index.add(corpus_embeddings)  # Add embeddings to the index

# Save the FAISS index (optional)
faiss.write_index(index, "faiss_index.index")

# Define the function to embed the user query
def embed_query(query):
    query_embedding = model.encode([query], convert_to_tensor=False)[0]  # Embed query and return first result
    return query_embedding

# Define a function to retrieve passages
def retrieve_passages(query, n=5):
    # Convert the query into an embedding
    query_embedding = embed_query(query)

    # Search the FAISS index for the top n passages
    distances, indices = index.search(np.array([query_embedding]), n)

    # Retrieve passages based on indices
    retrieved_passages = [corpus[i] for i in indices[0]]  # Map index to the original corpus
    return retrieved_passages

# Function to generate an answer from the query and retrieved passages (assuming you have an LLM for this)
def generate_answer(query, retrieved_passages):
    # For simplicity, we'll return the retrieved passages as the "answer"
    return f"Query: {query}\nRetrieved Passages: {retrieved_passages}"


input_ids = tokenizer(input_text, return_tensors="pt", clean_up_tokenization_spaces=True).input_ids

# Example query
user_query = "What are the symptoms of diabetes?"
retrieved_passages = retrieve_passages(user_query)
generated_answer = generate_answer(user_query, retrieved_passages)

print(generated_answer)


@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    user_query = data.get('query', '')

    if user_query:
        retrieved_passages = retrieve_passages(user_query)
        answer = generate_answer(user_query, retrieved_passages)
        return jsonify({'query': user_query, 'answer': answer})
    else:
        return jsonify({'error': 'No query provided'}), 400

if __name__ == '__main__':
    app.run(debug=True)



def prepare_input(query, retrieved_passages):
    passages = " ".join(retrieved_passages)  # Combine retrieved passages
    return f"question: {query} context: {passages}"

from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from transformers import T5ForConditionalGeneration, T5Tokenizer

# Load the T5 model and tokenizer for answer generation
model_name = "t5-small"  # or your fine-tuned model path
model = T5ForConditionalGeneration.from_pretrained(model_name)
tokenizer = T5Tokenizer.from_pretrained(model_name)

# Load the sentence transformer model
sentence_model = SentenceTransformer('all-MiniLM-L6-v2')

# Updated corpus with relevant medical information
corpus = [
    "Diabetes is a chronic condition that affects how your body turns food into energy.",
    "Symptoms of diabetes include increased thirst, frequent urination, and fatigue.",
    "The Great Wall of China is an ancient series of walls and fortifications.",
    "Chocolate cake is made by combining sugar, butter, flour, and cocoa powder.",
    "The boiling point of water is 100 degrees Celsius at sea level."
]

# Generate embeddings for the updated corpus
corpus_embeddings = sentence_model.encode(corpus, convert_to_tensor=False)
corpus_embeddings = np.array(corpus_embeddings)

# Create a FAISS index
d = corpus_embeddings.shape[1]
index = faiss.IndexFlatL2(d)
index.add(corpus_embeddings)

# Function to embed the user query
def embed_query(query):
    query_embedding = sentence_model.encode([query], convert_to_tensor=False)[0]
    return query_embedding

# Function to retrieve passages
def retrieve_passages(query, n=5):
    query_embedding = embed_query(query)
    distances, indices = index.search(np.array([query_embedding]), n)
    retrieved_passages = [corpus[i] for i in indices[0]]
    return retrieved_passages

# Prepare input for the T5 model
def prepare_input(query, retrieved_passages):
    passages = " ".join(retrieved_passages)
    return f"question: {query} context: {passages}"

# Function to generate answers in batch
def batch_generate(queries, n=5):
    inputs = []
    for query in queries:
        retrieved_passages = retrieve_passages(query, n)
        input_text = prepare_input(query, retrieved_passages)
        inputs.append(input_text)

    # Tokenize all inputs at once
    inputs_tokenized = tokenizer(inputs, return_tensors='pt', max_length=512, truncation=True, padding=True)

    # Generate answers using the T5 model
    outputs = model.generate(**inputs_tokenized)

    return [tokenizer.decode(output, skip_special_tokens=True) for output in outputs]

# Example queries
batch_queries = ["What are the symptoms of diabetes?", "What is hypertension?"]
generated_answers = batch_generate(batch_queries)

# Print generated answers
for answer in generated_answers:
    print(answer)

# If using batching, you can modify the retrieval and LLM code like so:
def batch_generate(queries, n=5):
    inputs = []
    for query in queries:
        retrieved_passages = retrieve_passages(query, n)
        input_text = prepare_input(query, retrieved_passages)
        inputs.append(input_text)

    # Tokenize all inputs at once
    inputs_tokenized = tokenizer(inputs, return_tensors='pt', max_length=512, truncation=True, padding=True)
    outputs = model.generate(**inputs_tokenized)

    return [tokenizer.decode(output, skip_special_tokens=True) for output in outputs]

# Call for batched queries
batch_queries = ["What are the symptoms of diabetes?", "What is hypertension?"]
generated_answers = batch_generate(batch_queries)
for answer in generated_answers:
    print(answer)



# Test Dataset
test_data = [
    {
        "question": "What are the symptoms of diabetes?",
        "answer": "Symptoms of diabetes include increased thirst, frequent urination, and fatigue."
    },
    {
        "question": "What is hypertension?",
        "answer": "Hypertension is a condition where the blood pressure in the arteries is persistently elevated."
    },
    {
        "question": "What is asthma?",
        "answer": "Asthma is a condition that causes the airways to become inflamed, making breathing difficult."
    },
    {
        "question": "What are the treatments for heart disease?",
        "answer": "Treatments for heart disease can include medications, lifestyle changes, and surgical procedures."
    }
]

!pip install rouge-score

from nltk.translate.bleu_score import corpus_bleu
from rouge_score import rouge_scorer
import nltk

# Make sure to download the NLTK data for BLEU score
nltk.download('punkt')

"""# 5. Evaluation
# This section evaluates the model using BLEU, ROUGE, and other metrics.

def evaluate_model(generated_answers, test_data):
    '''
    Evaluates the model's performance using BLEU and ROUGE scores.
    '''
    # Evaluation code here...

"""

# Function to evaluate BLEU and ROUGE scores
def evaluate_model(generated_answers, test_data):
    # Prepare references and hypotheses
    references = [[item['answer'].split()] for item in test_data]
    hypotheses = [answer.split() for answer in generated_answers]

    # Calculate BLEU score
    bleu_score = corpus_bleu(references, hypotheses)

    # Calculate ROUGE scores
    scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
    rouge_scores = [scorer.score(item['answer'], generated_answer) for item, generated_answer in zip(test_data, generated_answers)]

    # Average ROUGE scores
    average_scores = {}
    for score in rouge_scores:
        for key in score:
            if key not in average_scores:
                average_scores[key] = {
                    'fmeasure': [],
                    'recall': [],
                    'precision': []
                }
            average_scores[key]['fmeasure'].append(score[key].fmeasure)
            average_scores[key]['recall'].append(score[key].recall)
            average_scores[key]['precision'].append(score[key].precision)

    for key in average_scores:
        average_scores[key] = {
            'fmeasure': sum(average_scores[key]['fmeasure']) / len(average_scores[key]['fmeasure']),
            'recall': sum(average_scores[key]['recall']) / len(average_scores[key]['recall']),
            'precision': sum(average_scores[key]['precision']) / len(average_scores[key]['precision']),
        }

    return bleu_score, average_scores

def error_analysis(generated_answers, test_data):
    for i, item in enumerate(test_data):
        if generated_answers[i] != item['answer']:
            print(f"Question: {item['question']}")
            print(f"Expected: {item['answer']}")
            print(f"Generated: {generated_answers[i]}")
            print("---")



generated_answers = [
    "Symptoms of diabetes include increased thirst, frequent urination, and fatigue.",
    "Hypertension is a condition where blood pressure is persistently high.",
    "Asthma causes inflammation of the airways, making breathing hard.",
    "Treatments for heart disease can include medications and surgery."
]

bleu, rouge = evaluate_model(generated_answers, test_data)
print(f"BLEU Score: {bleu}")
print(f"ROUGE Scores: {rouge}")

error_analysis(generated_answers, test_data)



"""**6**. **USER Interface Development**"""

!pip install Flask

from flask import Flask, request, jsonify, render_template
import json

app = Flask(__name__)

# Placeholder functions for your model and retrieval (implement these)
def retrieve_passages(query):
    # Implement your retrieval logic here
    return ["Sample passage related to: " + query]

def generate_answer(query, retrieved_passages):
    # Implement your answer generation logic here
    return "Generated answer based on: " + ', '.join(retrieved_passages)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    user_query = request.json.get('query')
    retrieved_passages = retrieve_passages(user_query)
    generated_answer = generate_answer(user_query, retrieved_passages)
    return jsonify({"answer": generated_answer})

if __name__ == '__main__':
    app.run(debug=True)

!python app.py

!pip freeze > requirements.txt