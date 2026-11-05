#Import libraries
import streamlit as st
import chromadb
import hashlib

from groq import Groq
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

st.set_page_config(
    page_title="KnowMate AI",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 KnowMate AI")
st.subheader("Intelligent PDF Question Answering Chatbot")

st.write(
    "Upload your PDF documents and ask questions "
    "using Artificial Intelligence."
)

#GROQ_API_KEY
import os

# Create the .streamlit directory and write secrets.toml if it doesn't exist
os.makedirs("/content/.streamlit", exist_ok=True)
with open("/content/.streamlit/secrets.toml", "w") as f:
    f.write('GROQ_API_KEY = "	gsk_...OnGY"\n')

# Note: Please replace 'YOUR_GROQ_API_KEY_HERE' with your actual Groq API key.
# If you are using Colab Secrets (the key icon in the left sidebar), you can also do:
# from google.colab import userdata
# key = userdata.get('GROQ_API_KEY')

# Load using streamlit secrets
api_key = st.secrets["GROQ_API_KEY"]
client = Groq(api_key=api_key)

#Sentence Transformers=Converts Tokens into Numeric Vectors
@st.cache_resource
def load_embedding_model():

    model = SentenceTransformer(
        "all-MiniLM-L6-v2"
    )

    return model


embedding_model = load_embedding_model()

#ChromaDB
chroma_client = chromadb.PersistentClient(
    path="./chroma_db"
)

collection = chroma_client.get_or_create_collection(
    name="knowmate_documents"
)

#pyPDF
def extract_pdf_text(pdf_file):

    reader = PdfReader(pdf_file)

    documents = []

    for page_number, page in enumerate(reader.pages):

        text = page.extract_text()

        if text and text.strip():

            documents.append({
                "text": text,
                "page": page_number + 1
            })

    return documents

#Split text into chunks
def split_text(text, chunk_size=500, overlap=50):

    words = text.split()

    chunks = []

    for i in range(0, len(words), chunk_size - overlap):

        chunk = " ".join(
            words[i:i + chunk_size]
        )

        if chunk.strip():

            chunks.append(chunk)

    return chunks

#Generate embeddings and store them
def store_documents(pdf_files):

    documents = []
    metadatas = []
    ids = []

    for pdf_file in pdf_files:

        pages = extract_pdf_text(pdf_file)

        for page_data in pages:

            chunks = split_text(
                page_data["text"]
            )

            for index, chunk in enumerate(chunks):

                documents.append(chunk)

                metadatas.append({
                    "source": pdf_file.name,
                    "page": page_data["page"]
                })

                unique_id = hashlib.md5(
                    f"{pdf_file.name}_{page_data['page']}_{index}".encode()
                ).hexdigest()

                ids.append(unique_id)

    if not documents:
        return 0

    embeddings = embedding_model.encode(
        documents
    ).tolist()

    chroma_client.delete_collection(
        "knowmate_documents"
    )

    new_collection = chroma_client.create_collection(
        name="knowmate_documents"
    )

    new_collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )

    return len(documents)

#Retrieve relevant information
def retrieve_documents(question):

    query_embedding = embedding_model.encode(
        [question]
    ).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=4
    )

    return results

#Generate AI responses
def generate_answer(question, context, history):

    messages = [
        {
            "role": "system",
            "content": """
            You are KnowMate AI, an intelligent document assistant.

            Answer questions using the provided document context.

            If the answer is not available in the documents,
            clearly tell the user.

            Do not invent information.
            """
        }
    ]

    messages.extend(history[-6:])

    messages.append({
        "role": "user",
        "content": f"""
        Document Context:

        {context}

        User Question:

        {question}

        Answer based on the document context.
        """
    })

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.3,
        max_tokens=1000
    )

    return response.choices[0].message.content


uploaded_files = st.file_uploader(
    "Upload PDF Documents",
    type=["pdf"],
    accept_multiple_files=True
)

if st.button("Process Documents"):

    if uploaded_files:

        with st.spinner("Processing documents..."):

            count = store_documents(
                uploaded_files
            )

        if count > 0:

            st.success(
                f"Successfully processed {count} chunks!"
            )

        else:

            st.warning(
                "No readable text found in the PDFs."
            )

    else:

        st.warning("Please upload PDF documents.")


if "messages" not in st.session_state:

    st.session_state.messages = []


for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])


question = st.chat_input(
    "Ask something about your PDF documents..."
)


if question:

    st.session_state.messages.append({
        "role": "user",
        "content": question
    })

    with st.chat_message("user"):

        st.markdown(question)

    with st.chat_message("assistant"):

        with st.spinner("Thinking..."):

            results = collection.query(
                query_embeddings=embedding_model.encode(
                    [question]
                ).tolist(),
                n_results=4
            )

            retrieved_texts = results["documents"][0]

            metadata = results["metadatas"][0]

            context = "\n\n".join(retrieved_texts)

            answer = generate_answer(
                question,
                context,
                st.session_state.messages[:-1]
            )

            st.markdown(answer)

            st.markdown("**Sources:**")

            for item in metadata:

                st.write(
                    f"📄 {item['source']} - "
                    f"Page {item['page']}"
                )

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })

