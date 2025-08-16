import streamlit as st
import os
from app.core.rag import process_documents, get_rag_chain, summarize_documents

# --- UI Configuration ---
st.set_page_config(page_title="CatchAI - Copiloto Conversacional", layout="wide")

st.title("🧠 CatchAI - Copiloto Conversacional sobre Documentos")
st.markdown("""
    Sube hasta 5 archivos PDF y haz preguntas en lenguaje natural sobre su contenido.
    """)

# --- File Upload Section ---
uploaded_files = st.file_uploader(
    "Sube tus archivos PDF (máximo 5)",
    type="pdf",
    accept_multiple_files=True
)

# --- Process Documents Button ---
if st.button("Procesar Documentos"):
    if uploaded_files:
        if len(uploaded_files) > 5:
            st.warning("Por favor, sube un máximo de 5 archivos PDF.")
            st.stop() # Stop execution if more than 5 files are uploaded
        # Create a temporary directory to save uploaded files
        temp_dir = "data/uploaded_pdfs"
        os.makedirs(temp_dir, exist_ok=True)

        file_paths = []
        for uploaded_file in uploaded_files:
            file_path = os.path.join(temp_dir, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            file_paths.append(file_path)
        
        with st.spinner("Procesando documentos... Esto puede tardar unos minutos."):
            # Call the RAG core function to process documents
            # This function will load, split, embed, and store documents
            vectorstore = process_documents(file_paths)
            st.session_state.vectorstore = vectorstore # Store vectorstore in session state
        st.success("Documentos procesados y listos para preguntar!")
    else:
        st.warning("Por favor, sube al menos un archivo PDF para procesar.")

# --- Conversational Interface ---
if "vectorstore" in st.session_state:
    # Create and store the RAG chain in the session state if it doesn't exist
    if "rag_chain" not in st.session_state:
        st.session_state.rag_chain = get_rag_chain(st.session_state.vectorstore)

    # Summarization section
    if st.button("Resumir Documentos"):
        with st.spinner("Generando resumen..."):
            # Store summary in session state
            st.session_state.summary = summarize_documents(st.session_state.vectorstore)

    # Display summary if it exists in session state
    if "summary" in st.session_state:
        st.subheader("Resumen de los Documentos:")
        st.markdown(st.session_state.summary, unsafe_allow_html=True)
        st.markdown("---") # Add a separator

    st.subheader("Haz tu pregunta:")
    
    # Initialize and display chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept and process user input
    if prompt := st.chat_input("Escribe tu pregunta aquí..."):
        # Add user message to history and display it
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get and display assistant response
        with st.chat_message("assistant"):
            with st.spinner("Respondiendo..."):
                response = st.session_state.rag_chain.invoke({
                    "question": prompt,
                    "chat_history": st.session_state.messages
                })
                answer = response['answer']
                st.markdown(answer)
                # Add assistant response to history
                st.session_state.messages.append({"role": "assistant", "content": answer})
else:
    st.info("Sube y procesa tus documentos para empezar a chatear.")
