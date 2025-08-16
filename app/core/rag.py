import os
import shutil
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import ConversationalRetrievalChain
from langchain_community.llms import Ollama
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory

# Global variables for models (can be configured via environment variables later)
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
# LLM_MODEL_REPO_ID is no longer directly used for local model loading, but kept for context
LLM_MODEL_REPO_ID = "llama3.2" # Using llama3.2 from Ollama

def process_documents(file_paths: list):
    """
    Loads PDF documents, splits them into chunks, creates embeddings,
    and stores them in a Chroma vectorstore.
    """
    documents = []
    for file_path in file_paths:
        loader = PyPDFLoader(file_path)
        documents.extend(loader.load())

    # Split documents into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    chunks = text_splitter.split_documents(documents)

    # Create embeddings
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL_NAME)

    # Create Chroma vectorstore
    persist_directory = "data/chroma_db"
    
    if not os.path.exists(persist_directory):
        os.makedirs(persist_directory)

    vectorstore = Chroma.from_documents(chunks, embeddings, persist_directory=persist_directory)
    
    return vectorstore

def get_rag_chain(vectorstore):
    """
    Creates a conversational retrieval chain with memory.
    """
    llm = Ollama(model="llama3.2", base_url="http://host.docker.internal:11434")

    # Use a memory buffer to hold conversation history
    memory = ConversationBufferMemory(
        memory_key='chat_history', 
        return_messages=True, 
        output_key='answer' # Specify output key for the chain
    )

    # Create the conversational chain
    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=vectorstore.as_retriever(),
        memory=memory,
        return_source_documents=False,
        # The prompt for combining documents will be simpler, 
        # as the history is handled separately.
        combine_docs_chain_kwargs={"prompt": PromptTemplate.from_template(
            "Responde la pregunta basándote únicamente en el siguiente contexto:\n\n{context}\n\nPregunta: {question}\nRespuesta:"
        )}
    )
    
    return qa_chain

def summarize_documents(vectorstore):
    """
    Generates a concise summary for each document in the vectorstore.
    """
    llm = Ollama(model="llama3.2", base_url="http://host.docker.internal:11434")
    
    chroma_client = vectorstore._client
    collection_name = vectorstore._collection.name
    collection = chroma_client.get_collection(name=collection_name)
    
    # Get all documents with their metadata to group them by source
    count = collection.count()
    if count == 0:
        return "No hay documentos para resumir."
        
    all_chroma_docs = collection.get(include=['metadatas', 'documents'], limit=count)

    # Group document chunks by their source file
    docs_by_source = {}
    for i, metadata in enumerate(all_chroma_docs['metadatas']):
        source = metadata.get('source', 'unknown_source')
        if source not in docs_by_source:
            docs_by_source[source] = []
        docs_by_source[source].append(all_chroma_docs['documents'][i])

    # Generate a summary for each document
    summaries = []
    summary_prompt_template = """Por favor, resume el siguiente texto de forma concisa en 3-5 líneas.

Texto:
{text}

Resumen Conciso:"""
    summary_prompt = PromptTemplate.from_template(summary_prompt_template)
    from langchain.chains import LLMChain
    summary_chain = LLMChain(llm=llm, prompt=summary_prompt)

    for source, docs in docs_by_source.items():
        full_content = " ".join(docs)
        # Extracting the file name for the summary header
        file_name = os.path.basename(source)
        
        summary_header = f"Resumen de: {file_name}"
        
        summary_result = summary_chain.invoke(input={"text": full_content})['text']
        summaries.append(f"**{summary_header}**\n{summary_result}")
    
    return "\n\n".join(summaries)