import os
import logging
import re

import json
from langchain.prompts import PromptTemplate

from langchain.text_splitter import CharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader, TextLoader, CSVLoader
from langchain_community.vectorstores.qdrant import Qdrant
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_community.llms import gpt4all
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

def load_config():
    with open('config.json', 'r') as file:
        config = json.load(file)
    return config

def setup_environment():
    cache_dir = "huggingface/"
    os.environ["HF_HOME"] = cache_dir
    os.environ["SENTENCE_TRANSFORMERS_HOME"] = cache_dir
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def load_documents_from_folder(folder_path):
    documents = []
    for filename in os.listdir(folder_path):
        full_path = os.path.join(folder_path, filename)
        if filename.endswith('.pdf'):
            loader = PyPDFLoader(full_path)
        elif filename.endswith('.txt'):
            loader = TextLoader(full_path)
        elif filename.endswith('.csv'):
            loader = CSVLoader(full_path)
        else:
            continue
        documents.extend(loader.load())
    return documents

def preprocess_text(text):
    text_lower = text.lower()
    text_no_punctuation = re.sub(r'[^\w\s\$\%\.\,\"\'\!\?\(\)]', '', text_lower)
    text_normalized_tabs = re.sub(r'(\t)+', '', text_no_punctuation)
    return text_normalized_tabs

def split_documents(documents):
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0, separator="\n")
    return text_splitter.split_documents(documents)

def setup_embeddings_and_vector_store(docs):
    #embeddings = HuggingFaceEmbeddings(model_name="huggingface/models--BAAI--bge-large-en-v1.5/snapshots/d4aa6901d3a41ba39fb536a557fa166f842b0e09/", show_progress=True, model_kwargs={'device': "cpu"})
    embeddings = HuggingFaceEmbeddings(model_name="huggingface/models--BAAI--bge-large-en-v1.5/snapshots/d4aa6901d3a41ba39fb536a557fa166f842b0e09/", show_progress=True)
    #embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-large-en-v1.5", show_progress=True, model_kwargs={'device': "cpu"})
    qdrant = Qdrant.from_documents(docs, embeddings, location=":memory:", collection_name="cde_data", force_recreate=True) # move to server
    return qdrant

def setup_langchain():
    config = load_config()
    template_content = next(item["content"] for item in config["templates"] if item["active"])
    rag_prompt = PromptTemplate(template=template_content, input_variables=["context","question"])
    callbacks = [StreamingStdOutCallbackHandler()]
    
    # Select the active model
    model_name = next(item["name"] for item in config["models"] if item["active"])
    llm = gpt4all.GPT4All(
        model=model_name,
        max_tokens=2048,
        n_threads=10,
        temp=0.3,
        top_p=0.2,
        top_k=40,
        n_batch=8,
        seed=100,
        allow_download=False,
        verbose=True,
        callbacks=callbacks
    )
    llm_chain = LLMChain(prompt=rag_prompt, llm=llm, verbose=True)
    return llm_chain

def format_docs(qdrant, query):
    found_docs = qdrant.similarity_search_with_score(query, k=4)
    return "\n\n".join(doc[0].page_content for doc in found_docs)

def run_query(llm_chain, qdrant, query):
    context = format_docs(qdrant, query)
    resp = llm_chain.invoke(input={"question": query, "context": context})
    print(resp['text'])

if __name__ == "__main__":
    setup_environment()
    documents = load_documents_from_folder("data")
    for document in documents:
        document.page_content = preprocess_text(document.page_content)
    docs = split_documents(documents)
    qdrant = setup_embeddings_and_vector_store(docs)
    llm_chain = setup_langchain()
    #query = "What is the average age of all employees?"
    #run_query(llm_chain, qdrant, query)
